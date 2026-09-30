"""Per-warehouse aggregation DAG node.

Reads practice/data/warehouse-<letter>.md via the shared parser, computes the
warehouse total, per-item quantities and the low-stock list (source rows with
quantity < 5), and writes an intermediate JSON file for the merge task.
"""

from __future__ import annotations

import json
import os
from typing import Dict

from parse_warehouse import parse_warehouse

# Absolute anchors so the node works regardless of the caller's CWD.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # .../submissions/practice/run01
_WEEK05_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))  # .../week05
_DATA_DIR = os.path.join(_WEEK05_DIR, "practice", "data")

LOW_STOCK_THRESHOLD = 5


def aggregate_warehouse(warehouse_letter: str) -> Dict:
    """Aggregate a single warehouse and write its intermediate file.

    Returns the computed dict:
      {warehouse, total, item_quantities, low_stock:[{item,quantity}]}
    """
    letter = warehouse_letter.strip().lower()
    source_path = os.path.join(_DATA_DIR, f"warehouse-{letter}.md")

    warehouse_name, rows = parse_warehouse(source_path)

    total = 0
    item_quantities: Dict[str, int] = {}
    low_stock = []

    for item, qty in rows:
        total += qty
        item_quantities[item] = item_quantities.get(item, 0) + qty
        if qty < LOW_STOCK_THRESHOLD:
            low_stock.append({"item": item, "quantity": qty})

    result = {
        "warehouse": warehouse_name,
        "total": total,
        "item_quantities": item_quantities,
        "low_stock": low_stock,
    }

    out_path = os.path.join(_THIS_DIR, f"intermediate-{letter}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    import sys

    letter_arg = sys.argv[1] if len(sys.argv) > 1 else "a"
    computed = aggregate_warehouse(letter_arg)
    print(json.dumps(computed, ensure_ascii=False, indent=2))
