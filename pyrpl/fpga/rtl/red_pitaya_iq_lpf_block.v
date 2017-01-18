//////////////////////////////////////////////////////////////////////////////////
// Company: LKB
// Engineer: Leonhard Neuhaus
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


module red_pitaya_iq_lpf_block #(
    parameter     ALPHABITS = 25,
    parameter     HIGHESTALPHABIT = 18,
    parameter     LPFBITS   = 18 //,
//    parameter     HIGHPASS    = 0
)
(
    input clk_i,
    input reset_i  ,
    input signed [HIGHESTALPHABIT-1:0] alpha_i, 

    input signed [LPFBITS-1:0] signal_i,
    output signed [LPFBITS-1:0] signal_o
);

//reg signed [ALPHABITS-1:0] alpha;
reg  signed [LPFBITS+ALPHABITS-1:0]    y;
reg  signed [LPFBITS+ALPHABITS-1:0]    delta;   //we need this cumbersome imperfect implementation with a delta buffer to introduce some delay so the code works at 125 MHZ
//reg  signed [LPFBITS+1-1:0]  delta_out;
wire signed [LPFBITS-1:0]  y_out;

assign y_out = y[ALPHABITS+LPFBITS-1:ALPHABITS];

always @(posedge clk_i) begin
//    alpha <= $signed(alpha_i);
    if (reset_i == 1'b1) begin
        y <=            {ALPHABITS+LPFBITS{1'b0}};
        delta <=        {ALPHABITS+LPFBITS{1'b0}};
        //delta_out <=    {LPFBITS{1'b0}};
    end
    else begin
        //delta <= ($signed(signal_i)-$signed(y_out))*$signed(alpha);
        //y <= $signed(y) + $signed(delta);
        delta <= (signal_i-y_out)*alpha_i;
        //delta_out <= signal_i - y_out;
        y <= y + delta;
    end
end
    
assign signal_o = y_out;

//generate 
//if (HIGHPASS == 0)
//    assign signal_o = y_out;
//else
//    if (delta_out[LPFBITS:LPFBITS-1] == 2'b01)
//        assign signal_o = {1'b0,{LPFBITS-1{1'b1}}};
//    else if (delta_out[LPFBITS:LPFBITS-1] == 2'b10)
//       assign signal_o = {1'b1,{LPFBITS-1{1'b0}}};
//    else
//        assign signal_o = delta_out[LPFBITS-1:0];
//endgenerate

endmodule



