from pathlib import Path
import re
from typing import Dict, Set


def mask_comments_and_strings(source: str) -> str:
  """Masks comments and strings with spaces, preserving line and column offsets."""

  def _repl(m: re.Match) -> str:
    return re.sub(r"[^\r\n]", " ", m.group(0))

  return re.sub(
      r"//[^\r\n]*|/\*[\s\S]*?\*/|\"(?:\\.|[^\"\\\r\n])*\"", _repl, source
  )


def parse_waivers(raw_source: str) -> Dict[int, Set[str]]:
  """Extracts line-level waivers: // lint_waive: RULE_ID [optional notes].

  A waiver applies to the current line and the immediately following line.
  """
  waivers: Dict[int, Set[str]] = {}
  pattern = re.compile(
      r"(?://|/\*)\s*lint_waive:\s*([A-Za-z0-9_]+)", re.IGNORECASE
  )
  for idx, line in enumerate(raw_source.splitlines()):
    line_num = idx + 1
    matches = pattern.findall(line)
    if matches:
      rule_set = {m.strip() for m in matches}
      waivers.setdefault(line_num, set()).update(rule_set)
      waivers.setdefault(line_num + 1, set()).update(rule_set)
  return waivers
