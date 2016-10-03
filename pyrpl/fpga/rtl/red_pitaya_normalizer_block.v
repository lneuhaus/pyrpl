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

module red_pitaya_normalizer_block
#(
    parameter     ISR          = 24,
    parameter     SIGNALBITS   = 14, //bitwidth of signals
    parameter     GAINBITS     = 16  //minimum allowed filter bandwidth
    )
(
    input clk_i,
    input rstn_i  ,
    input [SHIFTBITS:0] shift, 
    input filter_on,
    input highpass,
    input signed  [SIGNALBITS-1:0] signal_i,
    input signed  [SIGNALBITS-1:0] inputoffset_i,
    input [SIGNALBITS-2:0] setpoint_i,
    input signed [GAINBITS-1:0] gain_i,
    output signed [SIGNALBITS-1:0] signal_o
);

// add an offset to the (analog) input value
wire signed [SIGNALBITS+1-1:0] in_subtracted;
wire [SIGNALBITS-1:0] in_abs;
assign in_subtracted = signal_i - inputoffset_i;
// make input positive, but don't add the extra bit. That gives a tiny
// offset to negative signals (1 bit, but avoid special treatment for the
// stragne number
assign in_abs = in_subtracted[SIGNALBITS] ? ((~in_subtracted) /*+'b1*/) : in_subtracted;
// buffer
reg [SIGNALBITS-1:0] input;
always @(posedge clk_i) begin
    input <= in_abs[SIGNALBITS-1:0];
end
// now, input is in principle a 13 bit number, unless something went really
// wrong with the input offset (in which case its 14 bits unsigned)

// multiply input by integral factor, add something for rounding
// integral goes from 1 to 2**(SIGNALBITS)-1
// input goes from 0 to 2**(SIGNALBITS)-1, but the MSB should be zero
// so product goes from 0 to 2**(2*SIGNALBITS)-1, but MSB should be zero
// we rescale product to product_done taking only the highest SIGNALBITS+1
// bits, of which only SIGNALBITS carry any information
wire  [SIGNALBITS-1:0] integral;
wire [SIGNALBITS*2-1:0] product;
assign product = input * integral; // no rounding since unsigned arithmetic
wire [SIGNALBITS*2:0] product_signed;
wire [SIGNALBITS*2:0] setpoint_signed;
assign product_signed = {1'b0, product};
// first sign bit (0), then the MSB mentioned above, then the SIGNALBITS-1 of
// relevant information
wire signed setpoint_signed =  {1'b0, 1'b0, setpoint_i, {SIGNALBITS{1'b0}};
// error doesnt need extra bit since we subtract 2 positive numbers
reg signed [SIGNALBITS*2:0] error;
always @(posedge clk_i) begin
    error <= setpoint_signed - product_signed;
end
// crop the number by throwing away the 2 most significant bits
reg signed [SIGNALBITS-1:0] error_done;
always @(posedge clk_i) begin
    // pos saturation
    if ({error[SIGNALBITS*2], (|(error[SIGNALBITS*2-1:SIGNALBITS*2-2]))} == 2'b01)
        error_done <= {1'b0, {SIGNALBITS-1{1'b1}}};
    else if ({error[SIGNALBITS*2], (&(error[SIGNALBITS*2-1:SIGNALBITS*2-2]))} == 2'b10)
        error_done <= {1'b1, {SIGNALBITS-1{1'b0}}};
    else
        error_done <= error[SIGNALBITS*2-2:SIGNALBITS-2];
end

assign signal_o = filter_on ? error_done : signal_i;

// gain calculation
// negative gain because of error calculation (setpoint - product)
// therefore just need a positive integrator
reg signed [SIGNALBITS: 0] int_sum;
always @(posedge clk_i) begin
    int_sum <= $signed(int_sat) + $signed(error_done);
end

// Integrator - 2 cycles delay (but treat similar to proportional since it
// will become negligible at high frequencies where delay is important)

localparam IBW = ISR+SIGNALBITS;

reg   [SIGNALBITS+GAINBITS-1: 0] ki_mult ;
wire  [IBW  : 0]     int_sum       ;
reg   [IBW-1: 0]     int_reg       ;
wire  [IBW-ISR-1: 0] int_shr   ;

always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      ki_mult  <= {SIGNALBITS+GAINBITS{1'b0}};
      int_reg  <= {IBW{1'b0}};
   end
   else begin
      ki_mult <= $signed(error_done) * $signed(gain_i) ;
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
