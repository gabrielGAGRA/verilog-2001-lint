from pathlib import Path
import re
from typing import Callable, Dict, List, Set

RE_MEM_DECL = re.compile(
    r"\breg\s+(?:\[[^\]]+\]\s+)?([a-zA-Z_0-9]+)\s*\[[^\]]+\]\s*;"
)
RE_GATED_CLK = re.compile(
    r"\b(?:assign\s+|wire\s+)[a-zA-Z_0-9]*clk[a-zA-Z_0-9]*\s*=\s*[^;]*(?:\b(?:clk|clock)\b\s*&|&\s*\b(?:clk|clock)\b)",
    re.IGNORECASE,
)
RE_TRISTATE = re.compile(r"1'[bB][zZ]")


def check_cyclone_v_invariants(
    file_path: Path,
    masked_lines: List[str],
    raw_lines: List[str],
    waivers: Dict[int, Set[str]],
    add_violation: Callable[..., None],
) -> None:
  """Enforces FPGA synthesis invariants (M10K synchronous RAM, no clock gating, no internal tri-states)."""
  mem_arrays = {
      m.group(1)
      for line in masked_lines
      for m in [RE_MEM_DECL.search(line)]
      if m
  }
  stem_lower = file_path.stem.lower()
  is_top = (
      stem_lower == "top"
      or stem_lower.endswith("_top")
      or stem_lower.startswith("top_")
      or any(re.search(r"\binout\b", l) for l in masked_lines)
  )

  in_comb = False
  for idx, line in enumerate(masked_lines):
    line_num = idx + 1

    if re.search(r"\balways\s*@\s*(\*|\(\s*\*\s*\))", line):
      in_comb = True
    elif re.search(r"\balways\s*@\s*\(", line):
      in_comb = False
    if "endmodule" in line:
      in_comb = False

    for mem in mem_arrays:
      is_async_assign = bool(
          re.search(rf"\bassign\s+[^=]+=\s*{mem}\s*\[", line)
      )
      is_async_comb = in_comb and bool(
          re.search(rf"\b\w+\s*=\s*{mem}\s*\[", line)
      )
      if is_async_assign or is_async_comb:
        add_violation(
            "M10K_ASYNC_READ_PROHIBITED",
            file_path,
            line_num,
            1,
            f"Asynchronous read on memory array '{mem}'. Cyclone V M10K blocks require synchronous read ('always @(posedge clk) q <= {mem}[addr]').",
            raw_lines[idx],
        )

    gated_clk = RE_GATED_CLK.search(line)
    if gated_clk:
      add_violation(
          "CLOCK_GATING_LOGIC_PROHIBITED",
          file_path,
          line_num,
          gated_clk.start() + 1,
          "Logic-gated clock detected (clk & en). Use dedicated register clock enables.",
          raw_lines[idx],
      )

    tristate = RE_TRISTATE.search(line)
    if tristate and not is_top:
      add_violation(
          "INTERNAL_TRISTATE_PROHIBITED",
          file_path,
          line_num,
          tristate.start() + 1,
          "Internal tri-state (1'bz) prohibited in Cyclone V core logic. Use multiplexers.",
          raw_lines[idx],
      )

  if file_path.suffix == ".v" and file_path.stem.lower().endswith("_top"):
    for idx, line in enumerate(masked_lines):
      m = re.search(r"\b(always|initial)\b", line)
      if m:
        add_violation(
            "TOP_LEVEL_LOGIC_PROHIBITED",
            file_path,
            idx + 1,
            m.start() + 1,
            "Top-level wrapper must contain only wiring and instantiations; move procedural logic into a submodule.",
            raw_lines[idx],
        )
