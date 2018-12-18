/*
 * $Id: red_pitaya_iq_block.v $
 *
 * @brief Red Pitaya IQ demodulator - modulator with variable amplitude and phase
 *
 * @Author Leonhard Neuhaus
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


module red_pitaya_iq_block #(
	  //input filter parameters
	  parameter INPUTFILTERSTAGES    = 1,  //how many cascaded first-order input filters
	  parameter INPUTFILTERSHIFTBITS = 5,  // up to 2^4 different cutoff frequencies
	  parameter INPUTFILTERMINBW = 50,  // minimum realizable filter bandwidth - within factor of 2pi

	  //fgen for sin/cos creation parameters
	  parameter LUTSZ     =  11,   //log2 of number of LUT entries
	  parameter LUTBITS   =  17,   //LUT word size
	  parameter PHASEBITS =  32,   //phase accumulator bits

	  //demodulation/modulation parameters
      parameter SIGNALBITS = 14, //input signal bitwidth
	  parameter LPFBITS    = 24, //internal bitwidths of low-pass filtered quadratures
      parameter GAINBITS  = 18 , //gain bitwidth
   	  parameter SHIFTBITS  = 8 , //binary point of gains

	  //quadrature low-pass parameter
	  parameter QUADRATUREFILTERSTAGES = 2,
      parameter QUADRATUREFILTERSHIFTBITS = 5,
      parameter QUADRATUREFILTERMINBW = 10
)
(
   // data
   input                 clk_i           ,  // clock
   input                 rstn_i          ,  // reset - active low
   input                 sync_i          ,  // synchronization input, active high
   input      [ 14-1: 0] dat_i           ,  // input data
   output     [ 14-1: 0] dat_o           ,  // output data
   output     [ 14-1: 0] signal_o        ,  // output data
   output     [ 14-1: 0] signal2_o       ,  // output data 2 (orthogonal quadrature)

   // communication with PS
   input      [ 16-1: 0] addr,
   input                 wen,
   input                 ren,
   output reg   		 ack,
   output reg [ 32-1: 0] rdata,
   input      [ 32-1: 0] wdata
);

//output states
localparam QUADRATURE    = 4'd0;
localparam OUTPUT_DIRECT = 4'd1;
localparam PFD 			 = 4'd2;
localparam QUADRATURE_HF = 4'd4;

// state registers
reg [4-1:0] output_select;
//reg         on;  //fgen is on; allows to re-synchronize the outputs
wire on;
assign on = sync_i;
reg sin_at_2f; //flag to enable signals at twice the fundamental frequency
reg cos_at_2f; //flag to enable signals at twice the fundamental frequency
reg sin_shifted_at_2f; //flag to enable signals at twice the fundamental frequency
reg cos_shifted_at_2f; //flag to enable signals at twice the fundamental frequency

// function registers
reg [PHASEBITS-1:0] start_phase;
reg [PHASEBITS-1:0] shift_phase;

reg signed [GAINBITS-1:0] g1;
reg signed [GAINBITS-1:0] g2;
reg signed [GAINBITS-1:0] g3;
reg signed [GAINBITS-1:0] g4;

reg [32-1:0] input_filter;
reg [32-1:0] quadrature_filter;

//  System bus connection
always @(posedge clk_i) begin
   if (rstn_i == 1'b0) begin
      //on <= 1'b1; //on by default
      // on is replaced by sync_i
      sin_at_2f <= 1'b0;  //off by default
      cos_at_2f <= 1'b0;  //off by default
      sin_shifted_at_2f <= 1'b0;  //off by default
      cos_shifted_at_2f <= 1'b0;  //off by default
      input_filter <= 32'd0;
      quadrature_filter <= 32'd0;
      start_phase <= {PHASEBITS{1'b0}};
      shift_phase <= {PHASEBITS{1'b0}};
      g1 <= {GAINBITS{1'b0}};
      g2 <= {GAINBITS{1'b0}};
      g3 <= {GAINBITS{1'b0}};
      g4 <= {GAINBITS{1'b0}};
      na_averages = 32'd0;
      na_sleepcycles = 32'd0;
      pfd_on <= 1'b1;
  	  output_select <= QUADRATURE;
   end
   else begin
      if (wen) begin
		 // on was replaced by sync_i
		 // if (addr==16'h100)   {cos_shifted_at_2f,sin_shifted_at_2f,cos_at_2f,sin_at_2f,pfd_on, on}   <= wdata[6-1:0];
		 if (addr==16'h100)   {cos_shifted_at_2f,sin_shifted_at_2f,cos_at_2f,sin_at_2f,pfd_on} <= wdata[6-1:1];
         if (addr==16'h104)   start_phase   <= wdata[PHASEBITS-1:0];
         if (addr==16'h108)   shift_phase   <= wdata[PHASEBITS-1:0];
         if (addr==16'h10C)   output_select <= wdata[4-1:0];
         if (addr==16'h110)   g1 <= wdata[GAINBITS-1:0];
         if (addr==16'h114)   g2 <= wdata[GAINBITS-1:0];
         if (addr==16'h118)   g3 <= wdata[GAINBITS-1:0];
         if (addr==16'h11C)   g4 <= wdata[GAINBITS-1:0];
         if (addr==16'h120)   input_filter  <= wdata;
         if (addr==16'h124)   quadrature_filter  <= wdata;
         if (addr==16'h130)   na_averages <= wdata;
         if (addr==16'h134)   na_sleepcycles <= wdata;
         if (addr==16'h134)   na_sleepcycles <= wdata;
      end

	  casez (addr)
	     16'h100 : begin ack <= wen|ren; rdata <= {{32-6{1'b0}},cos_shifted_at_2f,sin_shifted_at_2f,cos_at_2f,sin_at_2f,pfd_on,on}; end
	     16'h104 : begin ack <= wen|ren; rdata <= {{32-PHASEBITS{1'b0}},start_phase}; end
	     16'h108 : begin ack <= wen|ren; rdata <= {{32-PHASEBITS{1'b0}},shift_phase}; end
	     16'h10C : begin ack <= wen|ren; rdata <= {{32-4{1'b0}},output_select}; end
	     16'h110 : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},g1}; end
	     16'h114 : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},g2}; end
	     16'h118 : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},g3}; end
	     16'h11C : begin ack <= wen|ren; rdata <= {{32-GAINBITS{1'b0}},g4}; end
	     16'h120 : begin ack <= wen|ren; rdata <= input_filter; end
	     16'h124 : begin ack <= wen|ren; rdata <= quadrature_filter; end
	     16'h130 : begin ack <= wen|ren; rdata <= na_averages; end
	     16'h134 : begin ack <= wen|ren; rdata <= na_sleepcycles; end
         16'h140 : begin ack <= wen|ren; rdata <= {do_averaging,iq_i_sum[31-1:0]};end
         16'h144 : begin ack <= wen|ren; rdata <= {do_averaging,iq_i_sum[62-1:31]};end
         16'h148 : begin ack <= wen|ren; rdata <= {do_averaging,iq_q_sum[31-1:0]};end
         16'h14C : begin ack <= wen|ren; rdata <= {do_averaging,iq_q_sum[62-1:31]};end
	     16'h150 : begin ack <= wen|ren; rdata <= {{32-SIGNALBITS{1'b0}},pfd_integral};end

	     16'h200 : begin ack <= wen|ren; rdata <= LUTSZ; end
	     16'h204 : begin ack <= wen|ren; rdata <= LUTBITS; end
	     16'h208 : begin ack <= wen|ren; rdata <= PHASEBITS; end
	     16'h20C : begin ack <= wen|ren; rdata <= GAINBITS; end
	     16'h210 : begin ack <= wen|ren; rdata <= SIGNALBITS; end
	     16'h214 : begin ack <= wen|ren; rdata <= LPFBITS; end
	     16'h218 : begin ack <= wen|ren; rdata <= SHIFTBITS; end
		 16'h220 : begin ack <= wen|ren; rdata <= INPUTFILTERSTAGES; end
	     16'h224 : begin ack <= wen|ren; rdata <= INPUTFILTERSHIFTBITS; end
	     16'h228 : begin ack <= wen|ren; rdata <= INPUTFILTERMINBW; end
	     16'h230 : begin ack <= wen|ren; rdata <= QUADRATUREFILTERSTAGES; end
	     16'h234 : begin ack <= wen|ren; rdata <= QUADRATUREFILTERSHIFTBITS; end
	     16'h238 : begin ack <= wen|ren; rdata <= QUADRATUREFILTERMINBW; end

	     default: begin ack <= wen|ren;  rdata <=  32'h0; end
	  endcase
   end
end


//input pre-filter (typically AC filter)
wire signed [14-1:0] dat_i_filtered;
red_pitaya_filter_block #(
     .STAGES(INPUTFILTERSTAGES),
     .SHIFTBITS(INPUTFILTERSHIFTBITS),
     .SIGNALBITS(14),
     .MINBW(INPUTFILTERMINBW)
  )
  inputfilter
  (
  .clk_i(clk_i),
  .rstn_i(rstn_i),
  .set_filter(input_filter),
  .dat_i(dat_i),
  .dat_o(dat_i_filtered)
  );


//sub-module fgen_block that creates 2 phase-shited sin/cos pairs
wire signed [LUTBITS-1:0] sin;
wire signed [LUTBITS-1:0] cos;
wire signed [LUTBITS-1:0] sin_shifted;
wire signed [LUTBITS-1:0] cos_shifted;

red_pitaya_iq_fgen_block #(
  .LUTSZ        (  LUTSZ      ),
  .LUTBITS      (  LUTBITS    ),
  .PHASEBITS    (  PHASEBITS  )
)
iq_fgen
(
   // data
  .clk_i               (  clk_i          ),  // clock
  .rstn_i              (  rstn_i         ),
  .on                  (  on             ),
  .sin_at_2f           (  sin_at_2f      ),
  .cos_at_2f           (  cos_at_2f      ),
  .sin_shifted_at_2f   (  sin_shifted_at_2f ),
  .cos_shifted_at_2f   (  cos_shifted_at_2f ),
  .start_phase         (  start_phase    ),
  .shift_phase         (  shift_phase    ),
  .sin_o               (  sin            ),
  .cos_o               (  cos            ),
  .sin_shifted_o       (  sin_shifted    ),
  .cos_shifted_o       (  cos_shifted    )
  );


//demodulation
wire signed [LPFBITS-1:0] quadrature1_hf;
wire signed [LPFBITS-1:0] quadrature2_hf;
red_pitaya_iq_demodulator_block #(
        .INBITS   (SIGNALBITS),
        .OUTBITS  (LPFBITS),
        .SINBITS  (LUTBITS),
        .SHIFTBITS (1) //never change unless you know what you are doing!!!
        //This setting of 1 just prevents saturation! especially do not set to SHIFTBITS
        )
    demodulator
    (
        .clk_i (clk_i),
        .sin   (sin_shifted),
        .cos   (cos_shifted),
        .signal_i (dat_i_filtered),
        .signal1_o (quadrature1_hf),
        .signal2_o (quadrature2_hf)
    );

//low-passing
wire signed [LPFBITS-1:0] quadrature1;
wire signed [LPFBITS-1:0] quadrature2;
wire signed [SIGNALBITS-1:0] quadrature1_o;
wire signed [SIGNALBITS-1:0] quadrature2_o;

//option 1: Several low-pass filters without multipliers (bw is power of 2)
red_pitaya_filter_block #(
     .STAGES(QUADRATUREFILTERSTAGES),
     .SHIFTBITS(QUADRATUREFILTERSHIFTBITS),
     .SIGNALBITS(LPFBITS),
     .MINBW(QUADRATUREFILTERMINBW)
  )
  iqfilter [1:0]
  (
   .clk_i     (  {clk_i,clk_i}    ),
   .rstn_i    (  {rstn_i,rstn_i}  ),
   .set_filter(  {quadrature_filter, quadrature_filter}  ),
   .dat_i  ( {quadrature1_hf,quadrature2_hf}  ),
   .dat_o  ( {quadrature1,quadrature2}  )
  );

//modulation, summing and direct output
red_pitaya_iq_modulator_block #(
        .INBITS   (LPFBITS),
        .OUTBITS  (SIGNALBITS),
        .SINBITS  (LUTBITS),
        .GAINBITS (GAINBITS),
        .SHIFTBITS (SHIFTBITS)
    )
    modulator
    (
        .clk_i (clk_i),
        .sin   (sin),
        .cos   (cos),
        .g1      (g1) ,
        .g2      (g2) ,
        .g3      (g3) ,
        .g4      (g4) ,
        .signal1_i (quadrature1),
        .signal2_i (quadrature2),
        .dat_o     (dat_o),
        .signal_q1_o  (quadrature1_o),
        .signal_q2_o  (quadrature2_o)
    );

//NA functionality
reg    do_averaging;
reg signed [62-1:0] iq_i_sum;
reg signed [62-1:0] iq_q_sum;
reg    [32-1:0] na_averages;  //cycles to average over
reg    [32-1:0] na_sleepcycles;  //cycles to wait before averaging starts
reg    [32-1:0] na_averages_remaining;
reg    [32-1:0] na_sleep_remaining;

//last one means iq_channel_1 frequency was changed = trigger event
always @(posedge clk_i) begin
    if (rstn_i == 1'b0) begin //reset
        iq_i_sum <= {62{1'b0}};
        iq_q_sum <= {62{1'b0}};
        na_averages_remaining <= {32{1'b0}};
        na_sleep_remaining <= {32{1'b0}};
        do_averaging <= 1'b0;
    end
    else if (wen && addr[16-1:0]==16'h0108) begin //start new averaging series when iq1 frequency is changed
        iq_i_sum <= {63{1'b0}};
        iq_q_sum <= {63{1'b0}};
        na_averages_remaining <= na_averages;
        na_sleep_remaining <= na_sleepcycles;
        do_averaging <= 1'b1;
    end
    else if (na_averages_remaining == {32{1'b0}} ) begin //stall when averaging has finished
        do_averaging <= 1'b0;
    end
    else if (na_sleep_remaining == {32{1'b0}} ) begin //averaging in progress
        na_averages_remaining <= na_averages_remaining - 32'b1;
        do_averaging <= 1'b1;
        iq_i_sum <= iq_i_sum + quadrature1;
        iq_q_sum <= iq_q_sum + quadrature2;
    end
    else begin  //sleep has not finished yet, count down sleep cycle register
        na_sleep_remaining <= na_sleep_remaining - 32'b1;
        do_averaging <= 1'b1;
    end
end

// pfd functionality (optional)
wire [SIGNALBITS-1:0] pfd_integral;
reg pfd_on;
red_pitaya_pfd_block pfd_block (
	.rstn_i(pfd_on),
	.clk_i (clk_i),
	.s1 (dat_i_filtered[SIGNALBITS-1]), //sign bit of input signal as clock source
	.s2 (sin[LUTBITS-1]), //sign bit of sine reference signal as clock source
	.integral_o(pfd_integral)
);

// output_signal multiplexer
assign signal_o = (output_select==QUADRATURE) ? quadrature1_o
				//: (output_select==QUADRATURE_HF) ? quadrature1_hf[LPFBITS-1:LPFBITS-SIGNALBITS] // maybe for the future
				: (output_select==OUTPUT_DIRECT) ? dat_o
				: (output_select==PFD) ? pfd_integral
				: {SIGNALBITS{1'b0}};

assign signal2_o = quadrature2_o;

endmodule
