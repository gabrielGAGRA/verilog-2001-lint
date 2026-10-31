# verilog-2001-lint

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![HDL Standard](https://img.shields.io/badge/HDL-Verilog--2001%20%7C%20Verilog--2005-green.svg)](https://standards.ieee.org/)

**`v2001-lint`** is an opinionated, zero-dependency RTL linter and style guardian for **pure Verilog-2001 (IEEE 1364-2001)** or **Verilog-2005**, and FPGA digital hardware design, built on the foundations of the [Google Verilog Style Guide](https://github.com/google/styleguide/blob/gh-pages/verilogguide.md).

It checks **both synthesizable Verilog code and testbenches (`_tb.v`)**, and ships with built-in **LLM-ready engineering guides** in `llm-docs/` specifically tailored for AI agents.

---

## Origin & Rules

Google's style guide was authored for modern 2017 SystemVerilog. `verilog-2001-lint` adapts and specializes these rules specifically for **synthesizable Verilog-2001/2005**, introducing:
1. **Hardware synthesis invariants** tailored for FPGA architectures (such as Intel Cyclone V, Lattice, and Xilinx).
2. **Automated verification rules** for deterministic, self-checking testbenches.
3. **Strict prohibitions against SystemVerilog** (`logic`, `always_ff`, etc.) that break synthesis on tools like Intel Quartus Prime Lite.
4. **LLM Guidelines**: Curated rules in `llm-docs/` for feeding directly into system prompts or agent context windows.

---

## Why another Verilog linter?

Most modern hardware linters (such as **Verible**, **Verilator**, or **svlint**) focus primarily on SystemVerilog. Meanwhile, many real-world FPGA projects—especially in university projects use **Intel Quartus Prime Lite** and target synthesizable **Verilog-2001**:
* FPGA synthesis toolchains (Intel Quartus Prime Lite, Lattice Diamond, Microsemi Libero, legacy Xilinx ISE) often have **limited, buggy, or paid** SystemVerilog support.
* Verible and svlint allow SystemVerilog keywords (`logic`, `always_ff`, `always_comb`, `enum`, `typedef`), which pass linting but break synthesis on FPGA.
* Compilers like **Verilator** lack style rules, naming conventions, include guard enforcement, port ordering, or testbench architecture verification.
* Other tools are written in C++ or Rust, requiring installation of binaries, toolchains, or shared libraries.

**`verilog-2001-lint` solves this:** A pure-Python, zero-dependency linter that combines **strict Verilog-2001 dialect enforcement**, **Google Style Guide** consistency, and **FPGA hardware** synthesis invariants in one fast, unified tool.

---

## Built for LLMs and AI rules

`verilog-2001-lint` is uniquely built for **LLM pair-programming** (Claude, GPT, Gemini, Cursor, Copilot, Antigravity):

* **Context-Optimized Rules (`llm-docs/`)**: Included in the repository are high-density, authoritative constraints designed to be dropped directly into `docs/llm` folders or similar such as `AGENTS.md` or `.agents/rules`:
  * [`llm-docs/verilog-2001-style_guide.md`](llm-docs/verilog-2001-style_guide.md): Compact synthesizable Verilog-2001/2005 standard (Google Style Guide aligned).
  * [`llm-docs/testbench_guide.md`](llm-docs/testbench_guide.md): Self-checking testbench architecture, watchdog timers, and deterministic simulation discipline.
* **Tight Feedback Loop for LLMs**: When LLMs generate Verilog, `v2001-lint` acts as an automated quality gate in CLI/scripts. If the model accidentally forgets include guards, leaves floating inputs, or writes latches, `v2001-lint` provides exact line-number error snippets that the model can self-correct.

---

## Competitive Matrix

| Feature / Dimension | `verilog-2001-lint` | Verible (`verible-verilog-lint`) | Verilator (`--lint-only`) | `svlint` |
| :--- | :---: | :---: | :---: | :---: |
| **Primary Target** | **Verilog-2001 / 2005 (IEEE 1364)** | SystemVerilog (IEEE 1800) | Verilog / SystemVerilog | SystemVerilog |
| **Runtime & Dependencies** | **Zero-dependency Python** | C++ binary / Bazel build | C++ toolchain / compiler | Rust binary |
| **SystemVerilog Leakage Shield** | **Yes (Rejects `logic`, `always_ff`, etc.)** | No (Encourages SV) | No (Permissive) | No (Encourages SV) |
| **Google Style Guide Rules** | **Yes (Tailored for V2001)** | Yes (Targeting SV) | No | No |
| **FPGA Synthesis Invariants** | **Yes (M10K BRAM, gated clocks, latches)** | No | Partial (Latches) | No |
| **Testbench Quality Rules** | **Yes (Self-checking, watchdog, $finish)** | Minimal | No | Minimal |
| **Built-in Auto-Fixer** | **Yes (`--fix` for CRLF, tabs, `;;`)** | Separate formatter | No | No |
| **LLM / AI-Agent Guidelines** | **Yes (`llm-docs/` bundled)** | No | No | No |
| **Multi-Engine Orchestration** | **Yes (Internal + iverilog + verilator)** | Standalone only | Standalone only | Standalone only |
| **Configuration Format** | **TOML (`.v2001lint.toml` / `pyproject.toml`)** | Custom flags file | CLI pragmas | `.svlint.toml` |

---

## Key Features

1. **Strict Verilog-2001 Gatekeeper**:
   * Outlaws accidental SystemVerilog keywords (`logic`, `always_ff`, `always_comb`, `always_latch`, `typedef`, `struct`, `interface`, `unique case`, `priority case`).
   * Enforces `` `default_nettype none `` at top of file and `` `default_nettype wire `` after `endmodule` to eliminate implicit 1-bit wire bugs.
   * Restricts file extensions strictly to `.v` and `.vh`.

2. **Google Verilog Style Guide Conventions**:
   * Identifiers: `lower_snake_case` for nets, variables, and ports.
   * Constants: `UpperCamelCase` for `parameter` and `localparam`.
   * FSM States: Mandatory `localparam` and `kUpperCamelCase` (e.g. `kIdle`, `kWait`).
   * Signal Qualifiers: Rejects `sig_1` suffixes in favor of pipelined `sig_d1` or arrays.
   * Macros: `ALL_CAPS`, with mandatory single underscore (`_LOCAL_MACRO`) and `` `undef `` for file-local macros.

3. **FPGA & Microarchitecture Safety**:
   * **M10K Block RAM**: Detects asynchronous reads on inferred RAM arrays that cause synthesis toolchains to fail memory block mapping.
   * **Clock Gating**: Flags logic-gated clocks (`clk & en`) to ensure clean register clock enables.
   * **Tri-State Logic**: Blocks internal tri-states (`1'bz`) not supported by FPGA routing fabrics.
   * **Top-Level Wrapper**: Enforces pure routing and instantiation in `*_top.v` modules (no procedural logic or state registers).

4. **Testbench Architecture Standards**:
   * Enforces portless testbench headers (`module my_tb;`).
   * Enforces deterministic simulation completion via `$finish;` (bans interactive `$stop;`).
   * Validates watchdog timer protection against deadlocked simulations.

5. **Multi-Engine Hybrid Pre-Flight**:
   * Runs internal regex-based AST and styling passes.
   * Automatically invokes **Icarus Verilog (`iverilog`)** for compiler elaboration pre-flight checks if installed.
   * Automatically invokes **Verilator (`verilator`)** for deep static analysis (unconnected pins, comb loops, latches) if installed.

6. **In-Place Auto-Fixer (`--fix`)**:
   * Converts CRLF line endings to POSIX LF.
   * Replaces hard tabs with 2 spaces.
   * Strips trailing whitespace.
   * Removes redundant duplicate semicolons (`;;`).
   * Ensures files terminate with a newline.

---

## Installation

### Via `pip`:
```bash
pip install verilog-2001-lint
```

### Via `uv`:
```bash
uv tool install verilog-2001-lint
```

---

## Quickstart

Run against your project directory:
```bash
v2001-lint .
```

Auto-fix formatting issues and lint in one command:
```bash
v2001-lint --fix rtl/
```

Run without invoking external compilers:
```bash
v2001-lint --no-iverilog --no-verilator rtl/
```

### Command Line Options

```text
usage: v2001-lint [-h] [--exclude EXCLUDE] [--no-iverilog] [--no-verilator]
                  [--strict | --no-strict] [--fix]
                  [--max-line-length MAX_LINE_LENGTH] [-v]
                  [targets ...]

Strict Verilog-2001 (IEEE 1364-2001) & FPGA RTL Linter (Google Style Guide Aligned)

positional arguments:
  targets               Files or directories to lint (default: ['.'])

options:
  -h, --help            show this help message and exit
  --exclude EXCLUDE     Patterns or directory names to exclude
  --no-iverilog         Disable Icarus Verilog elaboration check
  --no-verilator        Disable Verilator static analysis check
  --strict, --no-strict Fail (exit 1) on errors (default: True)
  --fix                 Auto-fix formatting before linting
  --max-line-length MAX Maximum allowed line length (default: 100)
  -v, --version         show program's version number and exit
```

---

## Inline Waivers

Rules can be waived per line using comments:

```verilog
// lint_waive: SIGNAL_UNDERSCORE_NUMBER - Pin interface mapping
wire rx_0;

wire [7:0] data = lut_mem[addr]; // lint_waive: M10K_ASYNC_READ_PROHIBITED - Small distributed LUT
```

---

## Configuration

You can configure `verilog-2001-lint` directly in `pyproject.toml` or using a `.v2001lint.toml` file in your project root:

```toml
[tool.v2001lint]
targets = ["rtl", "tb"]
exclude = [".git", "work", "ip_cores"]
run_iverilog = true
run_verilator = true
strict = true
fix = false
max_line_length = 100
disabled_rules = [
    # "LINE_TOO_LONG",
]
```

---

## Documentation & LLM Resources

* [Full Lint Rules Catalog](docs/rules.md)
* [LLM Verilog-2001 Synthesizable RTL Style Guide](llm-docs/verilog-2001-style_guide.md)
* [LLM Verilog-2001 Testbench & Verification Standard](llm-docs/testbench_guide.md)

---

## License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.
