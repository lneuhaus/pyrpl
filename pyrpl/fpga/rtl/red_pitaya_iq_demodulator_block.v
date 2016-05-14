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
    parameter     SHIFTBITS  = 0
)
(
    input clk_i,
    input signed [SINBITS-1:0] sin, 
    input signed [SINBITS-1:0] cos, 
    input signed [INBITS-1:0] signal_i,
    output signed [OUTBITS-1:0] signal1_o,            
    output signed [OUTBITS-1:0] signal2_o            
);

reg signed [INBITS-1:0] firstproduct_reg;
always @(posedge clk_i) begin
    firstproduct_reg <= signal_i;//$signed(signal_i);
end

reg signed [SINBITS+INBITS-1:0] product1;
reg signed [SINBITS+INBITS-1:0] product2;
always @(posedge clk_i) begin
    //product1 <= $signed(firstproduct_reg)*$signed(sin);
    //product2 <= $signed(firstproduct_reg)*$signed(cos);
    product1 <= firstproduct_reg * sin;
    product2 <= firstproduct_reg * cos;
end

assign signal1_o = product1[SINBITS+INBITS-1-SHIFTBITS:SINBITS+INBITS-OUTBITS-SHIFTBITS];
assign signal2_o = product2[SINBITS+INBITS-1-SHIFTBITS:SINBITS+INBITS-OUTBITS-SHIFTBITS];

endmodule
