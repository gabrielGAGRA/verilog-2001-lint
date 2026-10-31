"""verilog2001-lint: Strict Verilog-2001 & FPGA RTL Linter aligned with Google Verilog Style Guide."""

from verilog2001_lint.linter import VerilogLinter
from verilog2001_lint.violation import LintViolation, Severity

__version__ = "1.0.0"
__all__ = ["VerilogLinter", "LintViolation", "Severity"]
