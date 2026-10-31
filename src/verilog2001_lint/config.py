from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set

try:
  if sys.version_info >= (3, 11):
    import tomllib
  else:
    import tomli as tomllib
except ImportError:
  tomllib = None  # type: ignore


@dataclass
class LintConfig:
  targets: List[str] = field(default_factory=lambda: ["."])
  exclude: List[str] = field(
      default_factory=lambda: [
          "local",
          ".git",
          "work",
          "__pycache__",
          "build",
          "dist",
      ]
  )
  run_iverilog: bool = True
  run_verilator: bool = True
  strict: bool = True
  fix: bool = False
  max_line_length: int = 100
  disabled_rules: Set[str] = field(default_factory=set)


def load_config(root_dir: Optional[Path] = None) -> LintConfig:
  """Loads configuration from .v2001lint.toml, v2001lint.toml, or pyproject.toml."""
  config = LintConfig()
  base = root_dir or Path.cwd()

  candidate_files = [
      base / ".v2001lint.toml",
      base / "v2001lint.toml",
      base / "pyproject.toml",
  ]

  found_file: Optional[Path] = None
  for c in candidate_files:
    if c.is_file():
      found_file = c
      break

  if not found_file or tomllib is None:
    return config

  try:
    with open(found_file, "rb") as f:
      data = tomllib.load(f)

    section: Dict[str, Any] = {}
    if found_file.name == "pyproject.toml":
      section = data.get("tool", {}).get("v2001lint", {})
    else:
      section = data.get("linter", data)

    if "targets" in section and isinstance(section["targets"], list):
      config.targets = [str(t) for t in section["targets"]]
    if "exclude" in section and isinstance(section["exclude"], list):
      config.exclude = [str(e) for e in section["exclude"]]
    if "run_iverilog" in section:
      config.run_iverilog = bool(section["run_iverilog"])
    if "run_verilator" in section:
      config.run_verilator = bool(section["run_verilator"])
    if "strict" in section:
      config.strict = bool(section["strict"])
    if "fix" in section:
      config.fix = bool(section["fix"])
    if "max_line_length" in section:
      config.max_line_length = int(section["max_line_length"])
    if "disabled_rules" in section and isinstance(
        section["disabled_rules"], list
    ):
      config.disabled_rules = {str(r) for r in section["disabled_rules"]}

  except Exception:
    pass

  return config
