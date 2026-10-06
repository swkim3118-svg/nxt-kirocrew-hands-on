"""Per-warehouse aggregation task -- an independent DAG node.

This module implements the reusable node used for warehouses A, B and C.
Each invocation of :func:`aggregate` reads exactly one warehouse markdown
file via :mod:`parse` and writes that warehouse's total and per-item
quantities to its own intermediate JSON file. It does NOT read any other
warehouse's file or output, so the three A/B/C invocations are mutually
independent and can run in any order (or in parallel).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from parse import parse_warehouse

# Directory of this module == run02/. Inputs live at practice/data relative
# to the week05 root (three levels up: run02 -> practice -> submissions -> week05).
RUN_DIR = Path(__file__).resolve().parent
WEEK05_ROOT = RUN_DIR.parents[2]
DATA_DIR = WEEK05_ROOT / "practice" / "data"


def aggregate(warehouse_id: str) -> Dict[str, object]:
    """Aggregate a single warehouse and persist its intermediate file.

    Independent DAG node: depends only on its own input file
    ``practice/data/warehouse-<id>.md``, never on another warehouse.

    Args:
        warehouse_id: Warehouse identifier, e.g. ``"a"``, ``"b"``, ``"c"``.

    Returns:
        A dict with:
          - ``"warehouse"``: the (lower-cased) warehouse id
          - ``"items"``: ``{item_name: quantity}`` for this warehouse
          - ``"total"``: sum of this warehouse's quantities

    Side effect:
        Writes ``run02/warehouse_<id>_agg.json`` with the same content.
    """
    wid = warehouse_id.strip().lower()
    src = DATA_DIR / f"warehouse-{wid}.md"

    parsed = parse_warehouse(src)

    result: Dict[str, object] = {
        "warehouse": wid,
        "items": parsed["items"],
        "total": parsed["total"],
    }

    out_path = RUN_DIR / f"warehouse_{wid}_agg.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python aggregate_warehouse.py <warehouse_id>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(aggregate(sys.argv[1]), ensure_ascii=False, indent=2))
