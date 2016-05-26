/**
 * @brief Red Pitaya PWM module
 *
 * @Author Matej Oblak
 *
 * (c) Red Pitaya  http://www.redpitaya.com
 *
 * This part of code is written in Verilog hardware description language (HDL).
 * Please visit http://en.wikipedia.org/wiki/Verilog
 * for more details on the language used herein.
 */
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

module red_pitaya_pwm #(
  int unsigned CCW = 24,  // configuration counter width (resolution)
  bit  [8-1:0] FULL = 8'd255 // 100% value - we increase it for total 12bit resolution
)(
  // system signals
  input  logic           clk ,  // clock
  input  logic           rstn,  // reset
  // configuration
  
  //input  logic [CCW-1:0] cfg ,  // no configuration but signal_i
  input          [ 14-1:0] signal_i, // 14 bit inputs for compatibility and future upgrades;
  									 // right now only 12 bits are used  
  // PWM outputs
  output logic           pwm_o ,  // PWM output - driving RC
  output logic           pwm_s    // PWM synchronization
);


// conversion of input signal into config register:
// bits 4-11 are the duty cycle
// bits 0-3 configure the duty cycle modulation
// therefore fundamental switch frequency is 
// 250 MHz/2**8 = 488.28125 kHz
// the duty cycle is modulated over a period of 16 PWM cycles
// -> lowest frequency is 30.51757812 kHz
// we need to convert bits 0-3 into a bit sequence that 
// will prolong the duty cycle by 1 if the bit is set 
// and 0 if it is not set. The 16 bits will be sequentially 
// interrogated by the PWM
// we will encode bits 0-3 as follows:
// bit3 = 16'b0101010101010101
// bit2 = 16'b0010001000100010
// bit1 = 16'b0000100000001000
// bit0 = 16'b0000000010000000
// resp. bit:  323132303231323
// as you can see, each row except for the first can be filled
// with exactly one bit, therefore our method is exclusive
// and will always lead to a modulation duty cycle in the interval [0:1[

// on top of all this, we need to convert the incoming signal from signed to unsigned
// and from 14 bits to 12
// the former is easy: just bitshift by 2
// the latter is easy as well: 
// maxnegative = 0b1000000 ->        0
// maxnegative + 1 = 0b10000001 ->   1
// ...
// -1 = 0b1111111111 -> 0b01111111111
// therefore: only need to invert the sign bit
// works as well for positive numbers:
// 0 -> 0b1000000000
// 1 -> 0b1000000001
//maxpositive = 0111111111 -> 11111111111

// its not clear at all if the timing will be right here since we work at 250 MHz in this module
// if something doesnt work, parts of the logic must be transferred down to 125 MHz
reg [CCW-1:0] cfg;
wire b3;
wire b2;
wire b1;
wire b0;
assign {b3,b2,b1,b0} = signal_i[5:2];
always @(posedge clk)
if (~rstn) begin
   cfg   <=  {CCW{1'b0}};
end else begin
   cfg  <= {!signal_i[13],signal_i[13-1:6],0'b0,b3,b2,b3,b1,b3,b2,b3,b0,b3,b2,b3,b1,b3,b2,b3};
end

// main part of PWM
reg  [ 4-1: 0] bcnt  ;
reg  [16-1: 0] b     ;
reg  [ 8-1: 0] vcnt, vcnt_r;
reg  [ 8-1: 0] v   , v_r   ;

// short description of what is going on:

// vcnt counts from 1, 2, 3, ..., FULL, 1, 2, 3
// vcnt_r = last cycle's vcnt

// bcnt goes like {FULL x 0}, {FULL x 1},..., {FULL x 15}, {FULL x 0}
// i.e. counts the number of cycles that vcnt has performed

// v gets updated every metacycle (when bcnt is 15 and VCNT is FULL)
// with the upper 8 bits of the set register

// b[0] = cfg[bcnt], i.e. changes every FULL cycles

// v_r is the sum of v and b[0], i.e. v_r alternates between upper 8 bits of config and that value +1  

always @(posedge clk)
if (~rstn) begin
   vcnt  <=  8'h0 ;
   bcnt  <=  4'h0 ;
   pwm_o <=  1'b0 ;
end else begin
   vcnt   <= (vcnt == FULL) ? 8'h0 : (vcnt + 8'd1) ;
   vcnt_r <= vcnt;
   v_r    <= (v + b[0]) ; // add decimal bit to current value
   if (vcnt == FULL) begin
      bcnt <=  bcnt + 4'h1 ;
      v    <= (bcnt == 4'hF) ? cfg[24-1:16] : v ; // new value on 16*FULL
      b    <= (bcnt == 4'hF) ? cfg[16-1:0] : {1'b0,b[15:1]} ; // shift right
   end
   // make PWM duty cycle
   pwm_o <= (vcnt_r <= v_r) ;
end

assign pwm_s = (bcnt == 4'hF) && (vcnt == (FULL-1)) ; // latch one before

endmodule: red_pitaya_pwm
