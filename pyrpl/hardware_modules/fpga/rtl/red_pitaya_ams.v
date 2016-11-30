/**
 * $Id: red_pitaya_ams.v 961 2014-01-21 11:40:39Z matej.oblak $
 *
 * @brief Red Pitaya analog mixed signal.
 *
 * @Author Matej Oblak
 *
 * (c) Red Pitaya  http://www.redpitaya.com
 *
 * This part of code is written in Verilog hardware description language (HDL).
 * Please visit http://en.wikipedia.org/wiki/Verilog
 * for more details on the language used herein.
 */

/**
 * GENERAL DESCRIPTION:
 *
 * Module using XADC and software interface for PWM DAC.
 *
 *
 *                    /------\
 *   SUPPLY V. -----> |      |
 *   TEMPERATURE ---> | XADC | ------
 *   EXTERNAL V. ---> |      |       |
 *                    \------/       |
 *                                   |
 *                                   ˇ
 *                               /------\
 *   PWD DAC <------------------ | REGS | <------> SW
 *                               \------/
 *
 *
 * Reading system and external voltages is done with XADC, running in sequencer
 * mode. It measures supply voltages, temperature and voltages on external
 * connector. Measured values are then exposed to SW.
 *
 * Beside that SW can sets registes which controls logic for PWM DAC (analog module).
 * 
 */

module red_pitaya_ams (
   // ADC
   input                 clk_i           ,  // clock
   input                 rstn_i          ,  // reset - active low
   // PWM DAC
   output reg [ 24-1: 0] dac_a_o         ,  // values used for
   output reg [ 24-1: 0] dac_b_o         ,  // conversion into PWM signal
   output reg [ 24-1: 0] dac_c_o         ,  // 
   output reg [ 24-1: 0] dac_d_o         ,  // 
   input      [ 14-1: 0] pwm0_i          ,  // 14 bit inputs for compatibility and future upgrades;
  								  	        // right now only 12 bits are used  
   input      [ 14-1: 0] pwm1_i          ,  
   
   // system bus
   input      [ 32-1: 0] sys_addr        ,  // bus address
   input      [ 32-1: 0] sys_wdata       ,  // bus write data
   input      [  4-1: 0] sys_sel         ,  // bus write byte select
   input                 sys_wen         ,  // bus write enable
   input                 sys_ren         ,  // bus read enable
   output reg [ 32-1: 0] sys_rdata       ,  // bus read data
   output reg            sys_err         ,  // bus error indicator
   output reg            sys_ack            // bus acknowledge signal
);

//---------------------------------------------------------------------------------
//
//  System bus connection

always @(posedge clk_i)
if (rstn_i == 1'b0) begin
   dac_a_o     <= 24'h000000 ;
   dac_b_o     <= 24'h000000 ;
   dac_c_o     <= 24'h000000 ;
   dac_d_o     <= 24'h000000 ;
end else begin
   dac_a_o <= cfg;
   dac_b_o <= cfg_b;
   if (sys_wen) begin
      // if (sys_addr[19:0]==16'h20)   dac_a_o <= sys_wdata[24-1: 0] ;
      // if (sys_addr[19:0]==16'h24)   dac_b_o <= sys_wdata[24-1: 0] ;
      if (sys_addr[19:0]==16'h28)   dac_c_o <= sys_wdata[24-1: 0] ;
      if (sys_addr[19:0]==16'h2C)   dac_d_o <= sys_wdata[24-1: 0] ;
   end
end

wire sys_en;
assign sys_en = sys_wen | sys_ren;

always @(posedge clk_i)
if (rstn_i == 1'b0) begin
   sys_err <= 1'b0 ;
   sys_ack <= 1'b0 ;
end else begin
   sys_err <= 1'b0 ;
   casez (sys_addr[19:0])
     20'h00020 : begin sys_ack <= sys_en;         sys_rdata <= {{32-24{1'b0}}, dac_a_o}          ; end
     20'h00024 : begin sys_ack <= sys_en;         sys_rdata <= {{32-24{1'b0}}, dac_b_o}          ; end
     20'h00028 : begin sys_ack <= sys_en;         sys_rdata <= {{32-24{1'b0}}, dac_c_o}          ; end
     20'h0002C : begin sys_ack <= sys_en;         sys_rdata <= {{32-24{1'b0}}, dac_d_o}          ; end
       default : begin sys_ack <= sys_en;         sys_rdata <=   32'h0                           ; end
   endcase
end


// conversion of 14 bit input signal into config register:
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

localparam CCW = 24; // configuration bitwidth for pwm module

reg [24-1:0] cfg;
wire bit3;
wire bit2;
wire bit1;
wire bit0;
assign {bit3,bit2,bit1,bit0} = pwm0_i[5:2];
always @(posedge clk_i)
if (rstn_i == 1'b0) begin
   cfg   <=  {CCW{1'b0}};
end else begin
   cfg  <= {~pwm0_i[13],pwm0_i[13-1:6],1'b0,bit3,bit2,bit3,bit1,bit3,bit2,bit3,bit0,bit3,bit2,bit3,bit1,bit3,bit2,bit3};
end

reg [24-1:0] cfg_b;
wire bit3_b;
wire bit2_b;
wire bit1_b;
wire bit0_b;
assign {bit3_b,bit2_b,bit1_b,bit0_b} = pwm1_i[5:2];
always @(posedge clk_i)
if (rstn_i == 1'b0) begin
   cfg_b   <=  {CCW{1'b0}};
end else begin
   cfg_b  <= {~pwm1_i[13],pwm1_i[13-1:6],1'b0,bit3_b,bit2_b,bit3_b,bit1_b,bit3_b,bit2_b,bit3_b,bit0_b,bit3_b,bit2_b,bit3_b,bit1_b,bit3_b,bit2_b,bit3_b};
end

endmodule
