"""DAG runner for warehouse inventory aggregation (run02).

DAG structure — three mutually independent warehouse nodes and one merge:

    task_a ─┐
    task_b ─┼─▶ task_merge ─▶ result.json + report.md
    task_c ─┘

  - task_a / task_b / task_c call aggregate_warehouse.aggregate("a"/"b"/"c")
    with NO inter-dependencies; they run concurrently via ThreadPoolExecutor.
  - task_merge depends on all three.  It runs consolidate() over the three
    intermediate warehouse_<id>_agg.json files, then writes result.json and
    report.md.

Low-stock basis for run02: item_total, threshold = 5.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from aggregate_warehouse import aggregate
from consolidate import consolidate, LOW_STOCK_BASIS, LOW_STOCK_THRESHOLD

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

WAREHOUSES = ["a", "b", "c"]

# ── DAG definition: node -> list of upstream dependencies. ───────────────
DAG: Dict[str, List[str]] = {
    "task_a": [],
    "task_b": [],
    "task_c": [],
    "task_merge": ["task_a", "task_b", "task_c"],
}


def _print_dag() -> None:
    print("DAG dependency structure:")
    for node in ("task_a", "task_b", "task_c", "task_merge"):
        deps = DAG[node]
        dep_str = ", ".join(deps) if deps else "(none — independent)"
        print(f"  {node} depends on: {dep_str}")
    print()


def _write_report(result: Dict, path: str) -> None:
    """Write the short Markdown report matching practice/출력형식.md."""
    lines: List[str] = [
        "# 창고 재고 통합 리포트",
        "",
        f"- 저재고 기준(low_stock_basis): `{result['low_stock_basis']}`",
        f"- 임계값(threshold): {result['threshold']} (quantity < {result['threshold']})",
        f"- 원본 파일: {', '.join(result['source_files'])}",
        f"- 전체 합계(grand_total): {result['grand_total']}",
        "",
        "## 창고별 합계 (warehouse_totals)",
        "",
        "| 창고 | 합계 |",
        "| --- | --- |",
    ]
    for warehouse, total in result["warehouse_totals"].items():
        lines.append(f"| {warehouse} | {total} |")
    lines.append("")

    lines += [
        "## 품목별 전체 수량 (item_totals)",
        "",
        "| 품목 | 총 수량 |",
        "| --- | --- |",
    ]
    for item, qty in result["item_totals"].items():
        lines.append(f"| {item} | {qty} |")
    lines.append("")

    lines.append("## 저재고 목록 (low_stock)")
    lines.append("")
    if result["low_stock"]:
        lines.append("| 품목 | 수량 |")
        lines.append("| --- | --- |")
        for entry in result["low_stock"]:
            lines.append(f"| {entry['item']} | {entry['quantity']} |")
    else:
        lines.append("저재고 품목이 없습니다.")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def run_dag() -> Dict:
    _print_dag()

    # ── Phase 1: three independent warehouse nodes concurrently ──────────
    print("Executing independent warehouse nodes concurrently: task_a, task_b, task_c")
    node_names = {letter: f"task_{letter}" for letter in WAREHOUSES}
    with ThreadPoolExecutor(max_workers=len(WAREHOUSES)) as executor:
        future_to_letter = {
            executor.submit(aggregate, letter): letter for letter in WAREHOUSES
        }
        for future in as_completed(future_to_letter):
            letter = future_to_letter[future]
            future.result()  # propagate any exception
            print(f"  ✔ {node_names[letter]} finished (warehouse {letter.upper()})")

    # ── Phase 2: merge node (depends on all three) ───────────────────────
    print("All warehouse nodes complete → running task_merge (consolidate)")
    intermediate_paths = [
        os.path.join(_THIS_DIR, f"warehouse_{letter}_agg.json") for letter in WAREHOUSES
    ]
    result = consolidate(intermediate_paths)

    # ── Write deliverables ───────────────────────────────────────────────
    result_path = os.path.join(_THIS_DIR, "result.json")
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(f"  ✔ wrote {result_path}")

    report_path = os.path.join(_THIS_DIR, "report.md")
    _write_report(result, report_path)
    print(f"  ✔ wrote {report_path}")

    print(
        f"\nDone. basis={LOW_STOCK_BASIS}, threshold={LOW_STOCK_THRESHOLD}, "
        f"grand_total={result['grand_total']}"
    )
    return result


if __name__ == "__main__":
    run_dag()
