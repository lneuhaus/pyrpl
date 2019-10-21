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
   output reg            sys_ack         ,  // bus acknowledge signal

   // XADC pins
   input      [  5-1: 0] vinp_i          ,  //!< voltages p
   input      [  5-1: 0] vinn_i            //!< voltages n

);


// bridge between ADC and sys clock

wire  [ 32-1: 0] addr         ;
wire  [ 32-1: 0] wdata        ;
wire             wen          ;
wire             ren          ;
reg   [ 32-1: 0] rdata        ;
reg              err          ;
reg              ack          ;

bus_clk_bridge i_bridge
(
   .sys_clk_i     (  clk_i      ),
   .sys_rstn_i    (  rstn_i     ),
   .sys_addr_i    (  sys_addr     ),
   .sys_wdata_i   (  sys_wdata    ),
   .sys_sel_i     (  sys_sel      ),
   .sys_wen_i     (  sys_wen      ),
   .sys_ren_i     (  sys_ren      ),
   .sys_rdata_o   (  sys_rdata    ),
   .sys_err_o     (  sys_err      ),
   .sys_ack_o     (  sys_ack      ),

   .clk_i         (  clk_i          ),
   .rstn_i        (  rstn_i         ),
   .addr_o        (  addr           ),
   .wdata_o       (  wdata          ),
   .wen_o         (  wen            ),
   .ren_o         (  ren            ),
   .rdata_i       (  rdata          ),
   .err_i         (  err            ),
   .ack_i         (  ack            )
);


// XADC registers
reg   [ 12-1: 0] adc_a_r      ;
reg   [ 12-1: 0] adc_b_r      ;
reg   [ 12-1: 0] adc_c_r      ;
reg   [ 12-1: 0] adc_d_r      ;
reg   [ 12-1: 0] adc_v_r      ;

reg   [ 12-1: 0] adc_temp_r   ;
reg   [ 12-1: 0] adc_pint_r   ;
reg   [ 12-1: 0] adc_paux_r   ;
reg   [ 12-1: 0] adc_bram_r   ;
reg   [ 12-1: 0] adc_int_r    ;
reg   [ 12-1: 0] adc_aux_r    ;
reg   [ 12-1: 0] adc_ddr_r    ;



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
   if (wen) begin
      // if (addr[19:0]==16'h20)   dac_a_o <= sys_wdata[24-1: 0] ;
      // if (addr[19:0]==16'h24)   dac_b_o <= sys_wdata[24-1: 0] ;
      if (addr[19:0]==16'h28)   dac_c_o <= wdata[24-1: 0] ;
      if (addr[19:0]==16'h2C)   dac_d_o <= wdata[24-1: 0] ;
   end
end

wire sys_en;
assign sys_en = sys_wen | sys_ren;

always @(posedge clk_i) begin
   err <= 1'b0 ;
   casez (addr[19:0])
     // PWM ports
     20'h00020 : begin ack <= 1'b1;         rdata <= {{32-24{1'b0}}, dac_a_o}          ; end
     20'h00024 : begin ack <= 1'b1;         rdata <= {{32-24{1'b0}}, dac_b_o}          ; end
     20'h00028 : begin ack <= 1'b1;         rdata <= {{32-24{1'b0}}, dac_c_o}          ; end
     20'h0002C : begin ack <= 1'b1;         rdata <= {{32-24{1'b0}}, dac_d_o}          ; end

     // XADC ports
     20'h00000 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_a_r}          ; end
     20'h00004 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_b_r}          ; end
     20'h00008 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_c_r}          ; end
     20'h0000C : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_d_r}          ; end
     20'h00010 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_v_r}          ; end
     20'h00030 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_temp_r}       ; end
     20'h00034 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_pint_r}       ; end
     20'h00038 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_paux_r}       ; end
     20'h0003C : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_bram_r}       ; end
     20'h00040 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_int_r}        ; end
     20'h00044 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_aux_r}        ; end
     20'h00048 : begin ack <= 1'b1;         rdata <= {{32-12{1'b0}}, adc_ddr_r}        ; end

     default : begin ack <= 1'b1;         rdata <=   32'h0; end

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



//---------------------------------------------------------------------------------
//  XADC


wire [ 8-1: 0] xadc_alarm     ;
wire           xadc_busy      ;
wire [ 5-1: 0] xadc_channel   ;
wire           xadc_eoc       ;
wire           xadc_eos       ;
wire [17-1: 0] xadc_vinn      ;
wire [17-1: 0] xadc_vinp      ;
wire           xadc_reset     = rstn_i ;

wire [16-1: 0] xadc_drp_dato  ;
wire           xadc_drp_drdy  ;
wire [ 7-1: 0] xadc_drp_addr  = {2'h0, xadc_channel};
wire           xadc_drp_clk   = clk_i     ;
wire           xadc_drp_en    = xadc_eoc  ;
wire [16-1: 0] xadc_drp_dati  = 16'h0     ;
wire           xadc_drp_we    =  1'b0     ;

assign xadc_vinn = {vinn_i[4], 6'h0, vinn_i[3:2], 6'h0, vinn_i[1:0]}; //vn, 9,8,1,0
assign xadc_vinp = {vinp_i[4], 6'h0, vinp_i[3:2], 6'h0, vinp_i[1:0]}; //vp, 9,8,1,0

XADC #(
  // INIT_40 - INIT_42: XADC configuration registers
  .INIT_40(16'h0000), // config reg 0
  .INIT_41(16'h2f0f), // config reg 1
  .INIT_42(16'h0400), // config reg 2
  // INIT_48 - INIT_4F: Sequence Registers
//.INIT_48(16'h0900), // Sequencer channel selection // VpVn & temperature
  .INIT_48(16'h4fe0), // Sequencer channel selection // include system voltages & temperature
  .INIT_49(16'h0303), // Sequencer channel selection
//.INIT_4A(16'h0100), // Sequencer Average selection // average temperature
  .INIT_4A(16'h47e0), // Sequencer Average selection // average system voltages & temperature
  .INIT_4B(16'h0000), // Sequencer Average selection
  .INIT_4C(16'h0800), // Sequencer Bipolar selection
  .INIT_4D(16'h0303), // Sequencer Bipolar selection
  .INIT_4E(16'h0000), // Sequencer Acq time selection
  .INIT_4F(16'h0000), // Sequencer Acq time selection
  // INIT_50 - INIT_58, INIT5C: Alarm Limit Registers
  .INIT_50(16'hb5ed), // Temp alarm trigger
  .INIT_51(16'h57e4), // Vccint upper alarm limit
  .INIT_52(16'ha147), // Vccaux upper alarm limit
  .INIT_53(16'hca33), // Temp alarm OT upper
  .INIT_54(16'ha93a), // Temp alarm reset
  .INIT_55(16'h52c6), // Vccint lower alarm limit
  .INIT_56(16'h9555), // Vccaux lower alarm limit
  .INIT_57(16'hae4e), // Temp alarm OT reset
  .INIT_58(16'h5999), // VBRAM upper alarm limit
  .INIT_5C(16'h5111), // VBRAM lower alarm limit
  .INIT_59(16'h5555), // VCCPINT upper alarm limit
  .INIT_5D(16'h5111), // VCCPINT lower alarm limit
  .INIT_5A(16'h9999), // VCCPAUX upper alarm limit
  .INIT_5E(16'h91eb), // VCCPAUX lower alarm limit
  .INIT_5B(16'h6aaa), // VCCDdro upper alarm limit
  .INIT_5F(16'h6666), // VCCDdro lower alarm limit
  // Simulation attributes: Set for proper simulation behavior
  .SIM_DEVICE("7SERIES"),            // Select target device (values)
  .SIM_MONITOR_FILE("../../../../code/bench/xadc_sim_values.txt")  // Analog simulation data file name
)
XADC_inst
(
  // ALARMS: 8-bit (each) output: ALM, OT
  .ALM        (  xadc_alarm           ),  // 8-bit output: Output alarm for temp, Vccint, Vccaux and Vccbram
  .OT         (                       ),  // 1-bit output: Over-Temperature alarm
  // STATUS: 1-bit (each) output: XADC status ports
  .BUSY       (  xadc_busy            ),  // 1-bit output: ADC busy output
  .CHANNEL    (  xadc_channel         ),  // 5-bit output: Channel selection outputs
  .EOC        (  xadc_eoc             ),  // 1-bit output: End of Conversion
  .EOS        (  xadc_eos             ),  // 1-bit output: End of Sequence
  // Analog-Input Pairs
  .VAUXN      (  xadc_vinn[15:0]      ),  // 16-bit input: N-side auxiliary analog input
  .VAUXP      (  xadc_vinp[15:0]      ),  // 16-bit input: P-side auxiliary analog input
  .VN         (  xadc_vinn[16]        ),  // 1-bit input: N-side analog input
  .VP         (  xadc_vinp[16]        ),  // 1-bit input: P-side analog input
  // CONTROL and CLOCK: 1-bit (each) input: Reset, conversion start and clock inputs
  .CONVST     (  1'b0                 ),  // 1-bit input: Convert start input
  .CONVSTCLK  (  1'b0                 ),  // 1-bit input: Convert start input
  .RESET      ( !xadc_reset           ),  // 1-bit input: Active-high reset
  // Dynamic Reconfiguration Port (DRP)
  .DO         (  xadc_drp_dato        ),  // 16-bit output: DRP output data bus
  .DRDY       (  xadc_drp_drdy        ),  // 1-bit output: DRP data ready
  .DADDR      (  xadc_drp_addr        ),  // 7-bit input: DRP address bus
  .DCLK       (  xadc_drp_clk         ),  // 1-bit input: DRP clock
  .DEN        (  xadc_drp_en          ),  // 1-bit input: DRP enable signal
  .DI         (  xadc_drp_dati        ),  // 16-bit input: DRP input data bus
  .DWE        (  xadc_drp_we          ),  // 1-bit input: DRP write enable

  .JTAGBUSY     (   ), // 1-bit output: JTAG DRP transaction in progress output
  .JTAGLOCKED   (   ), // 1-bit output: JTAG requested DRP port lock
  .JTAGMODIFIED (   ), // 1-bit output: JTAG Write to the DRP has occurred
  .MUXADDR      (   )  // 5-bit output: External MUX channel decode
);


always @(posedge clk_i) begin
   if (xadc_drp_drdy) begin
      if (xadc_drp_addr == 7'd0 )   adc_temp_r <= xadc_drp_dato[15:4]; // temperature
      if (xadc_drp_addr == 7'd13)   adc_pint_r <= xadc_drp_dato[15:4]; // vccpint
      if (xadc_drp_addr == 7'd14)   adc_paux_r <= xadc_drp_dato[15:4]; // vccpaux
      if (xadc_drp_addr == 7'd6 )   adc_bram_r <= xadc_drp_dato[15:4]; // vccbram
      if (xadc_drp_addr == 7'd1 )   adc_int_r  <= xadc_drp_dato[15:4]; // vccint
      if (xadc_drp_addr == 7'd2 )   adc_aux_r  <= xadc_drp_dato[15:4]; // vccaux
      if (xadc_drp_addr == 7'd15)   adc_ddr_r  <= xadc_drp_dato[15:4]; // vccddr

      if (xadc_drp_addr == 7'h03)   adc_v_r <= xadc_drp_dato[15:4]; // vin
      if (xadc_drp_addr == 7'd16)   adc_b_r <= xadc_drp_dato[15:4]; // ch0 - aif1
      if (xadc_drp_addr == 7'd17)   adc_c_r <= xadc_drp_dato[15:4]; // ch1 - aif2
      if (xadc_drp_addr == 7'd24)   adc_a_r <= xadc_drp_dato[15:4]; // ch8 - aif0
      if (xadc_drp_addr == 7'd25)   adc_d_r <= xadc_drp_dato[15:4]; // ch9 - aif3
   end
end


endmodule
