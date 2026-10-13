`timescale 1ns / 1ps

/*
 * Two-input fixed-point arithmetic block.
 *
 * Inputs and output are signed Q1.13 values. Coefficients are signed Q8.16.
 * Polynomial exponents are restricted to one or two. Ratio mode contains a
 * thirteen-stage restoring divider: it accepts one sample per clock even
 * though each result takes sixteen clocks to reach the output.
 */
module red_pitaya_arithmetic_block #(
   parameter SIGNAL_BITS = 14,
   parameter COEFFICIENT_BITS = 24,
   parameter COEFFICIENT_SHIFT = 16,
   parameter MAX_INPUT_DELAY = 7
)(
   input                              clk_i,
   input                              rstn_i,
   input signed [SIGNAL_BITS-1:0]     dat_a_i,
   input signed [SIGNAL_BITS-1:0]     dat_b_i,
   output signed [SIGNAL_BITS-1:0]    dat_o,
   input [15:0]                       addr,
   input                              wen,
   input                              ren,
   output reg                         ack,
   output reg [31:0]                  rdata,
   input [31:0]                       wdata
);

localparam OP_POLYNOMIAL = 2'd0;
localparam OP_PRODUCT = 2'd1;
localparam OP_RATIO = 2'd2;
localparam PRODUCT_BITS = 2*SIGNAL_BITS;
localparam COEFFICIENT_PRODUCT_BITS = SIGNAL_BITS+COEFFICIENT_BITS;
localparam RATIO_REMAINDER_BITS = COEFFICIENT_PRODUCT_BITS;
localparam RATIO_QUOTIENT_BITS = SIGNAL_BITS-1;
localparam RATIO_STAGES = RATIO_QUOTIENT_BITS;
localparam [31:0] ABI_VERSION = 32'h41524901; // "ARI", register-map revision 1

reg [1:0] operation;
reg signed [COEFFICIENT_BITS-1:0] coefficient_a;
reg signed [COEFFICIENT_BITS-1:0] coefficient_b;
reg square_a;
reg square_b;
reg [2:0] input_delay_a;
reg [2:0] input_delay_b;
reg [SIGNAL_BITS-1:0] denominator_min;
reg denominator_too_small;

always @(posedge clk_i) begin
   if (!rstn_i) begin
      operation <= OP_POLYNOMIAL;
      coefficient_a <= 24'sh010000;
      coefficient_b <= {COEFFICIENT_BITS{1'b0}};
      square_a <= 1'b0;
      square_b <= 1'b0;
      input_delay_a <= 3'd0;
      input_delay_b <= 3'd0;
      denominator_min <= {{SIGNAL_BITS-1{1'b0}}, 1'b1};
      ack <= 1'b0;
      rdata <= 32'd0;
   end else begin
      if (wen) begin
         if (addr == 16'h0100) operation <= wdata[1:0];
         if (addr == 16'h0104) coefficient_a <= wdata[COEFFICIENT_BITS-1:0];
         if (addr == 16'h0108) coefficient_b <= wdata[COEFFICIENT_BITS-1:0];
         if (addr == 16'h010C) square_a <= wdata[0];
         if (addr == 16'h0110) square_b <= wdata[0];
         if (addr == 16'h0114) input_delay_a <= wdata[2:0];
         if (addr == 16'h0118) input_delay_b <= wdata[2:0];
         if (addr == 16'h011C)
            denominator_min <= (wdata[SIGNAL_BITS-1:0] == 0) ?
                               {{SIGNAL_BITS-1{1'b0}}, 1'b1} :
                               wdata[SIGNAL_BITS-1:0];
      end
      ack <= wen | ren;
      case (addr)
         16'h0100: rdata <= {{30{1'b0}}, operation};
         16'h0104: rdata <= {{32-COEFFICIENT_BITS{1'b0}}, coefficient_a};
         16'h0108: rdata <= {{32-COEFFICIENT_BITS{1'b0}}, coefficient_b};
         16'h010C: rdata <= {{31{1'b0}}, square_a};
         16'h0110: rdata <= {{31{1'b0}}, square_b};
         16'h0114: rdata <= {{29{1'b0}}, input_delay_a};
         16'h0118: rdata <= {{29{1'b0}}, input_delay_b};
         16'h011C: rdata <= {{32-SIGNAL_BITS{1'b0}}, denominator_min};
         16'h0120: rdata <= {{31{1'b0}}, denominator_too_small};
         16'h0200: rdata <= ABI_VERSION;
         16'h0204: rdata <= COEFFICIENT_BITS;
         16'h0208: rdata <= COEFFICIENT_SHIFT;
         16'h020C: rdata <= 32'd5;
         16'h0210: rdata <= 32'd17;
         default: rdata <= 32'd0;
      endcase
   end
end

reg signed [SIGNAL_BITS-1:0] delay_pipe_a [0:MAX_INPUT_DELAY-1];
reg signed [SIGNAL_BITS-1:0] delay_pipe_b [0:MAX_INPUT_DELAY-1];
integer delay_index;
always @(posedge clk_i) begin
   if (!rstn_i) begin
      for (delay_index = 0; delay_index < MAX_INPUT_DELAY; delay_index = delay_index+1) begin
         delay_pipe_a[delay_index] <= {SIGNAL_BITS{1'b0}};
         delay_pipe_b[delay_index] <= {SIGNAL_BITS{1'b0}};
      end
   end else begin
      delay_pipe_a[0] <= dat_a_i;
      delay_pipe_b[0] <= dat_b_i;
      for (delay_index = 1; delay_index < MAX_INPUT_DELAY; delay_index = delay_index+1) begin
         delay_pipe_a[delay_index] <= delay_pipe_a[delay_index-1];
         delay_pipe_b[delay_index] <= delay_pipe_b[delay_index-1];
      end
   end
end

wire signed [SIGNAL_BITS-1:0] delayed_a =
   (input_delay_a == 0) ? dat_a_i : delay_pipe_a[input_delay_a-1'b1];
wire signed [SIGNAL_BITS-1:0] delayed_b =
   (input_delay_b == 0) ? dat_b_i : delay_pipe_b[input_delay_b-1'b1];

function signed [SIGNAL_BITS-1:0] saturate_signal;
   input signed [39:0] value;
   begin
      if (value > 40'sd8191)
         saturate_signal = 14'sh1FFF;
      else if (value < -40'sd8192)
         saturate_signal = -14'sd8192;
      else
         saturate_signal = value[SIGNAL_BITS-1:0];
   end
endfunction

// Common short datapath. Registering the inputs/products before the
// coefficient multipliers keeps both DSP stages off the routing mux path.
reg signed [SIGNAL_BITS-1:0] input_a_reg;
reg signed [SIGNAL_BITS-1:0] input_b_reg;
reg signed [PRODUCT_BITS-1:0] square_a_product;
reg signed [PRODUCT_BITS-1:0] square_b_product;
reg signed [PRODUCT_BITS-1:0] input_product;
reg signed [SIGNAL_BITS-1:0] power_a;
reg signed [SIGNAL_BITS-1:0] power_b;
reg signed [COEFFICIENT_PRODUCT_BITS-1:0] coefficient_product_a;
reg signed [COEFFICIENT_PRODUCT_BITS-1:0] coefficient_product_b;
reg signed [SIGNAL_BITS-1:0] short_output;

wire signed [39:0] square_a_scaled = $signed(square_a_product) >>> 13;
wire signed [39:0] square_b_scaled = $signed(square_b_product) >>> 13;
wire signed [39:0] input_product_scaled = $signed(input_product) >>> 13;
wire signed [39:0] coefficient_sum =
   $signed({{40-COEFFICIENT_PRODUCT_BITS{coefficient_product_a[COEFFICIENT_PRODUCT_BITS-1]}}, coefficient_product_a}) +
   $signed({{40-COEFFICIENT_PRODUCT_BITS{coefficient_product_b[COEFFICIENT_PRODUCT_BITS-1]}}, coefficient_product_b});
wire signed [39:0] short_result_scaled = coefficient_sum >>> COEFFICIENT_SHIFT;

always @(posedge clk_i) begin
   if (!rstn_i) begin
      input_a_reg <= 0;
      input_b_reg <= 0;
      square_a_product <= 0;
      square_b_product <= 0;
      input_product <= 0;
      power_a <= 0;
      power_b <= 0;
      coefficient_product_a <= 0;
      coefficient_product_b <= 0;
      short_output <= 0;
   end else begin
      input_a_reg <= delayed_a;
      input_b_reg <= delayed_b;
      // Use the registered inputs here. Bypassing them would put the DSP48
      // input setup directly behind the global DSP routing selector.
      square_a_product <= $signed(input_a_reg) * $signed(input_a_reg);
      square_b_product <= $signed(input_b_reg) * $signed(input_b_reg);
      input_product <= $signed(input_a_reg) * $signed(input_b_reg);

      if (operation == OP_PRODUCT) begin
         power_a <= saturate_signal(input_product_scaled);
         power_b <= 0;
      end else begin
         power_a <= square_a ? saturate_signal(square_a_scaled) : input_a_reg;
         power_b <= square_b ? saturate_signal(square_b_scaled) : input_b_reg;
      end

      coefficient_product_a <= $signed(power_a) * $signed(coefficient_a);
      coefficient_product_b <= $signed(power_b) * $signed(coefficient_b);
      short_output <= saturate_signal(short_result_scaled);
   end
end

// Ratio mode computes coefficient_a*input_a/input_b without prematurely
// saturating the intermediate ratio. The coefficient product is Q*.29; the
// divisor is shifted by three so the quotient is directly a Q1.13 signal.
wire signed [COEFFICIENT_PRODUCT_BITS-1:0] ratio_product_wire =
   $signed(input_a_reg) * $signed(coefficient_a);
reg signed [COEFFICIENT_PRODUCT_BITS-1:0] ratio_product;
reg [SIGNAL_BITS-1:0] ratio_denominator;
reg ratio_sign;

wire [COEFFICIENT_PRODUCT_BITS-1:0] ratio_product_abs =
   ratio_product[COEFFICIENT_PRODUCT_BITS-1] ? -ratio_product : ratio_product;
wire [SIGNAL_BITS-1:0] ratio_denominator_abs =
   input_b_reg[SIGNAL_BITS-1] ? -input_b_reg : input_b_reg;

reg [RATIO_REMAINDER_BITS-1:0] remainder_pipe [0:RATIO_STAGES];
reg [SIGNAL_BITS+2:0] divisor_pipe [0:RATIO_STAGES];
reg [RATIO_QUOTIENT_BITS-1:0] quotient_pipe [0:RATIO_STAGES];
reg ratio_sign_pipe [0:RATIO_STAGES];
reg ratio_saturate_pipe [0:RATIO_STAGES];
reg ratio_small_pipe [0:RATIO_STAGES];
integer ratio_index;

wire ratio_denominator_small = ratio_denominator < denominator_min;
wire [RATIO_REMAINDER_BITS-1:0] ratio_saturation_limit =
   {{RATIO_REMAINDER_BITS-(SIGNAL_BITS+16){1'b0}}, ratio_denominator, 16'b0};

always @(posedge clk_i) begin
   if (!rstn_i) begin
      ratio_product <= 0;
      ratio_denominator <= 0;
      ratio_sign <= 0;
      remainder_pipe[0] <= 0;
      divisor_pipe[0] <= 0;
      quotient_pipe[0] <= 0;
      ratio_sign_pipe[0] <= 0;
      ratio_saturate_pipe[0] <= 0;
      ratio_small_pipe[0] <= 0;
   end else begin
      ratio_product <= ratio_product_wire;
      ratio_denominator <= ratio_denominator_abs;
      ratio_sign <= input_a_reg[SIGNAL_BITS-1] ^ input_b_reg[SIGNAL_BITS-1] ^ coefficient_a[COEFFICIENT_BITS-1];
      remainder_pipe[0] <= ratio_product_abs;
      divisor_pipe[0] <= {ratio_denominator, 3'b0};
      quotient_pipe[0] <= 0;
      ratio_sign_pipe[0] <= ratio_sign;
      ratio_small_pipe[0] <= ratio_denominator_small;
      ratio_saturate_pipe[0] <= ratio_denominator_small |
                                (ratio_product_abs >= ratio_saturation_limit);
   end
end

genvar ratio_stage;
generate
   for (ratio_stage = 0; ratio_stage < RATIO_STAGES; ratio_stage = ratio_stage+1) begin: ratio_divider
      wire [RATIO_REMAINDER_BITS-1:0] shifted_divisor =
         {{RATIO_REMAINDER_BITS-(SIGNAL_BITS+3){1'b0}}, divisor_pipe[ratio_stage]} <<
         (RATIO_QUOTIENT_BITS-1-ratio_stage);
      always @(posedge clk_i) begin
         if (!rstn_i) begin
            remainder_pipe[ratio_stage+1] <= 0;
            divisor_pipe[ratio_stage+1] <= 0;
            quotient_pipe[ratio_stage+1] <= 0;
            ratio_sign_pipe[ratio_stage+1] <= 0;
            ratio_saturate_pipe[ratio_stage+1] <= 0;
            ratio_small_pipe[ratio_stage+1] <= 0;
         end else begin
            divisor_pipe[ratio_stage+1] <= divisor_pipe[ratio_stage];
            ratio_sign_pipe[ratio_stage+1] <= ratio_sign_pipe[ratio_stage];
            ratio_saturate_pipe[ratio_stage+1] <= ratio_saturate_pipe[ratio_stage];
            ratio_small_pipe[ratio_stage+1] <= ratio_small_pipe[ratio_stage];
            quotient_pipe[ratio_stage+1] <= quotient_pipe[ratio_stage];
            if (remainder_pipe[ratio_stage] >= shifted_divisor) begin
               remainder_pipe[ratio_stage+1] <= remainder_pipe[ratio_stage] - shifted_divisor;
               quotient_pipe[ratio_stage+1][RATIO_QUOTIENT_BITS-1-ratio_stage] <= 1'b1;
            end else begin
               remainder_pipe[ratio_stage+1] <= remainder_pipe[ratio_stage];
               quotient_pipe[ratio_stage+1][RATIO_QUOTIENT_BITS-1-ratio_stage] <= 1'b0;
            end
         end
      end
   end
endgenerate

reg signed [SIGNAL_BITS-1:0] ratio_output;
always @(posedge clk_i) begin
   if (!rstn_i) begin
      ratio_output <= 0;
      denominator_too_small <= 1'b0;
   end else begin
      denominator_too_small <= (operation == OP_RATIO) &&
                               ratio_small_pipe[RATIO_STAGES];
      if (ratio_small_pipe[RATIO_STAGES] && (quotient_pipe[RATIO_STAGES] == 0) &&
          (remainder_pipe[RATIO_STAGES] == 0))
         ratio_output <= 0;
      else if (ratio_saturate_pipe[RATIO_STAGES])
         ratio_output <= ratio_sign_pipe[RATIO_STAGES] ? -14'sd8192 : 14'sd8191;
      else if (ratio_sign_pipe[RATIO_STAGES])
         ratio_output <= -$signed({1'b0, quotient_pipe[RATIO_STAGES]});
      else
         ratio_output <= $signed({1'b0, quotient_pipe[RATIO_STAGES]});
   end
end

assign dat_o = (operation == OP_RATIO) ? ratio_output : short_output;

endmodule
