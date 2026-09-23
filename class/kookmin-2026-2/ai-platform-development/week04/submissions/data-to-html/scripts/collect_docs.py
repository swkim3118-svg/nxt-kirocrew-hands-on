#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""여러 md·csv 파일을 수집·파싱해 '사실 JSON'을 만든다.

숫자·구조는 이 스크립트가, 문장 요약은 AI가 맡는다.
파일을 읽지 못해도 전체 실행을 멈추지 않고, 그 파일을 needs_review에 남긴다.
"""
import argparse
import csv
import io
import json
import os
import re
import sys

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr")


def read_text(path):
    """텍스트 파일을 인코딩을 바꿔가며 읽는다. 실패하면 (None, 사유)."""
    for enc in CSV_ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), None
        except (UnicodeDecodeError, LookupError):
            continue
        except OSError as e:
            return None, f"열기 실패: {e}"
    return None, "인코딩을 알 수 없음(utf-8/cp949 모두 실패)"


def parse_md(path, rel):
    text, err = read_text(path)
    if err:
        return {"path": rel, "type": "md", "error": err}, err
    lines = text.splitlines()
    # 첫 번째 # 제목
    title = None
    headings = []
    for ln in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", ln.strip())
        if m:
            heading = m.group(2).strip()
            headings.append(heading)
            if title is None:
                title = heading
    if title is None:
        title = os.path.basename(path)
    words = len(re.findall(r"\S+", text))
    preview = text.strip().replace("\n", " ")[:200]
    empty = words == 0
    entry = {
        "path": rel,
        "type": "md",
        "title": title,
        "headings": headings[:20],
        "word_count": words,
        "preview": preview,
        "error": None,
    }
    return entry, ("본문이 비어 있음" if empty else None)


def _to_float(s):
    if s is None:
        return None
    s = s.strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_csv(path, rel):
    raw, err = read_text(path)
    if err:
        return {"path": rel, "type": "csv", "error": err}, err
    try:
        reader = list(csv.reader(io.StringIO(raw)))
    except csv.Error as e:
        return {"path": rel, "type": "csv", "error": f"csv 파싱 실패: {e}"}, f"csv 파싱 실패: {e}"
    if not reader:
        return {"path": rel, "type": "csv", "error": "빈 파일"}, "빈 파일"
    header = reader[0]
    body = reader[1:]
    # 숫자 컬럼 집계
    numeric_summary = {}
    for ci, col in enumerate(header):
        vals = []
        for row in body:
            if ci < len(row):
                v = _to_float(row[ci])
                if v is not None:
                    vals.append(v)
        # 값의 절반 이상이 숫자로 읽히면 숫자 컬럼으로 본다
        if vals and len(vals) >= max(1, len(body) / 2):
            total = sum(vals)
            numeric_summary[col] = {
                "sum": round(total, 4),
                "mean": round(total / len(vals), 4),
                "count": len(vals),
            }
    entry = {
        "path": rel,
        "type": "csv",
        "rows": len(body),
        "columns": header,
        "numeric_summary": numeric_summary,
        "preview_rows": body[:3],
        "error": None,
    }
    return entry, ("데이터 행이 없음" if len(body) == 0 else None)


def collect(paths, base_dir):
    files = []
    needs_review = []
    counts = {"md": 0, "csv": 0, "skipped": 0}
    for p in paths:
        rel = os.path.relpath(p, base_dir) if base_dir else os.path.basename(p)
        ext = os.path.splitext(p)[1].lower()
        if ext in (".md", ".markdown"):
            entry, note = parse_md(p, rel)
            counts["md"] += 1
        elif ext == ".csv":
            entry, note = parse_csv(p, rel)
            counts["csv"] += 1
        else:
            counts["skipped"] += 1
            continue
        files.append(entry)
        if entry.get("error"):
            entry["review"] = True
            needs_review.append(f"{rel}: {entry['error']}")
        elif note:
            entry["review"] = True
            needs_review.append(f"{rel}: {note}")
    return files, needs_review, counts


def gather_from_dir(dirpath, recursive):
    out = []
    if recursive:
        for root, _dirs, names in os.walk(dirpath):
            for n in names:
                out.append(os.path.join(root, n))
    else:
        for n in os.listdir(dirpath):
            fp = os.path.join(dirpath, n)
            if os.path.isfile(fp):
                out.append(fp)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description="md·csv 파일 수집·파싱 → 사실 JSON")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", help="훑을 폴더")
    src.add_argument("--files", nargs="+", help="파일 목록 직접 지정")
    ap.add_argument("--no-recursive", action="store_true", help="하위 폴더 제외 (--dir 전용)")
    ap.add_argument("--out", help="결과 JSON 저장 경로 (생략 시 표준출력)")
    args = ap.parse_args()

    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"폴더를 찾을 수 없음: {args.dir}", file=sys.stderr)
            sys.exit(1)
        base_dir = args.dir
        paths = gather_from_dir(args.dir, recursive=not args.no_recursive)
    else:
        paths = args.files
        base_dir = os.path.commonpath([os.path.dirname(os.path.abspath(p)) for p in paths]) if paths else None

    files, needs_review, counts = collect(paths, base_dir)
    result = {
        "dir": args.dir,
        "counts": counts,
        "files": files,
        "needs_review": needs_review,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"저장 완료: {args.out}  (md {counts['md']} / csv {counts['csv']} / 건너뜀 {counts['skipped']})")
    else:
        print(text)


if __name__ == "__main__":
    main()
