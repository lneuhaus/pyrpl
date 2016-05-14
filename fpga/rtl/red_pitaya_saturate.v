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

`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 13.12.2015 18:56:43
// Design Name: 
// Module Name: saturate
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

`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 13.12.2015 18:04:09
// Design Name: 
// Module Name: product_sat
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


module red_pitaya_saturate
#( parameter BITS_IN = 50,
   parameter BITS_OUT = 20,
   parameter SHIFT = 10
)
(
    input signed [BITS_IN-1:0] input_i,
    output signed [BITS_OUT-1:0] output_o,
    output overflow
    );

assign {output_o,overflow} =  ( {input_i[BITS_IN-1],|input_i[BITS_IN-2:SHIFT+BITS_OUT-1]} ==2'b01) ? 
                                                                            {{1'b0,{BITS_OUT-1{1'b1}}},1'b1}  : //positive overflow
                   ( {input_i[BITS_IN-1],&input_i[BITS_IN-2:SHIFT+BITS_OUT-1]} == 2'b10) ? 
                                                                            {{1'b1,{BITS_OUT-1{1'b0}}},1'b1}  : //negative overflow
                    {input_i[SHIFT+BITS_OUT-1:SHIFT],1'b0} ; //correct value           

endmodule
