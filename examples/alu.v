// ──────────────────────────────────────────────────────────────
// 32-bit ALU with comparator, shifter, and output mux
// ──────────────────────────────────────────────────────────────
module alu #(parameter WIDTH = 32) (
    input  wire [WIDTH-1:0] a,
    input  wire [WIDTH-1:0] b,
    input  wire [3:0]       op,
    output reg  [WIDTH-1:0] result,
    output wire             zero,
    output wire             overflow,
    output wire             negative
);
    // ── Arithmetic unit ───────────────────────────────────────
    wire [WIDTH-1:0] sum        = a + b;
    wire [WIDTH-1:0] difference = a - b;
    wire [WIDTH-1:0] product    = a * b;

    // ── Logic unit ────────────────────────────────────────────
    wire [WIDTH-1:0] bit_and = a & b;
    wire [WIDTH-1:0] bit_or  = a | b;
    wire [WIDTH-1:0] bit_xor = a ^ b;
    wire [WIDTH-1:0] bit_not = ~a;

    // ── Shift unit ────────────────────────────────────────────
    wire [WIDTH-1:0] shl = a << b[4:0];
    wire [WIDTH-1:0] shr = a >> b[4:0];
    wire [WIDTH-1:0] sar = $signed(a) >>> b[4:0];

    // ── Comparator ────────────────────────────────────────────
    wire eq  = (a == b);
    wire lt  = ($signed(a) < $signed(b));
    wire ltu = (a < b);

    // ── Output MUX (op select) ────────────────────────────────
    always @(*) begin
        case (op)
            4'b0000: result = sum;
            4'b0001: result = difference;
            4'b0010: result = product;
            4'b0011: result = bit_and;
            4'b0100: result = bit_or;
            4'b0101: result = bit_xor;
            4'b0110: result = bit_not;
            4'b0111: result = shl;
            4'b1000: result = shr;
            4'b1001: result = sar;
            4'b1010: result = {{(WIDTH-1){1'b0}}, eq};
            4'b1011: result = {{(WIDTH-1){1'b0}}, lt};
            4'b1100: result = {{(WIDTH-1){1'b0}}, ltu};
            default: result = {WIDTH{1'b0}};
        endcase
    end

    // ── Status flags ──────────────────────────────────────────
    assign zero     = (result == 0);
    assign negative = result[WIDTH-1];
    assign overflow = (op == 4'b0000) ? (a[WIDTH-1] == b[WIDTH-1]) && (result[WIDTH-1] != a[WIDTH-1])
                    : (op == 4'b0001) ? (a[WIDTH-1] != b[WIDTH-1]) && (result[WIDTH-1] != a[WIDTH-1])
                    : 1'b0;
endmodule


// ──────────────────────────────────────────────────────────────
// Register File (32 × 32-bit)
// ──────────────────────────────────────────────────────────────
module regfile #(parameter REGS = 32, parameter WIDTH = 32) (
    input  wire                   clk,
    input  wire                   we,
    input  wire [$clog2(REGS)-1:0] rs1, rs2, rd,
    input  wire [WIDTH-1:0]       wdata,
    output wire [WIDTH-1:0]       rdata1,
    output wire [WIDTH-1:0]       rdata2
);
    reg [WIDTH-1:0] mem [0:REGS-1];

    // Write port (synchronous)
    always @(posedge clk) begin
        if (we && rd != 0)
            mem[rd] <= wdata;
    end

    // Read ports (asynchronous, x0 always 0)
    assign rdata1 = (rs1 == 0) ? 0 : mem[rs1];
    assign rdata2 = (rs2 == 0) ? 0 : mem[rs2];
endmodule
