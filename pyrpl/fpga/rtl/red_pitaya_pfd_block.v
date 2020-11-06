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

module red_pitaya_pfd_block_old
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

endmodule

module red_pitaya_pfd_block_new
#(
	parameter SIGNALBITS = 14, //=output signal bitwidth
	parameter INPUTWIDTH = 14,
	parameter WORKINGWIDTH = 16, //i_val and q_val and ph bitwidth, minimal value: SIGNALBITS+2
	parameter PHASEWIDTH = 10, //number of (least significant) bits encoding the phase 
	parameter TURNWIDTH = 4, //number of (most significant) bits encoding the number of turns around the circle
	parameter NSTAGES = 7 //number of steps in the cordic algorithm
)
(   input rstn_i,
    input clk_i,
       
    input signed [INPUTWIDTH-1:0] i, //quadrature 1
    input signed [INPUTWIDTH-1:0] q, //quadrature 2
   
    output signed [SIGNALBITS-1:0] integral_o
);

reg signed [SIGNALBITS-1:0] integral;

//Adding 2 MSB and WORKINGWIDTH-SIGNALBITS LSB to i and q
//MSB to prevent overflow due to first summing and to the cordic gain
//LSB to add precision (q tends towards 0 during cordic loop)
wire signed [(WORKINGWIDTH-1):0] ext_i, ext_q;
assign	ext_i = { {2{i[(INPUTWIDTH-1)]}}, i, {(WORKINGWIDTH-INPUTWIDTH-2){1'b0}} };
assign	ext_q = { {2{q[(INPUTWIDTH-1)]}}, q, {(WORKINGWIDTH-INPUTWIDTH-2){1'b0}} };

reg	signed	[(WORKINGWIDTH-1):0]	i_val	[0:NSTAGES];
reg	signed	[(WORKINGWIDTH-1):0]	q_val	[0:NSTAGES];
reg			[(PHASEWIDTH-1):0]	    ph		[0:NSTAGES];
reg signed  [(TURNWIDTH-1):0]       turns   [0:NSTAGES];
reg         [1:0]                   last_quadrant;
reg         [4:0]                   start; 

assign integral_o = {turns[NSTAGES],ph[NSTAGES]};
initial turns[0] = 0;

always @(posedge clk_i) begin
    $display("turns[0]");
    $display(turns[0]);
    
    if (rstn_i == 1'b0) begin
        i_val[0] <= 0;
        q_val[0] <= 0;
		ph[0] <= 0;
		last_quadrant <= 2'b11;
		turns[0] <= 0;
		start <= 0;
    end
    else begin
		//Rotation to start in the quadrant [-45°,45°]
		last_quadrant <= {ext_i[WORKINGWIDTH-1], ext_q[WORKINGWIDTH-1]};
        case({ext_i[WORKINGWIDTH-1], ext_q[WORKINGWIDTH-1]})
        2'b01:  begin // Rotate by -315 degrees
                        i_val[0] <=  ext_i - ext_q;
                        q_val[0] <=  ext_i + ext_q;
                        ph[0] <= 10'b0110000000;
                        end
        2'b10:  begin // Rotate by -135 degrees
                        i_val[0] <= -ext_i + ext_q;
                        q_val[0] <= -ext_i - ext_q;
                        ph[0] <= 10'b1110000000;
                        if ((last_quadrant==2'b11) & (turns[0]!={1'b1,{TURNWIDTH-1{1'b0}}})) 
                            turns[0] <= turns[0] - 1;
                        end
        2'b11:  begin // Rotate by -225 degrees
                        i_val[0] <= -ext_i - ext_q;
                        q_val[0] <=  ext_i - ext_q;
                        ph[0] <= 10'b0010000000;
                        if ((last_quadrant==2'b10) & (turns[0] != {1'b0,{TURNWIDTH-1{1'b1}}}))
							turns[0] <= turns[0] + 1;
                        end
        2'b00:  begin // Rotate by -45 degrees
                        i_val[0] <=  ext_i + ext_q;
                        q_val[0] <= -ext_i + ext_q;
                        ph[0] <= 10'b1010000000;
                        end
        endcase
	end
end

wire [PHASEWIDTH-1:0] cordic_angle [0:(NSTAGES-1)];

assign cordic_angle[0] = 10'b0001001011; // 26.565051177077986 deg
assign cordic_angle[1] = 10'b0000100111; // 14.036243467926479 deg
assign cordic_angle[2] = 10'b0000010100; // 7.125016348901799 deg
assign cordic_angle[3] = 10'b0000001010; // 3.5763343749973515 deg
assign cordic_angle[4] = 10'b0000000101; // 1.7899106082460694 deg
assign cordic_angle[5] = 10'b0000000010; // 0.8951737102110744 deg
assign cordic_angle[6] = 10'b0000000001; // 0.4476141708605531 deg
// Note : cordic_angle[k] = Arctan(2^-k) + renormalisation en nb de tours en binaire

genvar k;
generate for(k=0; k<NSTAGES; k=k+1) begin
	always @(posedge clk_i) begin
		if (rstn_i == 1'b0) begin
			i_val[k+1] <= 0;
			q_val[k+1] <= 0;
			ph[k+1] <= 0;
		end
		else begin
			if (q_val[k][(WORKINGWIDTH-1)]) // Below the axis
			begin
				// If the vector is below the x-axis, rotate by
				// the CORDIC angle in a positive direction.
				i_val[k+1] <= i_val[k] - (q_val[k]>>>(k+1));
				q_val[k+1] <= (i_val[k]>>>(k+1)) + q_val[k];
				ph[k+1] <= ph[k] - cordic_angle[k];
				turns[k+1] <= turns[k];
			end else begin
				// On the other hand, if the vector is above the
				// x-axis, then rotate in the other direction
				i_val[k+1] <= i_val[k] + (q_val[k]>>>(k+1));
				q_val[k+1] <= -(i_val[k]>>>(k+1)) + q_val[k];
				ph[k+1] <= ph[k] + cordic_angle[k];
				turns[k+1] <= turns[k];
			end
		end
	end
	end
endgenerate

//To do : round the phase and feed to output port + deal with the turns counter

endmodule