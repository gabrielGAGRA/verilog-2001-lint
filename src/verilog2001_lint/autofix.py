from typing import List
import re

from verilog2001_lint.waivers import mask_comments_and_strings


def fix_source(source: str) -> str:
  """Auto-fixes formatting defects in Verilog-2001 files:

  - CRLF to POSIX LF line endings
  - Tabs converted to 2 spaces
  - Trailing whitespace removed
  - Duplicate semicolons (;;) removed outside for loop headers
  - Missing EOF newline added
  """
  masked = mask_comments_and_strings(source)
  out: List[str] = []
  for raw, m_line in zip(
      source.splitlines(keepends=True), masked.splitlines(keepends=True)
  ):
    eol = raw[len(raw.rstrip("\r\n")):]
    body = raw[: len(raw) - len(eol)]
    m_body = m_line[: len(body)]

    # Duplicate semicolons (code only; keep for(;;) headers intact)
    if ";;" in m_body and not re.search(r"\bfor\s*\(", m_body):
      chars = list(body)
      for m in reversed(list(re.finditer(r";{2,}", m_body))):
        chars[m.start() + 1 : m.end()] = []
      body = "".join(chars)

    # Tabs to 2 spaces
    indent = body[: len(body) - len(body.lstrip(" \t"))]
    body = indent.replace("\t", "  ") + body[len(indent):]
    line_ending = "\n" if eol else ""
    out.append(body.rstrip() + line_ending)

  result = "".join(out)
  if result and not result.endswith("\n"):
    result += "\n"
  return result
