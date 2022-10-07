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

module red_pitaya_pwm 
  #(  parameter CCW = 24,  // configuration counter width (resolution)
  parameter  [8-1:0] FULL = 8'd255 // 100% value - we increase it for total 12bit resolution
)(
  // system signals
  input             clk ,  // clock
  input             rstn,  // reset
  // configuration
  input signed  [CCW-1:0] cfg ,  // no configuration but signal_i

  // PWM outputs
  output reg  [0:0]      pwm_o ,  // PWM output - driving RC
  output         pwm_s    // PWM synchronization
);


// main part of PWM
reg  [ 4-1: 0] bcnt  ;
reg  [16-1: 0] b     ;
reg  [ 8-1: 0] vcnt, vcnt_r;
reg  [ 8-1: 0] v   ;
reg  [ 9-1: 0] v_r ; // needs an extra bit to avoid overflow
reg  [4-1:0]  clk_div;
  
// short description of what is going on:

// vcnt counts from 0, 1, 2, 3, ..., 255, 0, 1, 2, 3
// vcnt_r = last cycle's vcnt

// bcnt goes like {FULL x 0}, {FULL x 1},..., {FULL x 15}, {FULL x 0}
// i.e. counts the number of cycles that vcnt has performed

// v gets updated every metacycle (when bcnt is 15 and VCNT is FULL)
// with the upper 8 bits of the set register

// b[0] = cfg[bcnt], i.e. changes every FULL cycles

// v_r is the sum of v and b[0], i.e. v_r alternates between upper 8 bits of config and that value +1  


  
always @(posedge clk)
if (~rstn) begin
   clk_div <= 4'h0;
end
else begin
  clk_div <= clk_div + 1'h1;
end


  
always @(posedge clk) begin
    if (~rstn) begin
       vcnt  <=  8'h0 ;
       bcnt  <=  4'h0 ;
       pwm_o <=  1'b0 ;
       v <= 0;
       b <= 0;
       $display("setup");
    end
    else begin
        if (clk_div==0) begin
           vcnt   <= vcnt + 8'd1 ;
           vcnt_r <= vcnt;
           v_r    <= (v + b[0]) ; // add decimal bit to current value
           if (vcnt == FULL) begin
              bcnt <=  bcnt + 4'h1 ;
              v    <= (bcnt == 4'hF) ? cfg[24-1:16] : v ; // new value on 16*FULL
              b    <= (bcnt == 4'hF) ? cfg[16-1:0] : {1'b0,b[15:1]} ; // shift right
           end
           // make PWM duty cycle
           pwm_o <= ({1'b0,vcnt_r} < v_r) ;
        end
    end
end

assign pwm_s = (bcnt == 4'hF) && (vcnt == (FULL-1)) ; // latch one before

endmodule