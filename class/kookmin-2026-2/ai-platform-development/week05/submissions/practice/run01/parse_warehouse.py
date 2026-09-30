"""Shared parser for warehouse inventory markdown files.

Mirrors the checker's regex:
  heading: ^# 창고 (\\S+) 재고$
  rows:    ^\\|\\s*([a-zA-Z0-9_-]+)\\s*\\|\\s*(\\d+)\\s*\\|$
"""

from __future__ import annotations

import os
import re
from typing import List, Tuple

HEADING_RE = re.compile(r"^# 창고 (\S+) 재고$")
ROW_RE = re.compile(r"^\|\s*([a-zA-Z0-9_-]+)\s*\|\s*(\d+)\s*\|$")


def parse_warehouse(path: str) -> Tuple[str, List[Tuple[str, int]]]:
    """Read a warehouse markdown file and return (warehouse_name, rows).

    rows is a list of (item_name, quantity) pairs preserving source order.

    Raises ValueError on:
      - missing warehouse heading
      - duplicate warehouse heading
      - duplicate item rows
    """
    abs_path = os.path.abspath(path)
    with open(abs_path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    warehouse_name = None
    rows: List[Tuple[str, int]] = []
    seen_items = set()

    for line in lines:
        stripped = line.rstrip("\r")

        h = HEADING_RE.match(stripped)
        if h:
            if warehouse_name is not None:
                raise ValueError(f"Duplicate warehouse heading in {abs_path!r}")
            warehouse_name = h.group(1)
            continue

        r = ROW_RE.match(stripped)
        if r:
            item = r.group(1)
            qty = int(r.group(2))
            if item in seen_items:
                raise ValueError(f"Duplicate item row {item!r} in {abs_path!r}")
            seen_items.add(item)
            rows.append((item, qty))

    if warehouse_name is None:
        raise ValueError(f"Missing warehouse heading in {abs_path!r}")

    return warehouse_name, rows


if __name__ == "__main__":
    import sys

    name, parsed = parse_warehouse(sys.argv[1])
    print(f"warehouse={name}")
    for item, qty in parsed:
        print(f"  {item}: {qty}")
