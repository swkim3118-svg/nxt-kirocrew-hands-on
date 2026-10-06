"""Integration / consolidation DAG node.

Depends on all three per-warehouse aggregation nodes. Reads the three
``warehouse_<id>_agg.json`` intermediate files produced by
:mod:`aggregate_warehouse` and merges them into the final result dict
following ``practice/출력형식.md``:

  - source_files:     the original warehouse markdown file names
  - warehouse_totals: {warehouse -> int total}
  - item_totals:      {item -> int total summed across all warehouses}
  - grand_total:      int total across every warehouse
  - low_stock_basis:  "item_total"  (per the 2차 spec)
  - threshold:        5
  - low_stock:        [{"item", "quantity"}] for each item whose
                      total quantity across ALL warehouses is < threshold

Low-stock judgement uses the item total across every warehouse, NOT the
per-warehouse row. All numeric values are stored as ints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

LOW_STOCK_THRESHOLD = 5
LOW_STOCK_BASIS = "item_total"

# Fixed source-file order (A, B, C) as required by the output format.
SOURCE_FILES = ["warehouse-a.md", "warehouse-b.md", "warehouse-c.md"]


def consolidate(intermediate_paths: List[str]) -> Dict:
    """Merge the intermediate aggregation files into the final result.

    Args:
        intermediate_paths: paths to the three ``warehouse_<id>_agg.json`` files.

    Returns:
        The consolidated result dict following ``practice/출력형식.md`` with
        ``low_stock_basis == "item_total"``.
    """
    warehouse_totals: Dict[str, int] = {}
    item_totals: Dict[str, int] = {}
    grand_total = 0

    # Key intermediates by warehouse so the order of the path list is irrelevant.
    intermediates: Dict[str, Dict] = {}
    for path in intermediate_paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        intermediates[str(data["warehouse"])] = data

    for warehouse in sorted(intermediates):
        data = intermediates[warehouse]

        total = int(data["total"])
        warehouse_totals[warehouse.upper()] = total
        grand_total += total

        for item, qty in data["items"].items():
            item_totals[item] = item_totals.get(item, 0) + int(qty)

    # Low stock judged on the whole-fleet item total (< threshold).
    low_stock: List[Dict] = [
        {"item": item, "quantity": int(qty)}
        for item, qty in sorted(item_totals.items())
        if qty < LOW_STOCK_THRESHOLD
    ]

    return {
        "source_files": list(SOURCE_FILES),
        "warehouse_totals": warehouse_totals,
        "item_totals": item_totals,
        "grand_total": int(grand_total),
        "low_stock_basis": LOW_STOCK_BASIS,
        "threshold": int(LOW_STOCK_THRESHOLD),
        "low_stock": low_stock,
    }


if __name__ == "__main__":
    _THIS_DIR = Path(__file__).resolve().parent
    all_paths = [_THIS_DIR / f"warehouse_{letter}_agg.json" for letter in ("a", "b", "c")]
    existing = [str(p) for p in all_paths if p.exists()]
    missing = [p.name for p in all_paths if not p.exists()]
    if missing:
        print("note: missing intermediate files (run run_dag.py first): " + ", ".join(missing))
    if existing:
        print(json.dumps(consolidate(existing), ensure_ascii=False, indent=2))
