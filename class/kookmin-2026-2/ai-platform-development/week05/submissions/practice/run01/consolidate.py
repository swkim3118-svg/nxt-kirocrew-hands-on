"""Merge / consolidation DAG node.

Reads the three per-warehouse intermediate JSON files produced by the
aggregate_warehouse nodes and combines them into the final result dict
matching practice/출력형식.md:

  - source_files:     the original warehouse markdown file names
  - warehouse_totals: {warehouse -> int total}
  - item_totals:      {item -> int total summed across all warehouses}
  - grand_total:      int total across every warehouse
  - low_stock_basis:  "warehouse_row"
  - threshold:        5
  - low_stock:        per-warehouse list of {item, quantity, warehouse}
                      for each source row whose quantity < threshold

All numeric values are stored as ints.
"""

from __future__ import annotations

import json
from typing import Dict, List

LOW_STOCK_THRESHOLD = 5
LOW_STOCK_BASIS = "warehouse_row"

# Fixed source-file order (A, B, C) as required by the output format.
SOURCE_FILES = ["warehouse-a.md", "warehouse-b.md", "warehouse-c.md"]


def consolidate(intermediate_paths: List[str]) -> Dict:
    """Merge the intermediate files into the final result dict.

    Args:
        intermediate_paths: paths to the three intermediate-*.json files.

    Returns:
        The consolidated result dict following practice/출력형식.md.
    """
    warehouse_totals: Dict[str, int] = {}
    item_totals: Dict[str, int] = {}
    low_stock: List[Dict] = []
    grand_total = 0

    # Read every intermediate file, keyed by warehouse name so ordering of
    # the input path list does not matter.
    intermediates: Dict[str, Dict] = {}
    for path in intermediate_paths:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        intermediates[str(data["warehouse"])] = data

    for warehouse in sorted(intermediates):
        data = intermediates[warehouse]

        total = int(data["total"])
        warehouse_totals[warehouse] = total
        grand_total += total

        for item, qty in data["item_quantities"].items():
            item_totals[item] = item_totals.get(item, 0) + int(qty)

        for entry in data["low_stock"]:
            low_stock.append(
                {
                    "item": entry["item"],
                    "quantity": int(entry["quantity"]),
                    "warehouse": warehouse,
                }
            )

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
    import os

    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    all_paths = [
        os.path.join(_THIS_DIR, f"intermediate-{letter}.json")
        for letter in ("a", "b", "c")
    ]
    # Only consolidate intermediates that already exist. The full set is
    # produced by the DAG runner (run_dag.py); running this module directly
    # beforehand should preview whatever is available rather than crash.
    existing = [p for p in all_paths if os.path.exists(p)]
    missing = [p for p in all_paths if not os.path.exists(p)]
    if missing:
        print(
            "note: missing intermediate files (run run_dag.py to generate): "
            + ", ".join(os.path.basename(m) for m in missing)
        )
    if existing:
        print(json.dumps(consolidate(existing), ensure_ascii=False, indent=2))
