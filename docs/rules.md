# Verilog-2001 Linter Rule Reference

This document catalogs all static analysis and lint rules enforced by `verilog-2001-lint` (`v2001-lint`).

---

## Rule Summary Table

| Category | Rule ID | Default Severity | Description |
| :--- | :--- | :--- | :--- |
| **File Structure** | `FILE_EXT_SYSTEMVERILOG` | `ERROR` | Rejects `.sv` and `.svh` file extensions; enforces `.v` / `.vh`. |
| | `FILE_MULTIPLE_MODULES` | `ERROR` | Requires strictly one module per `.v` file. |
| | `FILE_MODULE_NAME_MISMATCH` | `ERROR` | Module identifier must match the file basename. |
| | `DIRECTIVE_DEFAULT_NETTYPE_NONE` | `ERROR` | Mandatory `` `default_nettype none `` prior to module declaration. |
| | `DIRECTIVE_DEFAULT_NETTYPE_WIRE` | `ERROR` | Mandatory `` `default_nettype wire `` after `endmodule`. |
| | `HEADER_GUARD_MISSING` | `ERROR` | Header files (`.vh`) must declare `ifndef / `define include guards. |
| | `FILE_HEADER_COMMENT_MISSING` | `WARNING` | Files must begin with a descriptive block or line comment header. |
| **Formatting** | `TAB_CHARACTER` | `WARNING` | Hard tabs are prohibited; use 2 spaces per indent level. |
| | `TRAILING_WHITESPACE` | `WARNING` | Disallows trailing spaces or tabs before newline. |
| | `LINE_ENDING_CRLF` | `WARNING` | CRLF (`\r\n`) prohibited; requires POSIX LF (`\n`). |
| | `LINE_TOO_LONG` | `WARNING` | Warns if lines exceed 100 characters (configurable). |
| | `INDENTATION_STEP` | `WARNING` | Indentation must be in multiples of 2 spaces. |
| | `REDUNDANT_SEMICOLON` | `WARNING` | Consecutive semicolons (`;;`) prohibited. |
| | `PREPROCESSOR_INDENT` | `WARNING` | Preprocessor directives (` `ifdef`, ` `else`, etc.) must start at column 0. |
| | `SPACING_STYLE` | `WARNING` | Requires space after control keywords (`if (`, `case (`, etc.). |
| | `BEGIN_END_STYLE` | `WARNING` | `begin` on same line as keyword; enforces `end else begin`. |
| | `SYNTHESIS_PRAGMA_PROHIBITED` | `ERROR` | Pragmas like `full_case`, `parallel_case`, and `translate_off` are banned. |
| **Naming & Types** | `SV_KEYWORD_BANNED` | `ERROR` | Prohibits SystemVerilog keywords (`logic`, `always_ff`, `always_comb`, `typedef`, etc.). |
| | `CLOCK_RESET_NAMING` | `ERROR` | Clocks must be `clk` (or `<domain>_clk`); resets must be `rst` (sync) or `arst` (async). |
| | `PORT_ORDER_CLK_RST` | `WARNING` | Clock port must be declared first in module port list. |
| | `PARAM_NAMING_STYLE` | `ERROR` | `parameter` and `localparam` must use `UpperCamelCase`. |
| | `FSM_STATE_NAMING_STYLE` | `ERROR` | FSM state constants must use `localparam` with `kUpperCamelCase` (e.g. `kIdle`). |
| | `SIGNAL_UNDERSCORE_NUMBER` | `ERROR` | Disallows signal suffixes like `sig_1`; use pipeline stages `_d1` or arrays. |
| | `MACRO_NAMING_AND_UNDEF` | `ERROR` | Macros must be `ALL_CAPS`; local macros in `.v` must start with `_` and be `` `undef ``'d. |
| | `BINARY_LITERAL_WIDTH_MISMATCH`| `ERROR` | Sized binary literals must explicitly state all bits (e.g. `4'b0001`). |
| | `PACKED_UNPACKED_ENDIANNESS` | `ERROR` | Packed vectors little-endian `[MSB:LSB]`; unpacked arrays big-endian `[0:N-1]`. |
| **Modules & Generates** | `DEFAULT_PORT_VALUE_PROHIBITED` | `ERROR` | Default input port assignments in module declarations are banned. |
| | `POSITIONAL_INSTANTIATION` | `ERROR` | Named port connection (`.port(sig)`) is mandatory. |
| | `POSITIONAL_PARAM_INSTANTIATION`| `ERROR` | Named parameter override (`#(.Param(val))`) is mandatory. |
| | `FLOATING_INPUT_PORT` | `ERROR` | Input ports must not be left unbound (`.in_val()`). |
| | `DEFPARAM_PROHIBITED` | `ERROR` | `defparam` is banned; use inline parameter overrides. |
| | `RECURSIVE_INSTANTIATION` | `ERROR` | Recursive module instantiation is prohibited. |
| | `GENERATE_BLOCK_LABEL` | `ERROR` | `generate begin` blocks must have labels starting with `gen_`. |
| | `INSTANCE_NAME_CONVENTION` | `ERROR` | Submodule instance name must start with module type (or `dut`/`uut` in testbenches). |
| **Procedural Logic** | `MANUAL_SENSITIVITY_LIST` | `ERROR` | Combinational blocks must use `always @*`. |
| | `SEQUENTIAL_BLOCKING_ASSIGNMENT` | `ERROR` | Blocking (`=`) prohibited in clocked sequential blocks. |
| | `COMBINATIONAL_NONBLOCKING_ASSIGNMENT` | `ERROR` | Non-blocking (`<=`) prohibited in combinational blocks. |
| | `ANTI_PATTERN_REDUNDANT_CLOCK_CHECK` | `ERROR` | `else if (clk)` checks inside edge-triggered blocks are banned. |
| | `DELAY_PROHIBITED` | `ERROR` | `#delay` statements are prohibited in synthesizable RTL. |
| | `CASEX_PROHIBITED` | `ERROR` | `casex` is prohibited; use `case` or `casez`. |
| | `CASEZ_Z_LITERAL` | `ERROR` | Wildcards in `casez` must use `?`, not `z`/`Z`. |
| | `TASK_IN_RTL_PROHIBITED` | `ERROR` | `task` is prohibited in synthesizable modules. |
| | `FUNCTION_NOT_AUTOMATIC` | `ERROR` | RTL functions must be declared `function automatic`. |
| | `SIGNED_LOGICAL_RIGHT_SHIFT` | `ERROR` | Signed variables must use `>>>` arithmetic shift instead of `>>`. |
| | `NESTED_TERNARY_PARENS` | `WARNING` | Nested ternaries (`a ? b : c ? d : e`) must be parenthesized. |
| | `REDUCTION_OPERATOR_PARENS`| `WARNING` | Reduction operators preceded by other operators must be parenthesized (`~(&foo)`). |
| | `CASE_MISSING_DEFAULT` | `ERROR` | Every `case` / `casez` statement must provide a `default:` branch. |
| **FPGA Synthesis** | `M10K_ASYNC_READ_PROHIBITED` | `ERROR` | Asynchronous reads on inferred BRAM arrays are prohibited. |
| | `CLOCK_GATING_LOGIC_PROHIBITED`| `ERROR` | Logic-gated clocks (`clk & en`) prohibited; use clock enables. |
| | `INTERNAL_TRISTATE_PROHIBITED` | `ERROR` | Internal `1'bz` prohibited; allowed only on top-level `inout` pins. |
| | `TOP_LEVEL_LOGIC_PROHIBITED` | `ERROR` | Top wrapper (`*_top.v`) must contain only wiring and instantiations. |
| **Testbench Architecture** | `TESTBENCH_HAS_PORTS` | `ERROR` | Testbench modules must be closed (no ports: `module tb;`). |
| | `TESTBENCH_MISSING_FINISH` | `ERROR` | Testbenches must contain `$finish;` for deterministic CI exit. |
| | `TESTBENCH_STOP_PROHIBITED` | `WARNING` | `$stop;` is prohibited in automated testbenches. |
| | `TESTBENCH_PLUSARG_TEST` | `WARNING` | `$test$plusargs` prohibited; use `$value$plusargs`. |
| **External Pre-flights** | `IVERILOG_COMPILER_ERROR` | `ERROR` | Icarus Verilog compiler syntax / elaboration error. |
| | `VERILATOR_<RULE>` | `ERROR` / `WARNING` | Verilator static RTL analysis issue (latch, width, etc.). |

---

## Waivers

Any rule can be waived for a specific line using an inline comment on that line or immediately above it:

```verilog
// lint_waive: SIGNAL_UNDERSCORE_NUMBER - Legacy protocol signal mapping
wire rx_pin_0;

wire [7:0] data_raw = mem[addr]; // lint_waive: M10K_ASYNC_READ_PROHIBITED - Small distributed LUT RAM
```
