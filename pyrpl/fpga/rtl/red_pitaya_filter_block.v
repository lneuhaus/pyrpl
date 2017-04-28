`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: LKB 
// Engineer: Leonhard Neuhaus
// 
// Create Date: 18.02.2016 11:42:49
// Design Name: 
// Module Name: red_pitaya_filter_block
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

module red_pitaya_filter_block
#(
    parameter     STAGES = 1,    //max. 4 stages
    parameter     SHIFTBITS = 4, //shift can be from 0 to 15 bits
    parameter     SIGNALBITS = 14, //bit width of the signals
    parameter     MINBW = 10
    )
(
    input clk_i,
    input rstn_i  ,
    input [32-1:0] set_filter, 
    input signed [SIGNALBITS-1:0] dat_i,
    output signed [SIGNALBITS-1:0] dat_o
);

//-----------------------------
// cascaded set of FILTERSTAGES low- or high-pass filters

wire signed [SIGNALBITS-1:0] filter_in[STAGES-1:0];
wire signed [SIGNALBITS-1:0] filter_out[STAGES-1:0];

assign filter_in[0] = dat_i;
assign dat_o = filter_out[STAGES-1];

genvar j;
generate for (j = 0; j < STAGES-1; j = j+1) begin
    assign filter_in[j+1] = filter_out[j];
end endgenerate

generate for (j = 0; j < STAGES; j = j+1)
    red_pitaya_lpf_block #(
     .SHIFTBITS(SHIFTBITS),
     .SIGNALBITS(SIGNALBITS),
     .MINBW(MINBW)
  )
  lpf
  (
  .clk_i(clk_i),
  .rstn_i(rstn_i),
  .shift(set_filter[j*8+SHIFTBITS-1:j*8]), 
  .filter_on(set_filter[j*8+7]),
  .highpass(set_filter[j*8+6]),
  .signal_i(filter_in[j]),
  .signal_o(filter_out[j])
  );

endgenerate

endmodule
