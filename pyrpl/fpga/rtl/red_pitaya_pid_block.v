/**
 * $Id: red_pitaya_pid_block.v 961 2014-01-21 11:40:39Z matej.oblak $
 *
 * @brief Red Pitaya PID controller.
 *
 * @Author Matej Oblak
 *
 * (c) Red Pitaya  http://www.redpitaya.com
 *
 * This part of code is written in Verilog hardware description language (HDL).
 * Please visit http://en.wikipedia.org/wiki/Verilog
 * for more details on the language used herein.
 */
/*
###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
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
 * GENERAL DESCRIPTION:
 *
 * Proportional-integral-derivative (PID) controller.
 *
 *
 *        /---\         /---\      /-----------\
 *   IN --| - |----+--> | P | ---> | SUM & SAT | ---> OUT
 *        \---/    |    \---/      \-----------/
 *          ^      |                   ^  ^
 *          |      |    /---\          |  |
 *   set ----      +--> | I | ---------   |
 *   point         |    \---/             |
 *                 |                      |
 *                 |    /---\             |
 *                 ---> | D | ------------
 *                      \---/
 *
 *
 * Proportional-integral-derivative (PID) controller is made from three parts. 
 *
 * Error which is difference between set point and input signal is driven into
 * propotional, integral and derivative part. Each calculates its own value which
 * is then summed and saturated before given to output.
 *
 * Integral part has also separate input to reset integrator value to 0.
 * 
 */

module red_pitaya_pid_block #(
   //parameters for gain control (binary points and total bitwidth)
   parameter     PSR = 12         ,
   parameter     ISR = 32         ,//official redpitaya: 18
   parameter     DSR = 10         ,
   parameter     GAINBITS = 24    ,
   parameter     DERIVATIVE = 0   , //disables differential gain if 0
   parameter     DERIVATIVE_FILTER_SHIFT = 4,
   parameter     INPUT_REGISTER = 0,
   
   //parameters for input pre-filter
   parameter     FILTERSTAGES = 0 ,
   parameter     FILTERSHIFTBITS = 5,
   parameter     FILTERMINBW = 10,
   
   //enable arbitrary output saturation or not
   parameter     ARBITRARY_SATURATION = 1
)
(
   // data
   input                 clk_i           ,  // clock
   input                 rstn_i          ,  // reset - active low
   input                 sync_i          ,  // synchronization input, active high
   input      [ 16-1: 0] external_enable_i, // synchronized expansion inputs
   input signed     [ 14-1: 0] dat_i           ,  // input data
   output signed    [ 14-1: 0] dat_o           ,  // output data
   input signed     [ 14-1: 0] diff_dat_i      ,  // input data for differential mode
   output signed    [ 14-1: 0] diff_dat_o      ,  // input data for differential mode

   // communication with PS
   input      [ 16-1: 0] addr,
   input                 wen,
   input                 ren,
   output reg   		 ack,
   output reg [ 32-1: 0] rdata,
   input      [ 32-1: 0] wdata
);

reg signed [ 14-1: 0] set_sp;   // set point
reg signed [ 16-1: 0] set_ival;   // integral value to set
reg            ival_write;
reg [  3-1: 0] pause_pid_on_sync;  // register to specify which gains (P, I, and/or D) are paused during active sync signal
reg enable_differential_mode;  // register to specify which gains (P, I, and/or D) are paused during active sync signal
reg external_pause_enabled;
reg [4-1:0] external_pause_pin;
wire external_run = !external_pause_enabled || external_enable_i[external_pause_pin];
wire pause_i_on_sync;
assign pause_i = pause_pid_on_sync[0] & !sync_i;
wire pause_p_on_sync;
assign pause_p = pause_pid_on_sync[1] & !sync_i;
wire pause_d_on_sync;
assign pause_d = pause_pid_on_sync[2] & !sync_i;
reg [ GAINBITS-1: 0] set_kp;   // Kp
reg [ GAINBITS-1: 0] set_ki;   // Ki
reg [ GAINBITS-1: 0] set_kd;   // Kd
reg [ 32-1: 0] set_filter;
reg [  6-1: 0] set_derivative_filter_shift;
wire signed [16-1:0] int_shr;   // integral readback; declared before bus use
// limits if arbitrary saturation is enabled
reg signed [ 14-1:0] out_max;
reg signed [ 14-1:0] out_min;

//  System bus connection
always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      set_sp <= 14'd0;
      set_ival <= 14'd0;
      pause_pid_on_sync <= {3{1'b1}};  // by default, all gains are paused on sync signal
      enable_differential_mode <= 1'b0; // by default no differential mode
      external_pause_enabled <= 1'b0;
      external_pause_pin <= 4'd0;
      set_kp <= {GAINBITS{1'b0}};
      set_ki <= {GAINBITS{1'b0}};
      set_kd <= {GAINBITS{1'b0}};
      set_filter <= 32'd0;
      set_derivative_filter_shift <= DERIVATIVE_FILTER_SHIFT;
      ival_write <= 1'b0;
      out_min <= {1'b1,{14-1{1'b0}}};
      out_max <= {1'b0,{14-1{1'b1}}};
   end
   else begin
      if (wen) begin
         if (addr==16'h100)   set_ival <= wdata[16-1:0];
         if (addr==16'h104)   set_sp  <= wdata[14-1:0];
         if (addr==16'h108)   set_kp  <= wdata[GAINBITS-1:0];
         if (addr==16'h10C)   set_ki  <= wdata[GAINBITS-1:0];
         if (addr==16'h110)   set_kd  <= wdata[GAINBITS-1:0];
         if ((DERIVATIVE != 0) && (addr==16'h114))
            set_derivative_filter_shift <= wdata[6-1:0];
         if ((FILTERSTAGES > 0) && (addr==16'h120))
            set_filter <= wdata;
         if (addr==16'h124)   out_min  <= wdata;
         if (addr==16'h128)   out_max  <= wdata;
         if (addr==16'h12C)   {enable_differential_mode,pause_pid_on_sync} <= wdata[4-1:0];
         if (addr==16'h130)   external_pause_enabled <= wdata[0];
         if (addr==16'h134)   external_pause_pin <= wdata[3:0];
      end
      if (addr==16'h100 && wen)
         ival_write <= 1'b1;
      else
         ival_write <= 1'b0;

	  casez (addr)
	     16'h100 : begin ack <= wen|ren; rdata <= int_shr; end
	     16'h104 : begin ack <= wen|ren; rdata <= {{32-14{1'b0}},set_sp}; end
	     16'h108 : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},set_kp}; end
	     16'h10C : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},set_ki}; end
	     16'h110 : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},set_kd}; end
	     16'h114 : begin ack <= wen|ren; rdata <= (DERIVATIVE != 0) ?
                    {{32-6{1'b0}},set_derivative_filter_shift} : DERIVATIVE_FILTER_SHIFT; end
	     16'h120 : begin ack <= wen|ren; rdata <= (FILTERSTAGES > 0) ? set_filter : 32'd0; end
	     16'h124 : begin ack <= wen|ren; rdata <= {{32-14{1'b0}},out_min}; end
	     16'h128 : begin ack <= wen|ren; rdata <= {{32-14{1'b0}},out_max}; end
	     16'h12C : begin ack <= wen|ren; rdata <= {{32-4{1'b0}},enable_differential_mode,pause_pid_on_sync}; end
	     16'h130 : begin ack <= wen|ren; rdata <= {31'd0,external_pause_enabled}; end
	     16'h134 : begin ack <= wen|ren; rdata <= {28'd0,external_pause_pin}; end
	     16'h200 : begin ack <= wen|ren; rdata <= PSR; end
	     16'h204 : begin ack <= wen|ren; rdata <= ISR; end
	     16'h208 : begin ack <= wen|ren; rdata <= DSR; end
	     16'h20C : begin ack <= wen|ren; rdata <= GAINBITS; end
	     16'h210 : begin ack <= wen|ren; rdata <= DERIVATIVE; end
	     16'h214 : begin ack <= wen|ren; rdata <= DERIVATIVE_FILTER_SHIFT; end
	     16'h220 : begin ack <= wen|ren; rdata <= FILTERSTAGES; end
	     16'h224 : begin ack <= wen|ren; rdata <= FILTERSHIFTBITS; end
	     16'h228 : begin ack <= wen|ren; rdata <= FILTERMINBW; end
	     
	     default: begin ack <= wen|ren;  rdata <=  32'h0; end 
	  endcase	     
   end
end


wire signed [14-1:0] dat_i_registered;
wire signed [14-1:0] dat_i_filtered;

// Break the timing path from the DSP input selector and output saturation
// logic into the cascaded PID input filters.  This is enabled only by the
// full-featured derivative profile and adds one sample of fixed PID latency.
generate
   if (INPUT_REGISTER > 0) begin: pid_input_register
      reg signed [14-1:0] dat_i_reg;
      always @(posedge clk_i) begin
         if (rstn_i == 1'b0)
            dat_i_reg <= 14'd0;
         else if (external_run)
            dat_i_reg <= dat_i;
      end
      assign dat_i_registered = dat_i_reg;
   end else begin: no_pid_input_register
      assign dat_i_registered = dat_i;
   end
endgenerate

generate
   if (FILTERSTAGES > 0) begin: pid_input_filter
      red_pitaya_filter_block #(
         .STAGES(FILTERSTAGES),
         .SHIFTBITS(FILTERSHIFTBITS),
         .SIGNALBITS(14),
         .MINBW(FILTERMINBW)
      ) inputfilter (
         .clk_i(clk_i),
         .rstn_i(rstn_i),
         .set_filter(set_filter),
         .dat_i(dat_i_registered),
         .dat_o(dat_i_filtered)
      );
   end else begin: no_pid_input_filter
      assign dat_i_filtered = dat_i_registered;
   end
endgenerate

//---------------------------------------------------------------------------------
//  Set point error calculation - 1 cycle delay

reg signed [ 15-1: 0] error        ;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      error <= 15'h0 ;
   end
   else if (external_run) begin
      if (enable_differential_mode == 1'b1)
         error <= $signed(dat_i_filtered) - $signed(diff_dat_i) ;
      else
         error <= $signed(dat_i_filtered) - $signed(set_sp) ;
   end
end

// send filtered signal to other pid module for differential processing
assign diff_dat_o = dat_i_filtered;

//---------------------------------------------------------------------------------
//  Proportional part - 1 cycle delay

reg signed  [15+GAINBITS-PSR-1: 0] kp_reg        ;
wire signed [15+GAINBITS-1: 0] kp_mult       ;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      kp_reg  <= {15+GAINBITS-PSR{1'b0}};
   end
   else if (external_run) begin
      kp_reg <= kp_mult[15+GAINBITS-1:PSR] ;
   end
end

assign kp_mult = (pause_p==1'b1) ? $signed({15+GAINBITS{1'b0}}) : $signed(error) * $signed(set_kp);

//---------------------------------------------------------------------------------
// Integrator - 2 cycles delay (but treat similar to proportional since it
// will become negligible at high frequencies where delay is important)

//formerly
//-localparam IBW = 64; //integrator bit-width. Over-represent the integral sum to record longterm drifts
//-reg   [15+GAINBITS-1: 0] ki_mult  ;
localparam IBW = ISR+16; //integrator bit-width. Over-represent the integral sum to record longterm drifts (overrepresented by 2 bits)
reg signed  [16+GAINBITS-1: 0] ki_mult ;
wire signed [IBW  : 0] int_sum       ;
reg signed  [IBW-1: 0] int_reg       ;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      ki_mult  <= {15+GAINBITS{1'b0}};
      int_reg  <= {IBW{1'b0}};
   end
   else begin
      if (ival_write)
         int_reg <= { {IBW-16-ISR{set_ival[16-1]}},set_ival[16-1:0],{ISR{1'b0}}};
      else if (external_run) begin
         ki_mult <= $signed(error) * $signed(set_ki) ;
         if (int_sum[IBW+1-1:IBW+1-2] == 2'b01) //normal positive saturation
            int_reg <= {1'b0,{IBW-1{1'b1}}};
         else if (int_sum[IBW+1-1:IBW+1-2] == 2'b10) // negative saturation
            int_reg <= {1'b1,{IBW-1{1'b0}}};
         else
            int_reg <= int_sum[IBW-1:0]; // use sum as it is
      end
   end
end

assign int_sum = (pause_i==1'b1) ? $signed(int_reg) : $signed(ki_mult) + $signed(int_reg);
assign int_shr = $signed(int_reg[IBW-1:ISR]) ;

//---------------------------------------------------------------------------------
// Band-limited derivative. One DSP computes Kd * (error[n]-error[n-1]).
// A shift-based pipelined low-pass then limits ADC and quantization noise.
// Its transfer function is modeled exactly in Pid._pid_transfer_function.

localparam DERIVATIVE_BITS = 16+GAINBITS-DSR;
localparam DERIVATIVE_FILTER_MAX_SHIFT = 24;
wire signed [DERIVATIVE_BITS-1:0] derivative_term;

generate
   if (DERIVATIVE == 1) begin: derivative
      reg signed [15-1:0] error_previous;
      wire signed [16-1:0] error_delta;
      reg signed [16+GAINBITS-1:0] kd_product;
      wire signed [DERIVATIVE_BITS-1:0] derivative_target;
      reg signed [DERIVATIVE_BITS:0] filter_delta;
      reg signed [DERIVATIVE_BITS+DERIVATIVE_FILTER_MAX_SHIFT-1:0] filter_accumulator;
      wire signed [DERIVATIVE_BITS-1:0] filter_output;
      wire [6-1:0] filter_shift;
      wire signed [DERIVATIVE_BITS+DERIVATIVE_FILTER_MAX_SHIFT-1:0] filter_delta_extended;
      wire signed [DERIVATIVE_BITS+DERIVATIVE_FILTER_MAX_SHIFT-1:0] shifted_filter_delta;

      assign error_delta = $signed({error[14], error})
                         - $signed({error_previous[14], error_previous});
      assign derivative_target = kd_product[16+GAINBITS-1:DSR];
      assign filter_output = filter_accumulator[
         DERIVATIVE_BITS+DERIVATIVE_FILTER_MAX_SHIFT-1:DERIVATIVE_FILTER_MAX_SHIFT];
      assign filter_shift = (set_derivative_filter_shift < 1) ? 1 :
                            (set_derivative_filter_shift > DERIVATIVE_FILTER_MAX_SHIFT) ?
                            DERIVATIVE_FILTER_MAX_SHIFT : set_derivative_filter_shift;
      assign filter_delta_extended = {{DERIVATIVE_FILTER_MAX_SHIFT-1{filter_delta[DERIVATIVE_BITS]}},
                                      filter_delta};
      assign shifted_filter_delta = $signed(filter_delta_extended)
                                  <<< (DERIVATIVE_FILTER_MAX_SHIFT-filter_shift);
      assign derivative_term = pause_d ? {DERIVATIVE_BITS{1'b0}} : filter_output;

      always @(posedge clk_i) begin
         if (rstn_i == 1'b0) begin
            error_previous <= 15'd0;
            kd_product <= {(16+GAINBITS){1'b0}};
            filter_delta <= {(DERIVATIVE_BITS+1){1'b0}};
            filter_accumulator <= {(DERIVATIVE_BITS+DERIVATIVE_FILTER_MAX_SHIFT){1'b0}};
         end else if (external_run) begin
            error_previous <= error;
            if (pause_d) begin
               kd_product <= {(16+GAINBITS){1'b0}};
               filter_delta <= {(DERIVATIVE_BITS+1){1'b0}};
               filter_accumulator <= {(DERIVATIVE_BITS+DERIVATIVE_FILTER_MAX_SHIFT){1'b0}};
            end else begin
               kd_product <= $signed(error_delta) * $signed(set_kd);
               filter_delta <= $signed({derivative_target[DERIVATIVE_BITS-1], derivative_target})
                             - $signed({filter_output[DERIVATIVE_BITS-1], filter_output});
               filter_accumulator <= $signed(filter_accumulator) + $signed(shifted_filter_delta);
            end
         end
      end
   end else begin: no_derivative
      assign derivative_term = {DERIVATIVE_BITS{1'b0}};
   end
endgenerate

//---------------------------------------------------------------------------------
//  Sum together - saturate output - 1 cycle delay


//maximum possible bitwidth for pid_sum
// = max( 15+GAINBITS(24)-PSR(12) = 27, // from kp_reg
//        IBW(48)-ISR(32) = 16,         // from int_shr
//        16+GAINBITS-DSR = 30)                 // from derivative_term
localparam MAXBW = (DERIVATIVE == 1) ? DERIVATIVE_BITS : 28;

wire signed [   MAXBW-1: 0] pid_sum;
reg signed  [   14-1: 0] pid_out;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      pid_out    <= 14'b0;
   end
   else if (external_run) begin
      if ({pid_sum[MAXBW-1],|pid_sum[MAXBW-2:13]} == 2'b01) //positive overflow
         pid_out <= 14'h1FFF;
      else if ({pid_sum[MAXBW-1],&pid_sum[MAXBW-2:13]} == 2'b10) //negative overflow
         pid_out <= 14'h2000;
      else
         pid_out <= pid_sum[14-1:0];
   end
end

assign pid_sum = $signed(kp_reg) + $signed(int_shr) + $signed(derivative_term);


generate 
	if (ARBITRARY_SATURATION == 0)
		assign dat_o = pid_out;
	else begin
		// Apply the user-configurable out_min/out_max limits after the fixed
		// full-scale saturation above. Registering this comparison keeps the
		// programmable limiter off the 125 MHz combinational timing path, at
		// the cost of one additional PID latency cycle. If
		// ARBITRARY_SATURATION is disabled, dat_o bypasses these programmable
		// limits and uses pid_out directly.
		reg signed [ 14-1:0] out_buffer;
		always @(posedge clk_i) begin
			if (rstn_i == 1'b0)
				out_buffer <= 14'd0;
			else if (external_run && pid_out >= out_max)
				out_buffer <= out_max;
			else if (external_run && pid_out <= out_min)
				out_buffer <= out_min;
			else if (external_run)
				out_buffer <= pid_out;
		end
		assign dat_o = out_buffer; 
	end
endgenerate

endmodule
