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
    output signed [OUTBITS-1:0] signal_o //the i-quadrature
);

wire signed [GAINBITS+INBITS-1:0] firstproduct1;
wire signed [GAINBITS+INBITS-1:0] firstproduct2;
assign firstproduct1 = signal1_i * g1 + (g2 <<<INBITS);
assign firstproduct2 = signal2_i * g4;

reg signed [OUTBITS-1:0] firstproduct1_reg;
reg signed [OUTBITS-1:0] firstproduct2_reg;
always @(posedge clk_i) begin
    if ({firstproduct1[GAINBITS+INBITS-1],|firstproduct1[GAINBITS+INBITS-2:GAINBITS+INBITS-SHIFTBITS-1]} == 2'b01) //positive overflow
        firstproduct1_reg <= {1'b0,{OUTBITS-1{1'b1}}};
     else if ({firstproduct1[GAINBITS+INBITS-1],&firstproduct1[GAINBITS+INBITS-2:GAINBITS+INBITS-SHIFTBITS-1]} == 2'b10) //negative overflow
        firstproduct1_reg <= {1'b1,{OUTBITS-1{1'b0}}};
     else
        firstproduct1_reg <= firstproduct1[GAINBITS+INBITS-SHIFTBITS-1:GAINBITS+INBITS-SHIFTBITS-OUTBITS];
     
     if ({firstproduct2[GAINBITS+INBITS-1],|firstproduct2[GAINBITS+INBITS-2:GAINBITS+INBITS-SHIFTBITS-1]} == 2'b01) //positive overflow
        firstproduct2_reg <= {1'b0,{OUTBITS-1{1'b1}}};
     else if ({firstproduct2[GAINBITS+INBITS-1],&firstproduct2[GAINBITS+INBITS-2:GAINBITS+INBITS-SHIFTBITS-1]} == 2'b10) //negative overflow
        firstproduct2_reg <= {1'b1,{OUTBITS-1{1'b0}}};
     else
        firstproduct2_reg <= firstproduct2[GAINBITS+INBITS-SHIFTBITS-1:GAINBITS+INBITS-SHIFTBITS-OUTBITS];
end

wire signed [OUTBITS+SINBITS-1:0] secondproduct1;
wire signed [OUTBITS+SINBITS-1:0] secondproduct2;
assign secondproduct1 = firstproduct1_reg * sin;
assign secondproduct2 = firstproduct2_reg * cos;

reg signed [OUTBITS+SINBITS-1:0] secondproduct_reg;
reg signed [OUTBITS-1:0] secondproduct_out;

//summation and saturation management
always @(posedge clk_i) begin
    secondproduct_reg <= secondproduct1 + secondproduct2;
    secondproduct_out <= secondproduct_reg[OUTBITS+SINBITS-1:SINBITS]; //can boost the gain here because no overflow is possible if the sin does not exceed 2**l(utsize-1)-1
end
assign dat_o = secondproduct_out;

red_pitaya_product_sat  #( 
	.BITS_IN1(INBITS), 
	.BITS_IN2(GAINBITS), 
	.SHIFT(SHIFTBITS), 
	.BITS_OUT(OUTBITS))
i0_product_and_sat (
  .factor1_i(signal1_i),
  .factor2_i(g3),
  .product_o(i0_product),
  .overflow ()
);   
//output the scaled quadrature
wire signed [OUTBITS-1:0] i0_product;
reg signed [OUTBITS-1:0] i0_product_reg;
always @(posedge clk_i) 
    i0_product_reg <= i0_product;
assign signal_o = i0_product_reg;

endmodule
