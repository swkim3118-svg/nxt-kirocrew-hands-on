"""Markdown parser for warehouse inventory files.

Each warehouse file is a markdown document with a table of the form:

    # 창고 A 재고

    | 품목 | 수량 |
    |---|---:|
    | mug | 12 |
    | bottle | 3 |
    | sensor | 7 |

This module provides a pure function that reads one such file and returns
the per-item quantities plus the total.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict


def _is_separator_row(cells: list[str]) -> bool:
    """A markdown table separator row is made only of dashes/colons."""
    return all(re.fullmatch(r":?-+:?", c) for c in cells if c != "")


def parse_warehouse(path: str | Path) -> Dict[str, object]:
    """Read a single warehouse markdown file and return its inventory.

    Pure function: only reads the file at ``path``, no other side effects.

    Args:
        path: Path to a warehouse ``.md`` file.

    Returns:
        A dict with:
          - ``"items"``: ``{item_name: quantity}`` mapping (int quantities)
          - ``"total"``: sum of all quantities (int)
    """
    text = Path(path).read_text(encoding="utf-8")

    items: Dict[str, int] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        # Split table row into cells, dropping the empty leading/trailing parts.
        cells = [c.strip() for c in stripped.strip("|").split("|")]

        if len(cells) < 2:
            continue
        if _is_separator_row(cells):
            continue

        name, qty_raw = cells[0], cells[1]

        # Skip the header row ("품목" / "수량").
        if not re.fullmatch(r"-?\d+", qty_raw):
            continue

        items[name] = int(qty_raw)

    total = sum(items.values())
    return {"items": items, "total": total}


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print("usage: python parse.py <warehouse.md>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(parse_warehouse(sys.argv[1]), ensure_ascii=False, indent=2))
