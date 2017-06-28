//////////////////////////////////////////////////////////////////////////////////
// Company: LKB
// Engineer: Leonhard Neuhaus
//
// Create Date: 27.11.2014 14:15:43
// Design Name:
// Module Name: red_pitaya_prng
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


/*
#58: Random noise generator
open
lneuhaus

Original suggestion:
x_{n+1} = (a x_n + b) modulo c

    a=16807
    b= plus ou moins n'importe quoi
    c=2^31

https://en.wikipedia.org/wiki/Lehmer_random_number_generator:

In 1988, Park and Miller2 suggested a Lehmer RNG with particular parameters
n = 231 − 1 = 2,147,483,647 (a Mersenne prime M31)
Given the dynamic nature of the area, it is difficult for nonspecialists to
make decisions about what generator to use. "Give me something I can understand,
implement and port... it needn't be state-of-the-art, just make sure it's
reasonably good and efficient." Our article and the associated minimal standard
generator was an attempt to respond to this request. Five years later, we see
no need to alter our response other than to suggest the use of the multiplier
a = 48271 in place of 16807.

Therefore:
x_{n+1} = (a x_n + b) modulo c
a=48271
b= 2*18 1234 + 4 (or user override)
c=2^31-1
asg_phase_register <= 2*x_n (32 bits) in fpga

asg.scale = 1.0
http://docs.scipy.org/doc/numpy/reference/generated/numpy.random.normal.html
asg.data = np.random.normal(loc=0.0, scale=sigma_in_volt, size=data_length)
*/


module red_pitaya_prng_lehmer #(
    parameter     A = 48271,      // recommended by Park and Miller
    parameter     B = 323485697,
    parameter     SEED = 901448241,
    parameter     STATEBITS = 31,
    parameter     OUTBITS   = 14
)
(
    input clk_i,
    input reset_i  ,
    output signed [OUTBITS-1:0] signal_o
);

reg [STATEBITS-1:0] xn;
wire [STATEBITS-1:0] xn_wire;
reg [STATEBITS-1:0] b;
reg [16-1:0] a;

always @(posedge clk_i)
if (reset_i == 1'b0) begin
   a <= A;
   b <= B;   // whatever
   xn <= SEED ; // whatever
end else begin
   xn <= ((&xn_wire)==1'b1) ? {STATEBITS{1'b0}} : xn_wire;
   // = very wrong modulo 2**31-1, but halves number of bits and gives
   // period of about 125 MHz and seemingly white noise
end

assign xn_wire = a * xn + b;
assign signal_o = xn[STATEBITS-1:STATEBITS-OUTBITS];
//signal_o will carry values between 0 and 2**(RSZ)-2

endmodule



// simple 32-bit xorshift generator from "Numerical recipes (C++), online version, pp. 354-355", ID G1
// the book can be found here: http://apps.nrbook.com/empanel/index.html#
// actually, this implementation contains three independent, nested generators
module red_pitaya_prng_xor #(
    parameter     B1 = 13,
    parameter     B2 = 17,
    parameter     B3 = 5,
    parameter     SEED1 = 1,
    parameter     SEED2 = 2,
    parameter     SEED3 = 3,
    parameter     STATEBITS = 32,
    parameter     OUTBITS   = 14
)
(
    input clk_i,
    input reset_i  ,
    output signed [OUTBITS-1:0] signal_o
);

reg [STATEBITS-1:0] x1;
reg [STATEBITS-1:0] x2;
reg [STATEBITS-1:0] x3;

always @(posedge clk_i) begin
  if (reset_i == 1'b0) begin
     x1 <= SEED1;
     x2 <= SEED2;
     x3 <= SEED3;
  end
  else begin
     x1 <= x3 ^ (x3 >> B1);
     x2 <= x1 ^ (x1 << B2);
     x3 <= x2 ^ (x2 >> B3);
  end
end

assign signal_o = x3[STATEBITS-1:STATEBITS-OUTBITS];

endmodule
