// ──────────────────────────────────────────────────────────────
// 8×8 Booth-style multiplier with pipeline register
// ──────────────────────────────────────────────────────────────
module multiplier #(parameter WIDTH = 8) (
    input  wire              clk,
    input  wire              rst,
    input  wire [WIDTH-1:0]  a,
    input  wire [WIDTH-1:0]  b,
    output reg  [2*WIDTH-1:0] product,
    output reg               valid
);
    wire [2*WIDTH-1:0] result;

    // Partial product generator — behavioral multiply
    assign result = a * b;

    // Pipeline register
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            product <= 0;
            valid   <= 0;
        end else begin
            product <= result;
            valid   <= 1;
        end
    end
endmodule


// ──────────────────────────────────────────────────────────────
// Full Adder — basic cell used inside the multiplier
// ──────────────────────────────────────────────────────────────
module full_adder (
    input  wire a,
    input  wire b,
    input  wire cin,
    output wire sum,
    output wire cout
);
    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (b & cin) | (a & cin);
endmodule


// ──────────────────────────────────────────────────────────────
// Half Adder
// ──────────────────────────────────────────────────────────────
module half_adder (
    input  wire a,
    input  wire b,
    output wire sum,
    output wire cout
);
    assign sum  = a ^ b;
    assign cout = a & b;
endmodule


// ──────────────────────────────────────────────────────────────
// 4-bit Ripple-Carry Adder (structural, using full_adder)
// ──────────────────────────────────────────────────────────────
module rca4 (
    input  wire [3:0] a,
    input  wire [3:0] b,
    input  wire       cin,
    output wire [3:0] sum,
    output wire       cout
);
    wire c1, c2, c3;

    full_adder fa0 (.a(a[0]), .b(b[0]), .cin(cin), .sum(sum[0]), .cout(c1));
    full_adder fa1 (.a(a[1]), .b(b[1]), .cin(c1),  .sum(sum[1]), .cout(c2));
    full_adder fa2 (.a(a[2]), .b(b[2]), .cin(c2),  .sum(sum[2]), .cout(c3));
    full_adder fa3 (.a(a[3]), .b(b[3]), .cin(c3),  .sum(sum[3]), .cout(cout));
endmodule
