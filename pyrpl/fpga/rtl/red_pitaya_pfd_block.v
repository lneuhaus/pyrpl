`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 29.10.2015 13:14:46
// Design Name: 
// Module Name: pfd
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


module red_pitaya_pfd_block_new
(   input rstn_i,
    input clk_i, 
       
    input i, //signal 1
    input q, //signal 2
    
    output [2-1:0] integral_o
    );

reg [2-1:0] integral;

assign integral_o = integral[2-1:0];

always @(posedge clk_i) begin
    if (rstn_i == 1'b0) begin
        integral <= 2'b00;
    end
    else begin
        if ({i,q}==2'b00)
            integral <= 2'b00;
        else if ({i,q}==2'b11)  
            integral <= 2'b10;
		else if ({i,q}==2'b10)
			integral <= 2'b01;
		else if ({i,q}==2'b01)
			integral <= 2b'11;
    end   
end

endmodule

/* module red_pitaya_pfd_block
#(
    parameter ISR = 0
)
(   input rstn_i,
    input clk_i, 
       
    input s1, //signal 1
    input s2, //signal 2
    
    output [14-1:0] integral_o
    );

reg l1; //s1 from last cycle
reg l2; //s2 from last cycle

wire e1;
wire e2;

reg [14+ISR-1:0] integral;

assign e1 = ( {s1,l1} == 2'b10 ) ? 1'b1 : 1'b0;
assign e2 = ( {s2,l2} == 2'b10 ) ? 1'b1 : 1'b0;

assign integral_o = integral[14+ISR-1:ISR];

always @(posedge clk_i) begin
    if (rstn_i == 1'b0) begin
        l1 <= 1'b0;
        l2 <= 1'b0;
        integral <= {(14+ISR){1'b0}};
    end
    else begin
        l1 <= s1;
        l2 <= s2;
        if (integral == {1'b0,{14+ISR-1{1'b1}}})  //auto-reset or positive saturation
            //integral <= {INTBITS{1'b0}};
            integral <= integral + {14+ISR{1'b1}}; //decrement by one
        else if (integral == {1'b1,{14+ISR-1{1'b0}}}) //auto-reset or negative saturation
            //integral <= {INTBITS{1'b0}};
            integral <= integral + {{14+ISR-1{1'b0}},1'b1};
        //output signal is proportional to frequency difference of s1-s2
        else if ({e1,e2}==2'b10)
            integral <= integral + {{14+ISR-1{1'b0}},1'b1};
        else if ({e1,e2}==2'b01)  
            integral <= integral + {14+ISR{1'b1}};
    end   
end

endmodule */
