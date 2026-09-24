module test (
input clk,
input rst
);
always @(posedge clk) begin
if(rst)
out <= 0;
else begin
out <= 1;
end
end
endmodule