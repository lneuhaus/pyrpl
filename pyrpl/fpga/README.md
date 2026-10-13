# Directory structure

|  path             | contents
|-------------------|-------------------------------------------------------------
| `fpga/Makefile`   | main Makefile, used to run FPGA related tools
| `fpga/*.tcl`      | TCL scripts to be run inside FPGA tools
| `fpga/ip/`        | third party IP, for now Zynq block diagrams
| `fpga/rtl/`       | Verilog (SystemVerilog) "Register-Transfer Level"
| `fpga/rtl_legacy/` | frozen source overrides used only by the legacy profile
| `fpga/rtl_profiles/` | minimal source overrides for specialized profiles
| `fpga/profiles/`  | synthesis settings and runtime-manifest templates
| `fpga/bitstreams/`| published, tested images grouped by runtime profile
| `fpga/sdc/`       | "Synopsys Design Constraints" contains Xilinx design constraints
| `fpga/sim/`       | simulation scripts
| `fpga/tbn/`       | Verilog (SystemVerilog) "test bench"
|                   |
| `fpga/build/<profile>/sdk/` | generated platform files for one profile
| `fpga/build/<profile>/` | ignored bitstream, reports, checkpoints, and build log

# Build process

> [!NOTE]
> First consider using the fpga build scripts in [RedPitaya/Makefile.x86](https://github.com/RedPitaya/RedPitaya/blob/master/Makefile.x86) that supports all the different RedPitaya board types using the [RedPitaya-FPGA](https://github.com/RedPitaya/RedPitaya-FPGA) hdl code rather than this fpga build.

Assuming you have a specific requirement to use this hdl code rather than the RedPitaya-FPGA hdl code in your design make sure that you update the part number and constraints sdc file specific to your target board in `fpga/red_pitaya_vivado.tcl`
```
set part xc7z010clg400-1
read_xdc                          $path_sdc/red_pitaya.xdc
```

Xilinx Vitis / Vivado 2023.2 is required. If installed at the default location, then the next command will properly configure system variables:
```bash
. /opt/Xilinx/Vivado/2023.2/settings64.sh
```

If you need to update to a more recent version of Vitis / Vivado then update the Vivado version in `fpga/ip/system_bd.tcl` - be prepared to fix up various build tcl scripts to replace depreciated tcl commands
```
set scripts_vivado_version 2023.2
```

The default mode for building the FPGA is to run a TCL script inside Vivado. Non project mode is used, to avoid the generation of project files, which are too many and difficult to handle. This allows us to only place source files and scripts under version control.

On Windows, select the hardware source profile explicitly:

```bat
cd pyrpl\fpga
make_bin.bat default
make_bin.bat legacy
make_bin.bat no_iir
make_bin.bat iir32
make_bin.bat pid_derivative
make_bin.bat arithmetic
make_bin.bat cordic
make_bin.bat cordic_vco
```

Calling `make_bin.bat` without an argument builds `default`. Results are kept
in `build\<profile>`. A build never overwrites the tested files under
`bitstreams`.

On Windows, `make_bin.bat` temporarily maps the repository root to an unused
drive letter between `R:` and `Z:`, then builds from the short but non-root path
`<drive>:\pyrpl\fpga`. This avoids Vivado 2024.2 path failures in both its
installed `common.tcl` and generated `.Xil/realtime` files; Vivado cannot
reliably create the latter directly at a substituted drive root. The drive is
removed when the nested build exits. Synthesis also intentionally uses one
thread because the parallel helper can lose access to its installed Tcl files.
The original thread count is restored immediately after synthesis, so
placement, physical optimization, and routing retain normal parallelism.

Implementation directives are selected by each profile. The `no_iir` profile
runs two post-route physical-optimization passes; `pid_derivative` also runs
two because of its extra DSP paths, and `arithmetic` runs two for its
pipelined divider. `default` and `iir32` run one, while the
compatibility-only `legacy` profile skips that expensive step.

| Build profile | IIR | PID filters | DSP modules |
|---------------|-----|-------------|-------------|
| `default` | 24-bit, 8-stage | none | 3 PID, 3 IQ |
| `pid_derivative` | none | 4 input stages plus band-limited D | 3 PID, 3 IQ |
| `arithmetic` | none | band-limited D, no input filters | 3 PID, 3 IQ, two-input arithmetic |
| `cordic` | none | none | 3 PID, 3 IQ, standalone CORDIC plus CORDICs in IQ0/IQ1 |
| `cordic_vco` | none | none | same three CORDICs, with VCO control on all IQs |
| `legacy` | original 32-bit, 14-stage | 4 input stages | 3 PID, 3 IQ |
| `no_iir` | none | 4 input stages | 3 PID, 3 IQ |
| `iir32` | pipelined 32-bit, 14-stage | none | 2 PID, 3 IQ |

`pid_derivative` combines the no-IIR topology with the current PID RTL. Each of
its three PIDs has the original four-stage input prefilter and one derivative
multiplier. Its `derivative_filter_ratio` setting is constrained to 3 through
10, corresponding to a roll-off angular frequency between `3 / tau_d` and
`10 / tau_d`. The FPGA uses the nearest available shift-filter cutoff and
Python models that discrete filter exactly. A register before each PID input
filter breaks the otherwise long four-stage bypass path and adds one 8 ns cycle
to the PID latency; the profile manifest includes this delay in the Python
transfer-function model.

The `arithmetic` profile uses slot 4 for a two-input module and enables the
band-limited derivative on all three PIDs without restoring their input
prefilters. Its modes are `polynomial` (`a*input**p + b*input_b**q`, with each
exponent selectable as 1 or 2), `product` (`a*input*input_b`), and `ratio`
(`a*input/input_b`). Inputs use normalized signed values and coefficients are
signed Q8.16. Polynomial/product results take four FPGA cycles; the fully
pipelined divider accepts a new sample every cycle and has sixteen cycles of
latency. `denominator_min` protects division near zero, saturating nonzero
results and setting `denominator_too_small`. Each input can be delayed by zero
through seven cycles, which is useful when combining a direct signal with a
PID-processed copy.

The normalized cutoff calculation performs a numerical search. It is decorated
with `@lru_cache(maxsize=None)`, so each of the 24 possible shift values is
calculated only once per Python process. `maxsize=None` disables cache eviction;
the cache is nevertheless bounded in practice by those 24 shift values. This
is only a Python performance optimization and does not cache FPGA state.

The specialized profiles retain the established FPGA address map. `no_iir`
and `pid_derivative` leave address slot 4 inactive, `cordic` uses slot 4 for
its standalone phase output, `arithmetic` uses it for its two-input arithmetic
output, and `iir32` leaves PID slot 2 inactive. IQ2 is
retained because it is used by the network analyzer. In the `cordic` profile,
`cordic.input` selects I and `cordic.input_q` independently selects Q. Its
output is `atan2(Q, I)` in turns, with 12 fractional phase bits, a two-bit
turn counter, and ten cycles of latency. Exact zero input magnitude holds the
last valid phase. Convert a sampled output with
`cordic.to_radians(value)` or `cordic.to_degrees(value)`.

Set `cordic.input_pair` to `iq0`, `iq1`, or `iq2` to consume that IQ's
filtered I and Q quadratures directly. This local connection does not consume
additional entries in the global DSP routing table and does not depend on the
IQ module's `output_signal` setting. The default value, `independent`, uses
`cordic.input` and `cordic.input_q` as described above.

IQ0 and IQ1 additionally contain their own CORDICs in place of their legacy
PFD datapaths. Select `iq.output_signal = "cordic"` to route the phase through
the DSP fabric, or read `iq.cordic_phase` directly. The value is in turns;
`iq.cordic_phase_radians` and `iq.cordic_phase_degrees` provide converted
readbacks. IQ2 retains the legacy PFD and its `iq2_2` quadrature output for the
network and spectrum analyzers. The standalone CORDIC remains available for
the requested independently routed `in1`/`in2` use case.

All three IQ modulators in `cordic` and `cordic_vco` register their second
multiplier products before the final addition. This adds one 8 ns cycle to the
remodulated/direct IQ output; the profile timing metadata includes that cycle.
The demodulated quadrature and integrated-CORDIC paths are unchanged.
The same profiles set the Network Analyzer correction delay to four cycles so
its automatically corrected response includes this additional output cycle.

`cordic_vco` extends that topology with a VCO input on every IQ. Set
`iq.vco_input` to any DSP signal, `iq.vco_range` to the frequency deviation
in hertz produced by a +1 V input, and then enable `iq.vco_on`. Negative
`vco_range` values invert the tuning direction. The routed input, multiplier,
and effective phase increment are registered in three consecutive clock
cycles to protect the 125 MHz timing path. The CORDIC output can be selected
directly as the VCO input, making phase-feedback loops possible without CPU
intervention. The VCO register-map signature is `0x56434F01` (`VCO`, revision
1).

All profiles expose the same IQ oscillator trigger controls. The default
`trigger_source="immediately"` retains software synchronization. With
`trigger_source="external"`, `trigger_pin` selects `P0` through `P7` or `N0`
through `N7`; a rising edge starts the oscillator, which then runs until it is
rearmed. Re-select either trigger setting or call `iq.arm_trigger()` to rearm
one IQ. The selected expansion pin must be configured as an input through the
Housekeeping module (the FPGA reset default). Expansion inputs pass through a
shared two-flop synchronizer before reaching the three IQ modules.

The `default` profile also exposes external sample-and-hold control for each PID.
Set `pause_source="external"` and choose `pause_pin` from `P0` through `P7`
or `N0` through `N7`. The PID runs while the synchronized pin is high. While
it is low, the PID controller datapath, integrator, derivative state, and
complete output are held without being reset; operation resumes from that
state when the pin returns high. Profile-specific PID input prefilters keep
tracking the input while the controller is held. `pause_source="off"`
preserves the normal behavior, including
the independent `paused` and `pause_gains` software controls. Configure the
selected expansion pin as an HK input for normal external use.

The CORDIC exposes the read-only ABI signature `0x434F5202`: the upper three
bytes spell `COR` and the low byte is register-map revision 2. PyRPL checks
this value after loading the profile so incompatible CORDIC logic is detected
before its registers are used.

Run the standalone RTL testbench on Windows with:

```bat
cd pyrpl\fpga
run_cordic_tb.bat
```

The script compiles the CORDIC and its SystemVerilog testbench with Vivado
2024.2, elaborates `red_pitaya_cordic_block_tb`, and runs it in batch mode.
Generated simulator files remain under `build\cordic_sim`; success is reported
as `CORDIC_TEST_PASS` followed by `CORDIC RTL simulation passed.`

The arithmetic datapath has a corresponding standalone test:

```bat
cd pyrpl\fpga
run_arithmetic_tb.bat
```

It checks polynomial, product, ratio, and protected divide-by-zero behavior.
Success is reported as `ARITHMETIC_TEST_PASS`.

The IQ trigger state machine has its own standalone RTL test:

```bat
cd pyrpl\fpga
run_iq_trigger_tb.bat
```

It checks immediate mode, first and repeated rising-edge starts, per-IQ
rearming, falling-edge behavior, and global IQ synchronization rearming.

To load an unpublished build for hardware testing while retaining the correct
Python contract, select its profile and override only the binary path:

```python
p = Pyrpl(
    hostname=HOSTNAME,
    fpga_profile="legacy",
    filename="fpga/build/legacy/red_pitaya.bin",
    reloadfpga=True,
)
```

The equivalent direct Vivado commands are:

```text
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs default build/default
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs legacy build/legacy
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs no_iir build/no_iir
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs iir32 build/iir32
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs pid_derivative build/pid_derivative
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs arithmetic build/arithmetic
vivado -nolog -nojournal -mode batch -source red_pitaya_vivado.tcl -tclargs cordic build/cordic
```

After building a new profile, stage it for runtime hardware tests. This copies
the binary and shared device-tree overlay, and generates their SHA-256 hashes:

```text
python publish_fpga_profile.py no_iir
python publish_fpga_profile.py iir32
python publish_fpga_profile.py pid_derivative
python publish_fpga_profile.py arithmetic
```

The staged directory appears under `bitstreams/<profile>` and makes the profile
available through `fpga_profile`. Hardware-test it before committing those
generated runtime artifacts. Use `--force` only when deliberately replacing an
already staged profile.

The next scripts perform various tasks for the xc7z010clg400-1 part:

| TCL script                      | action
|---------------------------------|---------------------------------------------
| `red_pitaya_vivado_project.tcl` | creates a Vivado project for graphical editing
| `red_pitaya_vivado.tcl`         | creates the bitstream and reports

To generate a redpitaya.bin file for the xc7z010clg400-1 part, redpitaya.dtbo device tree, reports, run these two commands:
```bash
source /opt/Xilinx/Vivado/2023.2/settings64.sh
make
```

# Device tree
> [!NOTE]
> You do not need to build the .bin file or the device tree to use Pyrpl.  They are provided pre-built.

Device tree is used by Linux to describe features and address space of memory mapped hardware attached to the CPU.  It can (optionally) be installed onto the RedPitaya board with the redpitaya.bin file generated (specify the full path to the files).  In this example assuming the generated .bin and .dtbo files are in the same directory as the python code:
```
from pyrpl import Pyrpl
p = Pyrpl(hostname=HOSTNAME,
    reloadfpga = True, filename = 'red_pitaya.bin',
    dtbo_filename = 'red_pitaya.dtbo'
    )
```
The pre-built .bin file and device tree are used if these files are not specified.  You can avoid reloading the fpga files each time you run your script by setting reloadfpga = False.  If you use the config, configuration file attribute, then the attributes that are used are stored in a .yaml file in the PYRPL_USER_DIR so next time you start your application the settings including reloadfpga will be restored.

## FPGA profiles

The `fpga_profile` setting selects a published, tested bitstream together with
its Python hardware contract. The source tree contains eight build profiles,
but `available_fpga_profiles()` only lists profiles that have been staged under
`bitstreams`.

```python
from pyrpl import Pyrpl
from pyrpl import available_fpga_profiles

print(available_fpga_profiles())  # ('default', 'legacy')

# The timing-optimized profile is the default.
p = Pyrpl(hostname=HOSTNAME, fpga_profile="default")

# Select this only when the wider IIR or PID prefilters are required.
p = Pyrpl(hostname=HOSTNAME, fpga_profile="legacy")
```

The same selection is available on the command line:

```text
python -m pyrpl my_config fpga_profile=legacy
```

## Testing FPGA profiles

FPGA profile selection and test filtering are separate operations:

1. `REDPITAYA_FPGA_PROFILE` selects the packaged profile requested for the
   pytest session.
2. The session-scoped hardware fixture currently creates PyRPL with
   `reloadfpga=True`, so it loads that profile at session startup rather than
   merely inspecting the image that happened to be loaded previously.
3. PyRPL validates the loaded register-map constants against the selected
   manifest.
4. The autouse pytest fixture examines `requires_fpga` markers. A test such as
   `@pytest.mark.requires_fpga("pid_derivative")` is skipped when the selected
   manifest does not advertise that capability. Unmarked tests still run.

The profile is therefore selected first; pytest does not discover a profile
from arbitrary FPGA logic and then select tests from that. One pytest process
uses one profile because the hardware fixture is session-scoped.

Select a profile in PowerShell with:

```powershell
$env:REDPITAYA_HOSTNAME = "169.254.101.38"
$env:REDPITAYA_FPGA_PROFILE = "legacy"
pytest pyrpl/test/test_hardware_modules
```

The equivalent `cmd.exe` syntax is:

```bat
set REDPITAYA_HOSTNAME=169.254.101.38
set REDPITAYA_FPGA_PROFILE=legacy
pytest pyrpl\test\test_hardware_modules
```

Do not put spaces around `=` in `cmd.exe`; doing so changes the environment
variable name. To run only derivative-specific tests:

```powershell
$env:REDPITAYA_FPGA_PROFILE = "pid_derivative"
pytest pyrpl/test/test_hardware_modules/test_pid_na_iq.py -k pid_derivative
```

An unpublished build is not selectable until it has a runtime manifest. After
building it, stage it before hardware testing:

```text
cd pyrpl/fpga
python publish_fpga_profile.py pid_derivative
python publish_fpga_profile.py arithmetic
python publish_fpga_profile.py cordic
python publish_fpga_profile.py cordic_vco
```

Publishing copies `build/pid_derivative/red_pitaya.bin` into the corresponding
`bitstreams` directory and creates checksum-locked runtime metadata. Staging a
development build makes it selectable; it does not imply that the generated
artifacts are ready to commit.

Run several profiles as separate pytest sessions so each image is loaded and
validated independently:

```powershell
foreach ($profile in @("default", "legacy", "no_iir", "iir32", "pid_derivative", "arithmetic", "cordic", "cordic_vco")) {
    $env:REDPITAYA_FPGA_PROFILE = $profile
    pytest pyrpl/test/test_hardware_modules
}
```

Tests marked with `requires_fpga` are skipped when the selected profile does
not provide the requested capability. Frequency-response artifacts use the
profile ID as their label unless `PYRPL_BITSTREAM_LABEL` is set explicitly.
`PYRPL_BITSTREAM_LABEL` affects only the output directory name and never
selects or loads a bitstream.

The setting is persisted under the `redpitaya` configuration branch:

```yaml
redpitaya:
  fpga_profile: legacy
  reloadfpga: auto
```

With `reloadfpga: auto`, changing profile reloads the corresponding packaged
image. Explicit `filename` and `dtbo_filename` arguments remain available for
development images, but their register map must match the selected profile.
At startup PyRPL checks the IIR constants and PID filter count and rejects a
mismatched image.

# Signal mapping

## XADC inputs

XADC input data can be accessed through the Linux IIO (Industrial IO) driver interface.

| E2 con | schematic | ZYNQ p/n | XADC in | IIO filename     | measurement target | range |
|--------|-----------|----------|---------|------------------|--------------------|-------|
| AI0    | AIF[PN]0  | B19/A20  | AD8     | in_voltage11_raw | general purpose    | 7.01V |
| AI1    | AIF[PN]1  | C20/B20  | AD0     | in_voltage9_raw  | general purpose    | 7.01V |
| AI2    | AIF[PN]2  | E17/D18  | AD1     | in_voltage10_raw | general purpose    | 7.01V |
| AI3    | AIF[PN]3  | E18/E19  | AD9     | in_voltage12_raw | general purpose    | 7.01V |
|        | AIF[PN]4  | K9 /L10  | AD      | in_voltage0_raw  | 5V power supply    | 12.2V |

### Input range

The default mounting intends for unipolar XADC inputs, which allow for observing only positive signals with a saturation range of *0V ~ 1V*. There are additional voltage dividers use to extend this range up to the power supply voltage. It is possible to configure XADC inputs into a bipolar mode with a range of *-0.5V ~ +0.5V*, but it requires removing R273 and providing a *0.5V ~ 1V* common voltage on the E2 connector.

**NOTE:** Unfortunately there is a design error, where the XADC input range in unipolar mode was thought to be *0V ~ 0.5V*. Consequently the voltage dividers were miss designed for a range of double the supply voltage.

#### 5V power supply

```
                         -------------------0  Vout
           ------------  |  ------------
 Vin  0----| 56.0kOHM |-----| 4.99kOHM |----0  GND
           ------------     ------------
```
Ratio: 4.99/(56.0+4.99)=0.0818
Range: 1V / ratio = 12.2V

#### General purpose inputs

```
                         -------------------0  Vout
           ------------  |  ------------
 Vin  0----| 30.0kOHM |-----| 4.99kOHM |----0  GND
           ------------     ------------
```
Ratio: 4.99/(30.0+4.99)=0.143
Range: 1V / ratio = 7.01


## GPIO LEDs

| LED     | color  | SW driver       | dedicated meaning
|---------|--------|-----------------|----------------------------------
| `[7:0]` | yellow | RP API          | user defined
| `  [8]` | yellow | kernel `MIO[0]` | CPU heartbeat (user defined)
| `  [9]` | reg    | kernel `MIO[7]` | SD card access (user defined)
| ` [10]` | green  | none            | "Power Good" status
| ` [11]` | blue   | none            | FPGA programming "DONE"

For now only LED8 and LED9 are accessible using a kernel driver. LED [7:0] are not driven by a kernel driver, since the Linux GPIO/LED subsystem does not allow access to multiple pins simultaneously.

### Linux access to GPIO

This document is used as reference: http://www.wiki.xilinx.com/Linux+GPIO+Driver

The base value of `MIO` GPIOs was determined to be `906`.
```bash
redpitaya> find /sys/class/gpio/ -name gpiochip*
/sys/class/gpio/gpiochip906
```

GPIOs are accessible at base value + MIO index:
```bash
echo 906 > /sys/class/gpio/export
echo 913 > /sys/class/gpio/export
```

### Linux access to LED

This document is used as reference: http://www.wiki.xilinx.com/Linux+GPIO+Driver

By providing GPIO/LED details in the device tree, it is possible to access LEDs using a dedicated kernel interface.
NOTE: only LED 8 and LED 9 support this interface for now.

To show CPU load on LED 9 use:
```bash
echo heartbeat > /sys/class/leds/led9/trigger
```
To switch LED 8 on use:
```bash
echo 1 > /sys/class/leds/led8/brightness
```
