module tb;
reg clk=0, rst=1, en=0;
wire [7:0] count;
counter dut(clk,rst,en,count);
always #5 clk=~clk;
initial begin
  @(negedge clk); rst=0; en=1;
  repeat(260) @(negedge clk);
  if (count !== 8'd4) $fatal(1,"counter wrap mismatch");
  en=0; repeat(3) @(negedge clk);
  if (count !== 8'd4) $fatal(1,"counter enable mismatch");
  rst=1; @(negedge clk);
  if (count !== 0) $fatal(1,"counter reset mismatch");
  $display("COUNTER_PASS checks=3"); $finish;
end
initial begin #10000; $fatal(1,"TIMEOUT"); end
endmodule
