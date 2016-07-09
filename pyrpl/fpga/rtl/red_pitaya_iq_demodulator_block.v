//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 27.11.2014 14:15:43
// Design Name: 
// Module Name: 
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


module red_pitaya_iq_demodulator_block #(
    parameter     INBITS   = 14,
    parameter     OUTBITS   = 18,
    parameter     SINBITS   = 14,
    parameter     SHIFTBITS  = 1
    // why SHIFTBITS SHOULD ALWAYS BE 1:
    // the sin from fgen ranges from -2**(SINBITS-1)+1 to 2**(SINBITS-1)-1
    // i.e. the strange number is excluded by definition. Including the
    // strange number -2**(SINBITS-1), the product signal_i * sin / cos
    // would be maximally
    // 2**(SINBITS+INBITS-1-1). That is, including the sign bit it would
    // occupy SINBITS+INBITS-1 bits. Excluding the strange number of the sin
    // factor makes the maximum less than that, i.e. we can safely represent
    // the product with SINBITS+INBITS-2 bits, including the sign bit.
    // That makes SHIFTBITS = -1 (see below). OUTBITS only determines how many
    // LSB's we cut off.
)
(
    input clk_i,
    input signed  [SINBITS-1:0] sin, 
    input signed  [SINBITS-1:0] cos, 
    input signed  [INBITS-1:0]  signal_i,
    output signed [OUTBITS-1:0] signal1_o,            
    output signed [OUTBITS-1:0] signal2_o            
);

reg signed [INBITS-1:0] firstproduct_reg;
always @(posedge clk_i) begin
    firstproduct_reg <= signal_i;
end


reg signed [SINBITS+INBITS-1:0] product1;
reg signed [SINBITS+INBITS-1:0] product2;

// soft implementation of symmetric rounding
//wire signed [SINBITS+INBITS-1:0] product1_unrounded;
//wire signed [SINBITS+INBITS-1:0] product2_unrounded;
//assign product1_unrounded = firstproduct_reg * sin;
//assign product2_unrounded = firstproduct_reg * cos;
//wire signed [SINBITS+INBITS-1:0] product1_roundoffset;
//wire signed [SINBITS+INBITS-1:0] product2_roundoffset;
//assign product1_roundoffset = (product1_unrounded[SINBITS+INBITS-1]) ? {{(OUTBITS+SHIFTBITS+1){1'b0}},{1'b1},{(SINBITS+INBITS-OUTBITS-SHIFTBITS-2){1'b0}}}
//                            : {{(OUTBITS+SHIFTBITS+1){1'b0}},{1'b0},{(SINBITS+INBITS-OUTBITS-SHIFTBITS-2){1'b1}}};
//
//assign product2_roundoffset = (product2_unrounded[SINBITS+INBITS-1]) ? {{(OUTBITS+SHIFTBITS+1){1'b0}},{1'b1},{(SINBITS+INBITS-OUTBITS-SHIFTBITS-2){1'b0}}}
//                            : {{(OUTBITS+SHIFTBITS+1){1'b0}},{1'b0},{(SINBITS+INBITS-OUTBITS-SHIFTBITS-2){1'b1}}};

// after some problems, we choose asymmetric rounding for now - at least
// some rounding

always @(posedge clk_i) begin
//    product1 <= product1_unrounded + product1_roundoffset;
//    product2 <= product2_unrounded + product2_roundoffset;
    product1 <= firstproduct_reg * sin + $signed(1 << (SINBITS+INBITS-OUTBITS-SHIFTBITS-1));
    product2 <= firstproduct_reg * cos + $signed(1 << (SINBITS+INBITS-OUTBITS-SHIFTBITS-1));
end

assign signal1_o = product1[SINBITS+INBITS-1-SHIFTBITS:SINBITS+INBITS-OUTBITS-SHIFTBITS];
assign signal2_o = product2[SINBITS+INBITS-1-SHIFTBITS:SINBITS+INBITS-OUTBITS-SHIFTBITS];

endmodule
