`default_nettype none

module tqvp_byte_fir (
    input         clk,
    input         rst_n,

    input  [7:0]  ui_in,       // Not used here (but readable)
    output [7:0]  uo_out,      // FIR output mirrored to PMOD

    input  [3:0]  address,     // Local peripheral address
    input         data_write,  // Write strobe
    input  [7:0]  data_in,     // Data written

    output [7:0]  data_out     // Data read
);

    // Registers
    reg [7:0] control;        // bit0 = enable
    reg [7:0] coeff [0:3];    // coefficients h0..h3
    reg [7:0] samples [0:3];  // delay line x0..x3
    reg [7:0] output_val;     // FIR output

    // Internal multiply-accumulate
    wire [15:0] prod0 = coeff[0] * samples[0];
    wire [15:0] prod1 = coeff[1] * samples[1];
    wire [15:0] prod2 = coeff[2] * samples[2];
    wire [15:0] prod3 = coeff[3] * samples[3];
    wire [17:0] sum   = prod0 + prod1 + prod2 + prod3;

    // Sequential logic for writes and updates
    integer i;
    always @(posedge clk) begin
        if (!rst_n) begin
            control    <= 8'b0;
            coeff[0]  <= 8'd64;  // Default: average (64/256 each)
            coeff[1]  <= 8'd64;
            coeff[2]  <= 8'd64;
            coeff[3]  <= 8'd64;
            for (i=0; i<4; i=i+1)
                samples[i] <= 8'b0;
            output_val <= 8'b0;
        end else begin
            if (data_write) begin
                case (address)
                    4'h0: control   <= data_in;         // control
                    4'h1: coeff[0]  <= data_in;         // h0
                    4'h2: coeff[1]  <= data_in;         // h1
                    4'h3: coeff[2]  <= data_in;         // h2
                    4'h4: coeff[3]  <= data_in;         // h3
                    4'h5: begin                         // input sample
                        samples[3] <= samples[2];
                        samples[2] <= samples[1];
                        samples[1] <= samples[0];
                        samples[0] <= data_in;
                        if (control[0]) begin
                            output_val <= sum[15:8];    // >>8 scaling
                        end
                    end
                    default: ; // ignore
                endcase
            end
        end
    end

    // --- Combinational readback mux ---
    assign data_out = (address == 4'h0) ? control     :
                      (address == 4'h1) ? coeff[0]    :
                      (address == 4'h2) ? coeff[1]    :
                      (address == 4'h3) ? coeff[2]    :
                      (address == 4'h4) ? coeff[3]    :
                      (address == 4'h5) ? samples[0]  : // latest input
                      (address == 4'h6) ? output_val  :
                      (address == 4'h7) ? ui_in       : // optional: expose ui_in
                      8'h0;

    // --- Drive PMOD output ---
    assign uo_out = output_val;

endmodule
