// ──────────────────────────────────────────────────────────────
// Minimal RISC-style processor top-level
// Shows: FSM, ALU instance, regfile instance, multiplier,
//        FIFO (instruction buffer), barrel shifter
// ──────────────────────────────────────────────────────────────
module processor #(parameter WIDTH = 32) (
    input  wire             clk,
    input  wire             rst,
    input  wire [WIDTH-1:0] instr_in,
    input  wire             instr_valid,
    output wire [WIDTH-1:0] result_out,
    output wire             result_valid
);

    // ── Instruction FIFO ──────────────────────────────────────
    reg  [WIDTH-1:0] fifo_mem [0:7];
    reg  [2:0]       wr_ptr, rd_ptr;
    wire             fifo_full  = (wr_ptr[2] != rd_ptr[2]) && (wr_ptr[1:0] == rd_ptr[1:0]);
    wire             fifo_empty = (wr_ptr == rd_ptr);

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
        end else begin
            if (instr_valid && !fifo_full) begin
                fifo_mem[wr_ptr[1:0]] <= instr_in;
                wr_ptr <= wr_ptr + 1;
            end
        end
    end

    // ── Instruction decode ────────────────────────────────────
    wire [WIDTH-1:0] instr  = fifo_mem[rd_ptr[1:0]];
    wire [5:0]  opcode = instr[31:26];
    wire [4:0]  rs1    = instr[25:21];
    wire [4:0]  rs2    = instr[20:16];
    wire [4:0]  rd     = instr[15:11];
    wire [3:0]  alu_op = instr[7:4];
    wire [4:0]  shamt  = instr[4:0];

    // ── Register file ─────────────────────────────────────────
    wire [WIDTH-1:0] rdata1, rdata2;
    wire             reg_we;

    regfile #(.REGS(32), .WIDTH(WIDTH)) u_regfile (
        .clk    (clk),
        .we     (reg_we),
        .rs1    (rs1),
        .rs2    (rs2),
        .rd     (rd),
        .wdata  (wb_data),
        .rdata1 (rdata1),
        .rdata2 (rdata2)
    );

    // ── ALU ───────────────────────────────────────────────────
    wire [WIDTH-1:0] alu_result;
    wire             alu_zero, alu_overflow, alu_negative;

    alu #(.WIDTH(WIDTH)) u_alu (
        .a        (rdata1),
        .b        (rdata2),
        .op       (alu_op),
        .result   (alu_result),
        .zero     (alu_zero),
        .overflow (alu_overflow),
        .negative (alu_negative)
    );

    // ── Multiplier (separate, for MUL instruction) ────────────
    wire [2*WIDTH-1:0] mul_result;
    wire               mul_valid;

    multiplier #(.WIDTH(WIDTH)) u_mul (
        .clk     (clk),
        .rst     (rst),
        .a       (rdata1),
        .b       (rdata2),
        .product (mul_result),
        .valid   (mul_valid)
    );

    // ── Barrel shifter ────────────────────────────────────────
    wire [WIDTH-1:0] shift_result;
    assign shift_result = (opcode[0]) ? (rdata1 >> shamt)
                                      : (rdata1 << shamt);

    // ── Write-back MUX ────────────────────────────────────────
    wire [WIDTH-1:0] wb_data;
    assign wb_data = (opcode == 6'b000010) ? mul_result[WIDTH-1:0]
                   : (opcode == 6'b000011) ? shift_result
                   : alu_result;
    assign reg_we  = !fifo_empty;

    // ── Control FSM ───────────────────────────────────────────
    reg [2:0] state, next_state;
    localparam IDLE   = 3'd0;
    localparam FETCH  = 3'd1;
    localparam DECODE = 3'd2;
    localparam EXEC   = 3'd3;
    localparam WB     = 3'd4;

    always @(posedge clk or posedge rst) begin
        if (rst) state <= IDLE;
        else     state <= next_state;
    end

    always @(*) begin
        case (state)
            IDLE:   next_state = fifo_empty ? IDLE : FETCH;
            FETCH:  next_state = DECODE;
            DECODE: next_state = EXEC;
            EXEC:   next_state = WB;
            WB:     next_state = IDLE;
            default:next_state = IDLE;
        endcase
    end

    // ── Advance read pointer in WB state ─────────────────────
    always @(posedge clk or posedge rst) begin
        if (rst)
            rd_ptr <= 0;
        else if (state == WB && !fifo_empty)
            rd_ptr <= rd_ptr + 1;
    end

    // ── Outputs ───────────────────────────────────────────────
    assign result_out   = wb_data;
    assign result_valid = (state == WB);

endmodule
