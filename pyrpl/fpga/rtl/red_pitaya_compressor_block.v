`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: LKB 
// Engineer: Leonhard Neuhaus
// 
// Create Date: 18.02.2016 11:42:49
// Design Name: 
// Module Name: red_pitaya_lpf_block
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
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

/* This module takes a signed input signal of SIGNALBITS, multiplies it by a
gain ranging from 1 to 2**(SIGNALBITS-1)-1, and subtracts it from a custom
setpoint before outputting the signal. The multiplication factor is the
result from taking the absolute value of the output signal and integrating
it. That way, the output signal will be stabilized at setpoint up to the
unity-gain frequency of the integrator, but its higher-frequency components
will pass through. One useful application of this is to make a pdh signal
more robust to amplitude fluctuations that it already is, as even away from
the zero crossing of the error signal, where the pdh amplitude is
proportional to the DC power, the effective DC power after this module is
constant (and equal to the setpoint). */

module red_pitaya_compressor_block
#(
    parameter     SHIFTBITS =     4,//shift can be from 0 to 15 bits
    parameter     SIGNALBITS   = 14, //bitwidth of signals
    parameter     MINBW        = 10  //minimum allowed filter bandwidth
    )
(
    input clk_i,
    input rstn_i  ,
    input [SHIFTBITS:0] shift, 
    input filter_on,
    input highpass,
    input signed  [SIGNALBITS-1:0] signal_i,
    input signed  [SIGNALBITS-1:0] setpoint_i,
    output signed [SIGNALBITS-1:0] signal_o
);

reg  signed [SIGNALBITS+MAXSHIFT-1:0]    y;
reg  signed [SIGNALBITS+MAXSHIFT-1:0]    delta;   //we need this cumbersome imperfect implementation with a delta buffer to introduce some delay so the code works at 125 MHZ
wire signed [SIGNALBITS+MAXSHIFT-1:0]    shifted_delta;
wire signed [SIGNALBITS-1:0]  y_out;
wire filter_off;

assign y_out = y[MAXSHIFT+SIGNALBITS-1:MAXSHIFT];
assign shifted_delta = delta<<shift;

always @(posedge clk_i) begin
    if (rstn_i == 1'b0) begin
        y <=            {MAXSHIFT+SIGNALBITS{1'b0}};
        delta <=        {MAXSHIFT+SIGNALBITS{1'b0}};
    end
    else begin
        delta <= signal_i - y_out;
        y <= y + shifted_delta;
    end
end

assign signal_o = (filter_on == 1'b0) ? signal_i : ( (highpass==1'b0) ? y_out : delta);

endmodule


//---------------------------------------------------------------------------------
// Integrator - 2 cycles delay (but treat similar to proportional since it
// will become negligible at high frequencies where delay is important)

localparam IBW = ISR+16; //integrator bit-width. Over-represent the integral sum to record longterm drifts (overrepresented by 2 bits)

reg   [15+GAINBITS-1: 0] ki_mult ;
wire  [IBW  : 0] int_sum       ;
reg   [IBW-1: 0] int_reg       ;
wire  [IBW-ISR-1: 0] int_shr   ;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      ki_mult  <= {15+GAINBITS{1'b0}};
      int_reg  <= {IBW{1'b0}};
   end
   else begin
      ki_mult <= $signed(error) * $signed(set_ki) ;
      if (ival_write)
         int_reg <= { {IBW-16-ISR{set_ival[16-1]}},set_ival[16-1:0],{ISR{1'b0}}};
      else if (int_sum[IBW+1-1:IBW+1-2] == 2'b01) // positive saturation
         int_reg <= {1'b0,{IBW-1{1'b1}}};
      else if (int_sum[IBW+1-1:IBW+1-2] == 2'b10) // negative saturation
         int_reg <= {1'b1,{IBW-1{1'b0}}};
      else
         int_reg <= int_sum[IBW-1:0]; // use sum as it is
   end
end

assign int_sum = $signed(ki_mult) + $signed(int_reg) ;
assign int_shr = $signed(int_reg[IBW-1:ISR]) ;
