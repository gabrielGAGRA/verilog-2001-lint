# Verilog-2001 Synthesizable RTL Style & Engineering Guide

---

## 1. Conformance Terminology

* ***must*** / ***must not***: Absolute requirement or prohibition.
* ***may***: Permitted optional action.

---

## 2. File Organization & Directives

1. **File Extension & Modules**:
   * Hardware modules ***must*** use the `.v` extension. Header files ***must*** use `.vh`.
   * SystemVerilog extensions (`.sv`, `.svh`) ***must not*** be used.
   * Every `.v` file ***must*** contain exactly one module whose name matches the file basename.
   * Top-level wrappers ***must*** be named `<design>_top.v`.

2. **Nettype Hygiene**:
   * Every file ***must*** declare `` `default_nettype none `` prior to module declaration to disallow implicit 1-bit wire inference on typos.
   * Every `.v` file ***must*** restore `` `default_nettype wire `` immediately following `endmodule`.

3. **Include Guards**:
   * Header files (`.vh`) ***must*** include preprocessor guards:
     ```verilog
     `ifndef MY_HEADER_VH
     `define MY_HEADER_VH
     // Definitions
     `endif
     ```

4. **File Header**:
   * Every file ***must*** start with a descriptive header comment documenting module intent, clocking assumptions, and operation.

---

## 3. Formatting & Code Aesthetics

1. **Indentation**: Exactly 2 spaces per indentation level. Hard tabs ***must not*** be used.
2. **Line Length**: Lines ***should*** be kept under 100 characters. Continuations indent by 4 spaces.
3. **Line Endings**: POSIX LF (`\n`). CRLF line endings ***must not*** be committed.
4. **Begin / End Alignment**:
   * `begin` ***must*** be on the same line as the triggering keyword (`if (...) begin`, `always @* begin`).
   * `end` ***must*** occupy its own line.
   * Conditionals chaining `else` ***must*** use `end else begin`.
5. **Preprocessor Directives**: Branching preprocessor directives (`` `ifdef ``, `` `else ``, `` `endif ``) ***must*** be left-aligned at column 0.
6. **Spacing**: Control keywords (`if`, `for`, `while`, `case`) ***must*** be followed by a space before the open parenthesis.

---

## 4. Identifiers & Naming Conventions

1. **Signals, Ports, and Modules**:
   * Identifiers ***must*** use `lower_snake_case` (e.g., `data_in`, `fifo_full`, `tx_shift_reg`).
   * Suffixes ending in `_<digit>` (e.g. `data_1`) are prohibited. Use pipeline stage suffixes (`data_d1`) or unpacked arrays.
2. **Parameters & Local Constants**:
   * Parameters and localparams ***must*** use `UpperCamelCase` (e.g., `DataWidth`, `BaudRate`).
   * FSM state constants ***must*** be declared with `localparam` and use `kUpperCamelCase` (e.g., `kIdle`, `kWaitReady`, `kTxByte`).
3. **Clocks and Resets**:
   * Primary system clock ***must*** be named `clk` (or `<domain>_clk` for multi-clock systems).
   * Active-high synchronous reset ***must*** be named `rst`.
   * Active-high asynchronous reset ***must*** be named `arst`.
   * Active-low reset inputs from hardware pins ***must*** end in `_n` and be inverted immediately at top-level (`wire rst = ~rst_n;`).
4. **Macros**:
   * Global macro definitions ***must*** use `ALL_CAPS`.
   * File-local macros in `.v` files ***must*** start with a single underscore (`_MY_LOCAL_MACRO`) and ***must*** be undefined with `` `undef `` before file end.

---

## 5. Module Interfaces & Instantiation

1. **ANSI Port Headers**:
   * Port declarations ***must*** use ANSI style with explicit direction, type, signedness, and bit ranges:
     ```verilog
     module counter #(
       parameter Width = 8
     ) (
       input  wire             clk,
       input  wire             rst,
       input  wire             en,
       output reg  [Width-1:0] count
     );
     ```
2. **Port Ordering**: `clk` ***must*** appear first, followed by reset (`rst`/`arst`), flow control, data, and status.
3. **No Default Input Values**: Default input port values in declarations (e.g. `input wire in_val = 1'b0`) are prohibited.
4. **Named Connection**:
   * Submodule instantiations and parameter overrides ***must*** use explicit named binding:
     ```verilog
     counter #(.Width(16)) counter_inst (
       .clk(clk),
       .rst(rst),
       .en(en),
       .count(count_val)
     );
     ```
   * Positional port binding and `defparam` ***must not*** be used.
5. **No Floating Inputs**: Unconnected inputs ***must not*** be left floating (`.in_val()`); tie them off explicitly to sized constants.

---

## 6. Procedural Logic & FSM Standards

1. **Assignment Discipline**:
   * Clocked sequential blocks ***must*** use non-blocking assignments exclusively (`<=`).
   * Combinational blocks ***must*** use `always @*` and blocking assignments exclusively (`=`).
   * Never mix blocking and non-blocking assignments in the same procedural block.
2. **Eliminating Simulation-Synthesis Mismatches**:
   * Synthesis pragmas (such as `// synopsys full_case parallel_case`) ***must not*** be used.
   * `casex` ***must not*** be used under any circumstances.
   * `casez` ***may*** be used for priority decoding, but wildcard bits ***must*** be specified with `?` (e.g. `4'b1???`), never `z`/`Z`.
   * Every `case` and `casez` statement ***must*** contain a `default:` branch.
3. **FSM Architecture**:
   * FSMs ***must*** follow the clean two-process pattern:
     * Combinational block decodes `state_next` and control outputs, defaulting `state_next = 'bx;` to force explicit state transitions and prevent latch inference.
     * Sequential block handles only reset and `state <= state_next`.

---

## 7. FPGA Hardware Invariants (Cyclone V & Modern Architectures)

1. **Synchronous Memory Inference (M10K / BRAM)**:
   * Block RAM inference requires synchronous reads (`always @(posedge clk) q <= mem[addr]`).
   * Asynchronous memory reads (`assign q = mem[addr]`) synthesize to massive LUT registers and ***must not*** be used for arrays intended for embedded RAM blocks.
2. **Clock Enable Discipline**:
   * Logic-gated clocks (`wire clk_gated = clk & en`) create skew and clock glitches and are strictly prohibited.
   * Use register clock enables (`always @(posedge clk) if (clk_en) ...`).
3. **Tri-State Logic**:
   * Internal tri-states (`1'bz`) do not exist on modern FPGA routing fabrics. Internal multiplexers ***must*** be used.
   * High-impedance `1'bz` is permitted only on top-level bidirectional `inout` pins.
4. **Top Wrapper Architecture**:
   * `<design>_top.v` ***must*** serve exclusively as an interconnect and pin-binding harness. Procedural logic, state machines, and sequential registers ***must not*** exist in the top wrapper.
