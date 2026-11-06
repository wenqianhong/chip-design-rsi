// Original engineering fixture for tool acceptance, not a CPU benchmark.
module counter(input clk, input rst, input en, output reg [7:0] count = 0);
always @(posedge clk)
  if (rst) count <= 0;
  else if (en) count <= count + 1;
`ifdef FORMAL
reg past_valid = 0;
always @(posedge clk) begin
  past_valid <= 1;
  if (past_valid) begin
    if ($past(rst)) assert(count == 0);
    else if ($past(en)) assert(count == $past(count) + 8'd1);
    else assert(count == $past(count));
  end
end
`endif
endmodule
