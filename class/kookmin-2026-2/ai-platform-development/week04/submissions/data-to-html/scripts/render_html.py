#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""facts.json(수집·파싱 사실) + summaries.json(AI 요약)을 합쳐
문서 요약 + 핵심 표를 담은 HTML 한 파일을 만들어 저장한다.

표·파일 목록·확인 필요는 facts에서 그대로 그리고,
개요 총평과 문서 한 줄 요약은 summaries가 있으면 채운다.
"""
import argparse
import datetime
import html
import json
import os
import sys


def esc(s):
    return html.escape(str(s), quote=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_overview(facts, summaries):
    c = facts.get("counts", {})
    dir_ = facts.get("dir") or "(파일 직접 지정)"
    overview_text = (summaries or {}).get("overview") or "(요약 미작성)"
    return f"""  <section>
    <h2>개요</h2>
    <p class="meta">대상: <code>{esc(dir_)}</code></p>
    <p class="meta">파일 수: md {c.get('md', 0)}개 · csv {c.get('csv', 0)}개 · 건너뜀 {c.get('skipped', 0)}개</p>
    <p>{esc(overview_text)}</p>
  </section>"""


def render_summaries(facts, summaries):
    file_notes = (summaries or {}).get("files", {})
    rows = []
    for f in facts.get("files", []):
        if f.get("error") or f.get("review"):
            continue  # 확인 필요 섹션에서 다룸
        path = f.get("path", "")
        note = file_notes.get(path, "(요약 미작성)")
        rows.append(
            f"""      <tr>
        <td class="path">{esc(path)}</td>
        <td>{esc(note)}</td>
      </tr>"""
        )
    body = "\n".join(rows) if rows else '      <tr><td colspan="2" class="dim">요약할 파일 없음</td></tr>'
    return f"""  <section>
    <h2>문서 요약</h2>
    <table>
      <thead><tr><th>파일</th><th>요약</th></tr></thead>
      <tbody>
{body}
      </tbody>
    </table>
  </section>"""


def render_key_table(facts):
    rows = []
    for f in facts.get("files", []):
        if f.get("type") != "csv":
            continue
        ns = f.get("numeric_summary", {})
        for col, stat in ns.items():
            rows.append(
                f"""      <tr>
        <td class="path">{esc(f.get('path', ''))}</td>
        <td>{esc(col)}</td>
        <td class="num">{esc(stat.get('sum'))}</td>
        <td class="num">{esc(stat.get('mean'))}</td>
        <td class="num">{esc(stat.get('count'))}</td>
      </tr>"""
            )
    if not rows:
        return """  <section>
    <h2>핵심 표</h2>
    <p class="dim">해당 없음 (집계할 수치 컬럼이 없음)</p>
  </section>"""
    body = "\n".join(rows)
    return f"""  <section>
    <h2>핵심 표</h2>
    <table>
      <thead><tr><th>파일</th><th>컬럼</th><th>합계</th><th>평균</th><th>개수</th></tr></thead>
      <tbody>
{body}
      </tbody>
    </table>
  </section>"""


def render_needs_review(facts):
    items = facts.get("needs_review", [])
    if not items:
        return """  <section>
    <h2>확인 필요</h2>
    <p class="dim">없음</p>
  </section>"""
    lis = "\n".join(f"      <li>{esc(x)}</li>" for x in items)
    return f"""  <section>
    <h2>확인 필요</h2>
    <ul class="review">
{lis}
    </ul>
  </section>"""


CSS = """
  :root { color-scheme: light dark; }
  body { font-family: system-ui, "Segoe UI", "Malgun Gothic", sans-serif;
         max-width: 900px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
  h1 { border-bottom: 2px solid #4a6; padding-bottom: .3rem; }
  h2 { margin-top: 2rem; color: #4a6; }
  .meta { color: #888; margin: .2rem 0; font-size: .9rem; }
  table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
  th, td { border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }
  th { background: rgba(74,170,102,.15); }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.path, .path { font-family: ui-monospace, Consolas, monospace; font-size: .85rem; }
  .dim { color: #999; }
  ul.review li { color: #c33; }
  footer { margin-top: 2.5rem; color: #aaa; font-size: .8rem; }
"""


def build_html(facts, summaries, title):
    today = datetime.date.today().isoformat()
    parts = [
        "<!DOCTYPE html>",
        '<html lang="ko"><head><meta charset="utf-8">',
        f"<title>{esc(title)}</title>",
        f"<style>{CSS}</style>",
        "</head><body>",
        f"  <h1>{esc(title)}</h1>",
        f'  <p class="meta">생성일 {today}</p>',
        render_overview(facts, summaries),
        render_summaries(facts, summaries),
        render_key_table(facts),
        render_needs_review(facts),
        f'  <footer>data-to-html 스킬로 생성 · {today}</footer>',
        "</body></html>",
    ]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="facts.json + summaries.json -> HTML 리포트")
    ap.add_argument("--facts", required=True, help="collect_docs.py가 만든 facts.json")
    ap.add_argument("--summaries", help="AI가 만든 summaries.json (개요·파일별 요약)")
    ap.add_argument("--title", default="문서 취합 요약", help="HTML 제목")
    ap.add_argument("--submissions", help="저장 폴더. 여기에 data-to-html_YYYY-MM-DD.html로 저장")
    ap.add_argument("--out", help="저장 경로/파일명 직접 지정 (--submissions보다 우선)")
    args = ap.parse_args()

    facts = load_json(args.facts)
    summaries = load_json(args.summaries) if args.summaries else None
    doc = build_html(facts, summaries, args.title)

    if args.out:
        out_path = args.out
    elif args.submissions:
        os.makedirs(args.submissions, exist_ok=True)
        fname = f"data-to-html_{datetime.date.today().isoformat()}.html"
        out_path = os.path.join(args.submissions, fname)
    else:
        print("저장 위치가 없습니다. --submissions 또는 --out을 주세요.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
