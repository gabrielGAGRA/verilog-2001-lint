import argparse
from pathlib import Path
import re
import sys
from typing import List

from verilog2001_lint import __version__
from verilog2001_lint.autofix import fix_source
from verilog2001_lint.config import load_config
from verilog2001_lint.linter import VerilogLinter
from verilog2001_lint.violation import Severity


def parse_args() -> argparse.Namespace:
  cfg = load_config()

  parser = argparse.ArgumentParser(
      prog="v2001-lint",
      description="Strict Verilog-2001 (IEEE 1364-2001) & FPGA RTL Linter (Google Style Guide Aligned)",
      formatter_class=argparse.ArgumentDefaultsHelpFormatter,
  )
  parser.add_argument(
      "targets",
      nargs="*",
      default=cfg.targets,
      help="Files or directories to lint",
  )
  parser.add_argument(
      "--exclude",
      action="append",
      default=None,
      help="Patterns or directory names to exclude (can be specified multiple times)",
  )
  parser.add_argument(
      "--no-iverilog",
      action="store_true",
      default=not cfg.run_iverilog,
      help="Disable Icarus Verilog elaboration check",
  )
  parser.add_argument(
      "--no-verilator",
      action="store_true",
      default=not cfg.run_verilator,
      help="Disable Verilator static analysis check",
  )
  parser.add_argument(
      "--strict",
      action=argparse.BooleanOptionalAction,
      default=cfg.strict,
      help="Fail (exit 1) on errors",
  )
  parser.add_argument(
      "--fix",
      action="store_true",
      default=cfg.fix,
      help="Auto-fix tabs, trailing whitespace, CRLF to LF, ';;' and missing final newline before linting",
  )
  parser.add_argument(
      "--max-line-length",
      type=int,
      default=cfg.max_line_length,
      help="Maximum allowed line length before triggering LINE_TOO_LONG",
  )
  parser.add_argument(
      "-v",
      "--version",
      action="version",
      version=f"%(prog)s {__version__}",
  )
  args = parser.parse_args()

  if args.exclude is None:
    args.exclude = cfg.exclude
  else:
    # Combine CLI excludes with config excludes
    args.exclude = list(set(args.exclude + cfg.exclude))

  args._config = cfg
  return args


def main() -> int:
  args = parse_args()
  cfg = args._config

  linter = VerilogLinter(
      run_iverilog=not args.no_iverilog,
      run_verilator=not args.no_verilator,
      max_line_length=args.max_line_length,
      disabled_rules=cfg.disabled_rules,
  )

  targets: List[Path] = []
  excludes = [re.compile(re.escape(exc)) for exc in args.exclude]
  valid_extensions = {".v", ".vh", ".sv", ".svh"}

  for target in args.targets:
    t_path = Path(target).resolve()
    if t_path.is_file() and t_path.suffix in valid_extensions:
      targets.append(t_path)
    elif t_path.is_dir():
      targets.extend(
          p for p in t_path.rglob("*") if p.suffix in valid_extensions
      )

  filtered_files = sorted(
      {f for f in targets if not any(exc.search(str(f)) for exc in excludes)}
  )

  if not filtered_files:
    print("No Verilog files found to lint.")
    return 0

  print(
      f"\033[1mScanning {len(filtered_files)} file(s) for Verilog-2001 & FPGA compliance...\033[0m\n"
  )

  total_errors = 0
  total_warnings = 0

  if args.fix:
    fixed = 0
    for file_path in filtered_files:
      if file_path.suffix not in (".v", ".vh"):
        continue
      original = file_path.read_bytes().decode("utf-8", errors="replace")
      updated = fix_source(original)
      if updated != original:
        file_path.write_bytes(updated.encode("utf-8"))
        fixed += 1
        print(f"Fixed: {file_path}")
    if fixed:
      print()

  for file_path in filtered_files:
    violations = linter.lint_file(file_path)
    errors = [v for v in violations if v.severity == Severity.ERROR]
    warnings = [v for v in violations if v.severity == Severity.WARNING]
    total_errors += len(errors)
    total_warnings += len(warnings)

    for v in violations:
      print(v)
    if violations:
      print()

  print("-" * 60)
  status_color = "\033[92m" if total_errors == 0 else "\033[91m"
  status_text = "PASS" if total_errors == 0 else "FAIL"
  print(
      f"Result: {status_color}\033[1m{status_text}\033[0m ({total_errors} errors, {total_warnings} warnings)"
  )

  return 1 if total_errors > 0 and args.strict else 0


if __name__ == "__main__":
  sys.exit(main())
