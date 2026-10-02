/*
###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
*/

/*
Read-only SCPI server for the PyRPL FPGA image.

The server lets a second acquisition program read the PyRPL DSP signals while
PyRPL (through monitor_server) keeps full control of the lockbox. It never
writes to the FPGA: /dev/mem is mapped with PROT_READ only. Every client gets
its own forked process, so a client waiting for a trigger does not block the
others.

Usage:

    pyrpl_scpi_server [-p PORT] [-i PROFILE] [-s NAME=INDEX,...] [-m FILE]

    -p PORT   TCP port (default 5000, the port of the stock SCPI server)
    -i ID     FPGA profile id reported by *IDN? (default: content of
              /tmp/pyrpl_fpga_profile, else "unknown")
    -s LIST   DSP signals available in the loaded profile, for example
              "in1=10,in2=11,pid0=0". Defaults to the full PyRPL signal map.
    -m FILE   simulation: map FILE instead of /dev/mem. The file holds the
              HK block (0x1000 bytes) followed by the DSP block (0x100000
              bytes). Used by the unit tests.

Protocol: newline terminated text commands, SCPI style (case insensitive,
short or long keywords, several commands per line separated by ';').
Responses end with "\r\n" like the stock Red Pitaya SCPI server. A query that
fails answers "ERR!" so that clients stay in sync; the reason is available
through SYSTem:ERRor?. See docs/source/user_guide/scpi_server.rst.
*/

#define _GNU_SOURCE

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define SERVER_VERSION "1.0"

#define HK_BASE 0x40000000UL
#define HK_SIZE 0x1000UL
#define DSP_BASE 0x40300000UL
#define DSP_SIZE 0x100000UL

/* house keeping registers (red_pitaya_hk.v) */
#define HK_EXP_P_DIR 0x10
#define HK_EXP_N_DIR 0x14
#define HK_EXP_P_IN 0x20
#define HK_EXP_N_IN 0x24

/* the DSP block returns output_signal[n] at 0x10 + n * 0x10000 (red_pitaya_dsp.v) */
#define DSP_SAMPLE_OFFSET 0x10
#define DSP_SLOT_SIZE 0x10000
#define DSP_SLOTS 16
#define SIGNAL_NORM 8191.0 /* 2**13 - 1, same as pyrpl's Sampler */

#define MAX_SIGNALS 32
#define MAX_PARAMS (MAX_SIGNALS + 4)
#define MAX_LINE 4096
#define MAX_ACQ_VALUES 1000000 /* samples x signals of one SIGnal:ACQuire? */
#define MAX_DURATION 3600.0    /* upper bound for every time parameter, s */
#define ERROR_QUEUE 16

typedef struct {
    char name[32];
    int index;
} signal_t;

static const signal_t default_signals[] = {
    {"in1", 10},  {"in2", 11},  {"out1", 12},  {"out2", 13}, {"iq0", 5},
    {"iq1", 6},   {"iq2", 7},   {"iq2_2", 14}, {"pid0", 0},  {"pid1", 1},
    {"pid2", 2},  {"asg0", 8},  {"asg1", 9},   {"trig", 3},  {"iir", 4},
    {"cordic", 4}, {"off", 15},
};

static signal_t signals[MAX_SIGNALS];
static int n_signals = 0;
static char profile_id[64] = "unknown";

static volatile uint32_t *hk = NULL;
static volatile uint32_t *dsp = NULL;

enum { EDGE_RISING, EDGE_FALLING, EDGE_BOTH };

typedef struct {
    int fd;
    /* trigger settings, per connection */
    int trig_pin;  /* -1: no trigger */
    int trig_side; /* 0: DIOx_P, 1: DIOx_N */
    int trig_edge;
    double trig_timeout; /* s, 0 waits forever */
    double trig_delay;   /* s between trigger edge and first sample */
    /* SCPI error queue */
    int err_code[ERROR_QUEUE];
    char err_msg[ERROR_QUEUE][96];
    int err_count;
    /* response of the line being processed */
    char *out;
    size_t out_len, out_cap;
    int out_items;
    int disconnected;
} conn_t;

/* ------------------------------------------------------------------------ */
/* helpers                                                                   */

static double now(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + 1e-9 * ts.tv_nsec;
}

static void push_error(conn_t *c, int code, const char *fmt, ...)
{
    va_list ap;
    if (c->err_count >= ERROR_QUEUE) {
        c->err_code[ERROR_QUEUE - 1] = -350;
        snprintf(c->err_msg[ERROR_QUEUE - 1], sizeof(c->err_msg[0]), "Queue overflow");
        return;
    }
    c->err_code[c->err_count] = code;
    va_start(ap, fmt);
    vsnprintf(c->err_msg[c->err_count], sizeof(c->err_msg[0]), fmt, ap);
    va_end(ap);
    c->err_count++;
}

static void out_reserve(conn_t *c, size_t extra)
{
    if (c->out_len + extra + 1 <= c->out_cap)
        return;
    size_t cap = c->out_cap ? c->out_cap : 4096;
    while (cap < c->out_len + extra + 1)
        cap *= 2;
    char *p = realloc(c->out, cap);
    if (p == NULL) {
        perror("realloc");
        exit(1);
    }
    c->out = p;
    c->out_cap = cap;
}

static void out_printf(conn_t *c, const char *fmt, ...)
{
    va_list ap;
    int n;
    out_reserve(c, 64);
    va_start(ap, fmt);
    n = vsnprintf(c->out + c->out_len, c->out_cap - c->out_len, fmt, ap);
    va_end(ap);
    if (n < 0)
        return;
    if ((size_t)n >= c->out_cap - c->out_len) {
        out_reserve(c, n);
        va_start(ap, fmt);
        vsnprintf(c->out + c->out_len, c->out_cap - c->out_len, fmt, ap);
        va_end(ap);
    }
    c->out_len += n;
}

/* every query response is one item; items of one line are joined with ';' */
static void begin_item(conn_t *c)
{
    if (c->out_items++ > 0)
        out_printf(c, ";");
}

static int send_all(int fd, const char *buf, size_t len)
{
    while (len > 0) {
        ssize_t n = send(fd, buf, len, 0);
        if (n < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        buf += n;
        len -= n;
    }
    return 0;
}

/* true once the peer has closed the connection */
static int peer_closed(conn_t *c)
{
    char ch;
    ssize_t n = recv(c->fd, &ch, 1, MSG_PEEK | MSG_DONTWAIT);
    if (n == 0 || (n < 0 && errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR))
        c->disconnected = 1;
    return c->disconnected;
}

/* waits until the monotonic time t, sleeping when far away; returns -1 on disconnect */
static int wait_until(conn_t *c, double t)
{
    for (;;) {
        double remaining = t - now();
        if (remaining <= 0)
            return 0;
        if (remaining > 2e-3) {
            double chunk = remaining - 1e-3;
            if (chunk > 0.1)
                chunk = 0.1;
            struct timespec ts = {(time_t)chunk, (long)((chunk - (time_t)chunk) * 1e9)};
            nanosleep(&ts, NULL);
            if (peer_closed(c))
                return -1;
        }
    }
}

/* matches a SCPI keyword: "SIGnal" accepts "SIG" and "SIGNAL" */
static int kw_match(const char *tok, const char *pattern)
{
    size_t short_len = 0, len = strlen(tok);
    while (pattern[short_len] && !islower((unsigned char)pattern[short_len]))
        short_len++;
    if (len == short_len && strncasecmp(tok, pattern, len) == 0)
        return 1;
    return len == strlen(pattern) && strcasecmp(tok, pattern) == 0;
}

static char *trim(char *s)
{
    while (isspace((unsigned char)*s))
        s++;
    char *end = s + strlen(s);
    while (end > s && isspace((unsigned char)end[-1]))
        *--end = '\0';
    return s;
}

static char *unquote(char *s)
{
    size_t len = strlen(s);
    if (len >= 2 && (s[0] == '"' || s[0] == '\'') && s[len - 1] == s[0]) {
        s[len - 1] = '\0';
        s++;
    }
    return s;
}

static int parse_double(const char *s, double *value)
{
    char *end;
    errno = 0;
    *value = strtod(s, &end);
    return errno == 0 && end != s && *trim(end) == '\0' && isfinite(*value);
}

static int parse_long(const char *s, long *value)
{
    char *end;
    errno = 0;
    *value = strtol(s, &end, 10);
    return errno == 0 && end != s && *trim(end) == '\0';
}

/* ------------------------------------------------------------------------ */
/* hardware access, read only                                                */

static int find_signal(const char *name)
{
    for (int i = 0; i < n_signals; i++)
        if (strcasecmp(signals[i].name, name) == 0)
            return signals[i].index;
    return -1;
}

static inline int read_raw(int index)
{
    int raw = dsp[(index * DSP_SLOT_SIZE + DSP_SAMPLE_OFFSET) / 4] & 0x3fff;
    return (raw & 0x2000) ? raw - 0x4000 : raw;
}

/* parses "DIO3_P" / "dio3_n"; returns 0 on success */
static int parse_pin(const char *s, int *pin, int *side)
{
    if (strlen(s) != 6 || strncasecmp(s, "DIO", 3) != 0 || s[3] < '0' || s[3] > '7' ||
        s[4] != '_')
        return -1;
    *pin = s[3] - '0';
    if (toupper((unsigned char)s[5]) == 'P')
        *side = 0;
    else if (toupper((unsigned char)s[5]) == 'N')
        *side = 1;
    else
        return -1;
    return 0;
}

static inline int read_pin(int pin, int side)
{
    return (hk[(side ? HK_EXP_N_IN : HK_EXP_P_IN) / 4] >> pin) & 1;
}

static inline int pin_is_output(int pin, int side)
{
    return (hk[(side ? HK_EXP_N_DIR : HK_EXP_P_DIR) / 4] >> pin) & 1;
}

/* busy-waits for the configured edge. Returns 0 and the edge time, -1 on
 * timeout, -2 when the client disconnected. */
static int wait_trigger(conn_t *c, double *t_edge)
{
    double deadline = c->trig_timeout > 0 ? now() + c->trig_timeout : INFINITY;
    int previous = read_pin(c->trig_pin, c->trig_side);
    unsigned long loops = 0;
    for (;;) {
        int current = read_pin(c->trig_pin, c->trig_side);
        if (current != previous) {
            if (c->trig_edge == EDGE_BOTH || (c->trig_edge == EDGE_RISING && current) ||
                (c->trig_edge == EDGE_FALLING && !current)) {
                *t_edge = now();
                return 0;
            }
            previous = current;
        }
        if ((++loops & 0xfff) == 0) {
            if (now() > deadline)
                return -1;
            if (peer_closed(c))
                return -2;
        }
    }
}

/* ------------------------------------------------------------------------ */
/* commands                                                                  */

/* resolves params[first..] to DSP indices; returns their count or -1 */
static int resolve_signals(conn_t *c, char **params, int n_params, int first, int *indices)
{
    int k = 0;
    if (n_params <= first) {
        push_error(c, -109, "Missing parameter: signal name");
        return -1;
    }
    for (int i = first; i < n_params; i++) {
        int index = find_signal(params[i]);
        if (index < 0) {
            push_error(c, -224, "Unknown signal '%s', see SIGnal:LIST?", params[i]);
            return -1;
        }
        indices[k++] = index;
    }
    return k;
}

static int cmd_values(conn_t *c, char **params, int n_params, int raw)
{
    int indices[MAX_PARAMS], values[MAX_PARAMS];
    int k = resolve_signals(c, params, n_params, 0, indices);
    if (k < 0)
        return -1;
    for (int i = 0; i < k; i++) /* read back to back, format afterwards */
        values[i] = read_raw(indices[i]);
    begin_item(c);
    for (int i = 0; i < k; i++) {
        if (raw)
            out_printf(c, i ? ",%d" : "%d", values[i]);
        else
            out_printf(c, i ? ",%.8g" : "%.8g", values[i] / SIGNAL_NORM);
    }
    return 0;
}

static int cmd_stats(conn_t *c, char **params, int n_params)
{
    double duration;
    int indices[MAX_PARAMS];
    if (n_params < 1 || !parse_double(params[0], &duration) || duration < 0 ||
        duration > MAX_DURATION) {
        push_error(c, -224, "Duration must be between 0 and %g s", MAX_DURATION);
        return -1;
    }
    int k = resolve_signals(c, params, n_params, 1, indices);
    if (k < 0)
        return -1;
    double sum[MAX_PARAMS] = {0}, sumsq[MAX_PARAMS] = {0};
    int vmin[MAX_PARAMS], vmax[MAX_PARAMS];
    for (int i = 0; i < k; i++) {
        vmin[i] = INT32_MAX;
        vmax[i] = INT32_MIN;
    }
    double end = now() + duration;
    long n = 0;
    do {
        for (int i = 0; i < k; i++) {
            int v = read_raw(indices[i]);
            sum[i] += v;
            sumsq[i] += (double)v * v;
            if (v < vmin[i])
                vmin[i] = v;
            if (v > vmax[i])
                vmax[i] = v;
        }
        n++;
        if ((n & 0xfff) == 0 && peer_closed(c))
            return -1;
    } while (now() < end);
    begin_item(c);
    for (int i = 0; i < k; i++) {
        double mean = sum[i] / n;
        double variance = sumsq[i] / n - mean * mean;
        double std = variance > 0 ? sqrt(variance) : 0.0;
        out_printf(c, "%s%.8g,%.8g,%.8g,%.8g", i ? "," : "", mean / SIGNAL_NORM,
                   std / SIGNAL_NORM, vmin[i] / SIGNAL_NORM, vmax[i] / SIGNAL_NORM);
    }
    return 0;
}

static int cmd_acquire(conn_t *c, char **params, int n_params)
{
    long n;
    double interval;
    int indices[MAX_PARAMS];
    if (n_params < 2 || !parse_long(params[0], &n) || n < 1) {
        push_error(c, -224, "First parameter must be the number of points (>= 1)");
        return -1;
    }
    if (!parse_double(params[1], &interval) || interval < 0 || interval > MAX_DURATION) {
        push_error(c, -224, "Second parameter must be the interval in s (>= 0)");
        return -1;
    }
    int k = resolve_signals(c, params, n_params, 2, indices);
    if (k < 0)
        return -1;
    if (n > MAX_ACQ_VALUES || n * k > MAX_ACQ_VALUES) {
        push_error(c, -222, "At most %d values (points x signals) per acquisition",
                   MAX_ACQ_VALUES);
        return -1;
    }
    if (interval * (n - 1) + c->trig_delay > MAX_DURATION) {
        push_error(c, -222, "Acquisition would last more than %g s", MAX_DURATION);
        return -1;
    }

    double *t = malloc(n * sizeof(double));
    int16_t *raw = malloc(n * k * sizeof(int16_t));
    if (t == NULL || raw == NULL) {
        free(t);
        free(raw);
        push_error(c, -225, "Out of memory");
        return -1;
    }

    double t0;
    if (c->trig_pin >= 0) {
        int result = wait_trigger(c, &t0);
        if (result != 0) {
            free(t);
            free(raw);
            if (result == -1)
                push_error(c, -200, "Trigger timeout");
            return -1;
        }
    } else {
        t0 = now();
    }

    double start = t0 + c->trig_delay;
    for (long i = 0; i < n; i++) {
        if (wait_until(c, start + i * interval) < 0) {
            free(t);
            free(raw);
            return -1;
        }
        t[i] = now() - t0;
        for (int j = 0; j < k; j++)
            raw[i * k + j] = read_raw(indices[j]);
    }

    begin_item(c);
    for (long i = 0; i < n; i++) {
        out_printf(c, i ? ",%.9g" : "%.9g", t[i]);
        for (int j = 0; j < k; j++)
            out_printf(c, ",%.8g", raw[i * k + j] / SIGNAL_NORM);
    }
    free(t);
    free(raw);
    return 0;
}

static const char *edge_name(int edge)
{
    return edge == EDGE_RISING ? "RISING" : edge == EDGE_FALLING ? "FALLING" : "BOTH";
}

static int set_time(conn_t *c, char **params, int n_params, double *target, const char *what)
{
    double value;
    if (n_params != 1 || !parse_double(params[0], &value) || value < 0 ||
        value > MAX_DURATION) {
        push_error(c, -224, "%s must be between 0 and %g s", what, MAX_DURATION);
        return -1;
    }
    *target = value;
    return 0;
}

static void reset_settings(conn_t *c)
{
    c->trig_pin = -1;
    c->trig_side = 0;
    c->trig_edge = EDGE_RISING;
    c->trig_timeout = 1.0;
    c->trig_delay = 0.0;
}

/* executes one command; returns -1 for a failed query so that the caller can answer ERR! */
static int execute(conn_t *c, char *command)
{
    char *header = command, *args = command;
    char *params[MAX_PARAMS];
    int n_params = 0;
    char *nodes[4];
    int n_nodes = 0, query;

    while (*args && !isspace((unsigned char)*args))
        args++;
    if (*args)
        *args++ = '\0';
    args = trim(args);
    if (*args) {
        char *save = NULL;
        for (char *p = strtok_r(args, ",", &save); p; p = strtok_r(NULL, ",", &save)) {
            if (n_params == MAX_PARAMS) {
                push_error(c, -108, "Too many parameters");
                return -1;
            }
            params[n_params++] = unquote(trim(p));
        }
    }

    size_t len = strlen(header);
    query = len > 0 && header[len - 1] == '?';
    if (query)
        header[len - 1] = '\0';
    if (*header == ':')
        header++;
    if (*header == '*') {
        if (strcasecmp(header, "*IDN") == 0 && query) {
            begin_item(c);
            out_printf(c, "PYRPL,pyrpl_scpi_server,%s,%s", profile_id, SERVER_VERSION);
            return 0;
        }
        if (strcasecmp(header, "*RST") == 0 && !query) {
            reset_settings(c);
            c->err_count = 0;
            return 0;
        }
        if (strcasecmp(header, "*CLS") == 0 && !query) {
            c->err_count = 0;
            return 0;
        }
        push_error(c, -113, "Undefined header");
        return -1;
    }
    {
        char *save = NULL;
        for (char *p = strtok_r(header, ":", &save); p; p = strtok_r(NULL, ":", &save)) {
            if (n_nodes == 4) {
                push_error(c, -113, "Undefined header");
                return -1;
            }
            nodes[n_nodes++] = p;
        }
    }

    if (n_nodes == 2 && kw_match(nodes[0], "SYSTem") && kw_match(nodes[1], "ERRor") && query) {
        begin_item(c);
        if (c->err_count == 0) {
            out_printf(c, "0,\"No error\"");
        } else {
            out_printf(c, "%d,\"%s\"", c->err_code[0], c->err_msg[0]);
            c->err_count--;
            memmove(c->err_code, c->err_code + 1, c->err_count * sizeof(c->err_code[0]));
            memmove(c->err_msg, c->err_msg + 1, c->err_count * sizeof(c->err_msg[0]));
        }
        return 0;
    }

    if (n_nodes == 2 && kw_match(nodes[0], "SIGnal")) {
        if (kw_match(nodes[1], "LIST") && query) {
            begin_item(c);
            for (int i = 0; i < n_signals; i++)
                out_printf(c, i ? ",%s" : "%s", signals[i].name);
            return 0;
        }
        if (kw_match(nodes[1], "VALue") && query)
            return cmd_values(c, params, n_params, 0);
        if (kw_match(nodes[1], "RAW") && query)
            return cmd_values(c, params, n_params, 1);
        if (kw_match(nodes[1], "STATistics") && query)
            return cmd_stats(c, params, n_params);
        if (kw_match(nodes[1], "ACQuire") && query)
            return cmd_acquire(c, params, n_params);
    }

    if (n_nodes == 2 && kw_match(nodes[0], "TRIGger")) {
        if (kw_match(nodes[1], "SOURce")) {
            if (query) {
                begin_item(c);
                if (c->trig_pin < 0)
                    out_printf(c, "NONE");
                else
                    out_printf(c, "DIO%d_%c", c->trig_pin, c->trig_side ? 'N' : 'P');
                return 0;
            }
            if (n_params != 1) {
                push_error(c, -109, "Expected one trigger source");
                return -1;
            }
            if (strcasecmp(params[0], "NONE") == 0) {
                c->trig_pin = -1;
                return 0;
            }
            int pin, side;
            if (parse_pin(params[0], &pin, &side) != 0) {
                push_error(c, -224, "Trigger source must be NONE or DIO0_P..DIO7_N");
                return -1;
            }
            c->trig_pin = pin;
            c->trig_side = side;
            return 0;
        }
        if (kw_match(nodes[1], "EDGE")) {
            if (query) {
                begin_item(c);
                out_printf(c, "%s", edge_name(c->trig_edge));
                return 0;
            }
            if (n_params == 1 && (kw_match(params[0], "RISing") || strcasecmp(params[0], "POS") == 0))
                c->trig_edge = EDGE_RISING;
            else if (n_params == 1 &&
                     (kw_match(params[0], "FALLing") || strcasecmp(params[0], "NEG") == 0))
                c->trig_edge = EDGE_FALLING;
            else if (n_params == 1 && kw_match(params[0], "BOTH"))
                c->trig_edge = EDGE_BOTH;
            else {
                push_error(c, -224, "Edge must be RISing, FALLing or BOTH");
                return -1;
            }
            return 0;
        }
        if (kw_match(nodes[1], "TIMeout")) {
            if (query) {
                begin_item(c);
                out_printf(c, "%g", c->trig_timeout);
                return 0;
            }
            return set_time(c, params, n_params, &c->trig_timeout, "Timeout");
        }
        if (kw_match(nodes[1], "DELay")) {
            if (query) {
                begin_item(c);
                out_printf(c, "%g", c->trig_delay);
                return 0;
            }
            return set_time(c, params, n_params, &c->trig_delay, "Delay");
        }
    }

    /* read-only subset of the stock DIG:PIN commands */
    if (n_nodes >= 2 && kw_match(nodes[0], "DIGital") && kw_match(nodes[1], "PIN") && query &&
        (n_nodes == 2 || (n_nodes == 3 && kw_match(nodes[2], "DIRection")))) {
        int pin, side;
        if (n_params != 1 || parse_pin(params[0], &pin, &side) != 0) {
            push_error(c, -224, "Pin must be DIO0_P..DIO7_N");
            return -1;
        }
        begin_item(c);
        if (n_nodes == 2)
            out_printf(c, "%d", read_pin(pin, side));
        else
            out_printf(c, "%s", pin_is_output(pin, side) ? "OUT" : "IN");
        return 0;
    }

    push_error(c, -113, "Undefined header");
    return -1;
}

static void execute_line(conn_t *c, char *line)
{
    char *save = NULL;
    c->out_len = 0;
    c->out_items = 0;
    for (char *command = strtok_r(line, ";", &save); command;
         command = strtok_r(NULL, ";", &save)) {
        command = trim(command);
        if (*command == '\0')
            continue;
        /* the header ends at the first whitespace */
        size_t header_len = strcspn(command, " \t");
        int is_query = header_len > 0 && command[header_len - 1] == '?';
        if (execute(c, command) < 0 && is_query) {
            begin_item(c);
            out_printf(c, "ERR!");
        }
        if (c->disconnected)
            return;
    }
    if (c->out_items > 0) {
        out_printf(c, "\r\n");
        if (send_all(c->fd, c->out, c->out_len) < 0)
            c->disconnected = 1;
    }
}

static void serve(int fd)
{
    conn_t c;
    char buffer[MAX_LINE + 1];
    size_t used = 0;
    int discarding = 0;

    memset(&c, 0, sizeof(c));
    c.fd = fd;
    reset_settings(&c);

    while (!c.disconnected) {
        ssize_t n = recv(fd, buffer + used, MAX_LINE - used, 0);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
            break;
        used += n;
        size_t start = 0;
        for (size_t i = 0; i < used && !c.disconnected; i++) {
            if (buffer[i] != '\n')
                continue;
            buffer[i] = '\0';
            if (!discarding)
                execute_line(&c, buffer + start);
            discarding = 0;
            start = i + 1;
        }
        memmove(buffer, buffer + start, used - start);
        used -= start;
        if (used == MAX_LINE) { /* line too long: drop it up to the next newline */
            if (!discarding)
                push_error(&c, -102, "Command line longer than %d bytes", MAX_LINE);
            discarding = 1;
            used = 0;
        }
    }
    free(c.out);
    close(fd);
}

/* ------------------------------------------------------------------------ */
/* start up                                                                  */

static int parse_signal_list(char *list)
{
    char *save = NULL;
    n_signals = 0;
    for (char *item = strtok_r(list, ",", &save); item; item = strtok_r(NULL, ",", &save)) {
        char *eq = strchr(item, '=');
        long index;
        if (eq == NULL || n_signals == MAX_SIGNALS)
            return -1;
        *eq = '\0';
        if (!parse_long(eq + 1, &index) || index < 0 || index >= DSP_SLOTS ||
            strlen(trim(item)) == 0 || strlen(trim(item)) >= sizeof(signals[0].name))
            return -1;
        snprintf(signals[n_signals].name, sizeof(signals[0].name), "%s", trim(item));
        signals[n_signals].index = (int)index;
        n_signals++;
    }
    return n_signals > 0 ? 0 : -1;
}

static void map_memory(const char *simulation_file)
{
    int fd;
    if (simulation_file != NULL) {
        fd = open(simulation_file, O_RDONLY);
        if (fd < 0) {
            perror(simulation_file);
            exit(1);
        }
        hk = mmap(NULL, HK_SIZE, PROT_READ, MAP_SHARED, fd, 0);
        dsp = mmap(NULL, DSP_SIZE, PROT_READ, MAP_SHARED, fd, HK_SIZE);
    } else {
        fd = open("/dev/mem", O_RDONLY | O_SYNC);
        if (fd < 0) {
            perror("/dev/mem");
            exit(1);
        }
        hk = mmap(NULL, HK_SIZE, PROT_READ, MAP_SHARED, fd, HK_BASE);
        dsp = mmap(NULL, DSP_SIZE, PROT_READ, MAP_SHARED, fd, DSP_BASE);
    }
    if (hk == MAP_FAILED || dsp == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }
    close(fd);
}

static void read_profile_file(void)
{
    FILE *f = fopen("/tmp/pyrpl_fpga_profile", "r");
    if (f == NULL)
        return;
    if (fgets(profile_id, sizeof(profile_id), f) == NULL)
        snprintf(profile_id, sizeof(profile_id), "unknown");
    profile_id[strcspn(profile_id, "\r\n")] = '\0';
    fclose(f);
}

int main(int argc, char *argv[])
{
    int port = 5000, opt, enable = 1;
    const char *simulation_file = NULL;
    char *signal_list = NULL;

    read_profile_file();
    while ((opt = getopt(argc, argv, "p:i:s:m:h")) != -1) {
        switch (opt) {
        case 'p':
            port = atoi(optarg);
            break;
        case 'i':
            snprintf(profile_id, sizeof(profile_id), "%s", optarg);
            break;
        case 's':
            /* parse a copy: strtok_r would modify argv, which is what
             * /proc/<pid>/cmdline shows and PyRPL compares */
            signal_list = strdup(optarg);
            break;
        case 'm':
            simulation_file = optarg;
            break;
        default:
            fprintf(stderr,
                    "usage: %s [-p PORT] [-i PROFILE] [-s NAME=INDEX,...] [-m FILE]\n",
                    argv[0]);
            return opt == 'h' ? 0 : 2;
        }
    }
    if (port <= 0 || port > 65535) {
        fprintf(stderr, "invalid port %d\n", port);
        return 2;
    }
    if (signal_list != NULL) {
        if (parse_signal_list(signal_list) != 0) {
            fprintf(stderr, "invalid signal list, expected NAME=INDEX,...\n");
            return 2;
        }
    } else {
        n_signals = sizeof(default_signals) / sizeof(default_signals[0]);
        memcpy(signals, default_signals, sizeof(default_signals));
    }

    map_memory(simulation_file);

    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) {
        perror("socket");
        return 1;
    }
    setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(enable));
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);
    if (bind(sockfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }
    if (listen(sockfd, 8) < 0) {
        perror("listen");
        return 1;
    }
    signal(SIGCHLD, SIG_IGN); /* children are reaped automatically */
    signal(SIGPIPE, SIG_IGN);
    printf("pyrpl_scpi_server %s listening on port %d (profile %s, %d signals)\n",
           SERVER_VERSION, port, profile_id, n_signals);
    fflush(stdout);

    for (;;) {
        int fd = accept(sockfd, NULL, NULL);
        if (fd < 0) {
            if (errno == EINTR)
                continue;
            perror("accept");
            continue;
        }
        pid_t pid = fork();
        if (pid == 0) {
            close(sockfd);
            setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &enable, sizeof(enable));
            serve(fd);
            _exit(0);
        }
        if (pid < 0)
            perror("fork");
        close(fd);
    }
}
