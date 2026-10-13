`timescale 1ns / 1ps

module red_pitaya_arithmetic_block_tb;
   reg clk = 1'b0;
   reg rstn = 1'b0;
   reg signed [13:0] input_a = 0;
   reg signed [13:0] input_b = 0;
   wire signed [13:0] output_signal;
   reg [15:0] addr = 0;
   reg wen = 0;
   reg ren = 0;
   reg [31:0] wdata = 0;
   wire ack;
   wire [31:0] rdata;
   integer failures = 0;

   always #4 clk = ~clk;

   red_pitaya_arithmetic_block dut (
      .clk_i(clk),
      .rstn_i(rstn),
      .dat_a_i(input_a),
      .dat_b_i(input_b),
      .dat_o(output_signal),
      .addr(addr),
      .wen(wen),
      .ren(ren),
      .ack(ack),
      .rdata(rdata),
      .wdata(wdata)
   );

   task automatic write_register;
      input [15:0] register_address;
      input [31:0] register_value;
      begin
         @(negedge clk);
         addr = register_address;
         wdata = register_value;
         wen = 1'b1;
         @(negedge clk);
         wen = 1'b0;
      end
   endtask

   task automatic check_output;
      input integer expected;
      input integer tolerance;
      input [127:0] label;
      integer error;
      begin
         error = $signed(output_signal) - expected;
         if (error < 0)
            error = -error;
         if (error > tolerance) begin
            $display("%0s mismatch: expected=%0d observed=%0d", label, expected, $signed(output_signal));
            failures = failures + 1;
         end
      end
   endtask

   initial begin
      repeat (3) @(posedge clk);
      rstn = 1'b1;

      // 1*0.25 + 0.5*(0.5^2) = 0.375 = 3072 Q1.13 counts.
      input_a = 14'sd2048;
      input_b = 14'sd4096;
      write_register(16'h0104, 24'h010000);
      write_register(16'h0108, 24'h008000);
      write_register(16'h010C, 0);
      write_register(16'h0110, 1);
      write_register(16'h0100, 0);
      repeat (8) @(posedge clk);
      #1 check_output(3072, 2, "polynomial");

      // 2*0.25*0.5 = 0.25 = 2048 counts.
      write_register(16'h0104, 24'h020000);
      write_register(16'h0100, 1);
      repeat (8) @(posedge clk);
      #1 check_output(2048, 2, "product");

      // 0.5*0.25/0.5 = 0.25 = 2048 counts.
      write_register(16'h0104, 24'h008000);
      write_register(16'h0100, 2);
      repeat (20) @(posedge clk);
      #1 check_output(2048, 2, "ratio");

      // Sign is carried alongside every divider pipeline sample.
      input_a = -14'sd2048;
      repeat (20) @(posedge clk);
      #1 check_output(-2048, 2, "negative ratio");

      // A nonzero numerator divided by zero saturates and raises status.
      input_a = 14'sd2048;
      input_b = 0;
      repeat (20) @(posedge clk);
      #1 check_output(8191, 0, "protected ratio");
      addr = 16'h0120;
      ren = 1'b1;
      @(posedge clk);
      #1;
      if (rdata[0] !== 1'b1) begin
         $display("Denominator protection status was not asserted");
         failures = failures + 1;
      end
      ren = 1'b0;

      if (failures == 0)
         $display("ARITHMETIC_TEST_PASS");
      else
         $fatal(1, "ARITHMETIC_TEST_FAIL: %0d failure(s)", failures);
      $finish;
   end
endmodule
