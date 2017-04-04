//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 27.11.2014 14:15:43
// Design Name: 
// Module Name: red_pitaya_iq_fgen_block
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


module red_pitaya_iq_modulator_block #(
    parameter     INBITS   = 18,
    parameter     OUTBITS   = 14,
    parameter     SINBITS   = 14,
    parameter     GAINBITS  = 16,
    parameter     SHIFTBITS = 0)
(
    input clk_i,
    input signed [SINBITS-1:0] sin, 
    input signed [SINBITS-1:0] cos, 
    input signed [GAINBITS-1:0] g1,
    input signed [GAINBITS-1:0] g2,
    input signed [GAINBITS-1:0] g3,
    input signed [GAINBITS-1:0] g4,
    input signed [INBITS-1:0] signal1_i,
    input signed [INBITS-1:0] signal2_i,
    output signed [OUTBITS-1:0] dat_o,            
    output signed [OUTBITS-1:0] signal_q1_o, //the i-quadrature
    output signed [OUTBITS-1:0] signal_q2_o  //the q-quadrature
);

// firstproduct
wire signed [OUTBITS-1:0] firstproduct1;
wire signed [OUTBITS-1:0] firstproduct2;

red_pitaya_product_sat  #(
	.BITS_IN1(INBITS),
	.BITS_IN2(GAINBITS),
	.SHIFT(GAINBITS+INBITS-OUTBITS-SHIFTBITS),
	.BITS_OUT(OUTBITS))
firstproduct_saturation [1:0]
( .factor1_i  (  {signal2_i, signal1_i} ),
  .factor2_i  (  {       g4,        g1} ),
  .product_o  (  {firstproduct2, firstproduct1})
);

// buffering - one extra bit for the sum with g2
reg signed [OUTBITS+1-1:0] firstproduct1_reg;
reg signed [OUTBITS+1-1:0] firstproduct2_reg;
always @(posedge clk_i) begin
    firstproduct1_reg <= $signed(firstproduct1) + $signed(g2[GAINBITS-1:GAINBITS-OUTBITS]);
    firstproduct2_reg <= $signed(firstproduct2);
end

wire signed [OUTBITS+1+SINBITS-1-1:0] secondproduct1;
wire signed [OUTBITS+1+SINBITS-1-1:0] secondproduct2;
assign secondproduct1 = firstproduct1_reg * sin;
assign secondproduct2 = firstproduct2_reg * cos;

//sum of second product has an extra bit
reg signed [OUTBITS+1+SINBITS-1:0] secondproduct_sum;
reg signed [OUTBITS-1:0] secondproduct_out;
wire signed [OUTBITS-1:0] secondproduct_sat;

//summation and saturation management, and buffering
always @(posedge clk_i) begin
    secondproduct_sum <= secondproduct1 + secondproduct2;
    secondproduct_out <= secondproduct_sat;
end

// SHIFT to compensate: sin multiplication (2**SINBITS-1 is the largest number)
red_pitaya_saturate
    #( .BITS_IN(OUTBITS+SINBITS+1),
       .BITS_OUT(OUTBITS),
       .SHIFT(SINBITS-1)
    )
    sumsaturation
    (
    .input_i(secondproduct_sum),
    .output_o(secondproduct_sat)
    );

assign dat_o = secondproduct_out;

//output the scaled quadrature
wire signed [OUTBITS-1:0] q1_product;
wire signed [OUTBITS-1:0] q2_product;

//output first quadrature to scope etc.
red_pitaya_product_sat  #(
	.BITS_IN1(INBITS),
	.BITS_IN2(GAINBITS),
	.SHIFT(SHIFTBITS+2),
	.BITS_OUT(OUTBITS))
i0_product_and_sat (
  .factor1_i(signal1_i),
  .factor2_i(g3),
  .product_o(q1_product),
  .overflow ()
);
// output second quadrature to scope etc.
red_pitaya_product_sat  #(
	.BITS_IN1(INBITS),
	.BITS_IN2(GAINBITS),
	.SHIFT(SHIFTBITS+2),
	.BITS_OUT(OUTBITS))
q0_product_and_sat (
  .factor1_i(signal2_i),
  .factor2_i(g3),
  .product_o(q2_product),
  .overflow ()
);

// pipeline products
reg signed [OUTBITS-1:0] q1_product_reg;
reg signed [OUTBITS-1:0] q2_product_reg;
always @(posedge clk_i) begin
    q1_product_reg <= q1_product;
    q2_product_reg <= q2_product;
end

assign signal_q1_o = q1_product_reg;
assign signal_q2_o = q2_product_reg;

endmodule
