# -*- coding: utf-8 -*-
"""E04 운영 보고서 렌더러 (data-to-html 역할분담 원칙 적용).

숫자·구조는 E04_집계.json(코드가 만든 사실)에서 그대로 읽고,
총평·운영안·추가 확인 문장은 report_summaries.json(AI 작성)에서 읽는다.
AI가 숫자를 재계산하지 않는다.

근거 문서: ACCOUNT-01, CLUB-01, RULE-01, APPROVAL-SPACE-04(+RULE-02), MEMO-04
"""
import datetime
import html
import json
import os

SUB = os.path.join(
    os.environ["USERPROFILE"], "Desktop", "nxt-kirocrew-hands-on",
    "class", "kookmin-2026-2", "ai-platform-development", "week04", "submissions",
)
AGG = os.path.join(SUB, "E04_집계.json")
SUMM = os.path.join(SUB, "report_summaries.json")
OUT = os.path.join(SUB, "운영보고서_초기.html")


def esc(s):
    return html.escape(str(s), quote=True)


def won(n):
    return f"{int(n):,}원"


CSS = """
  :root { color-scheme: light dark; }
  body { font-family: system-ui, "Segoe UI", "Malgun Gothic", sans-serif;
         max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; }
  h1 { border-bottom: 2px solid #4a6; padding-bottom: .3rem; }
  h2 { margin-top: 2rem; color: #4a6; }
  .meta { color: #888; margin: .2rem 0; font-size: .9rem; }
  table { border-collapse: collapse; width: 100%; margin-top: .5rem; }
  th, td { border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }
  th { background: rgba(74,170,102,.15); }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .dim { color: #999; }
  .badge { display:inline-block; padding:.1rem .5rem; border-radius:.5rem; font-size:.8rem;
           background:rgba(74,170,102,.18); color:#2a7; margin-left:.4rem; }
  .warn { color:#c33; }
  ul.review li { margin:.3rem 0; }
  .basis { color:#777; font-size:.85rem; }
  .opt { border:1px solid #ccc; border-radius:.6rem; padding:.8rem 1rem; margin:.7rem 0; }
  .opt h3 { margin:.2rem 0 .4rem; }
  footer { margin-top: 2.5rem; color: #aaa; font-size: .8rem; }
"""


def main():
    with open(AGG, encoding="utf-8") as f:
        agg = json.load(f)
    with open(SUMM, encoding="utf-8") as f:
        summ = json.load(f)

    today = datetime.date.today().isoformat()
    cap = agg["정원"]
    st = agg["참가상태별_인원_E04"]
    ch = agg["확정자_선택"]
    acc = agg["회계"]
    plan = agg["구매계획"]
    rows_read = agg["읽은_행수"]

    # 구매계획 비교 표: 140/160/180
    def plan_row(label):
        p = plan[label]
        bf = p["재원별_예정비용"]
        return (bf.get("학교지원금", 0), bf.get("동아리회비", 0), p["총_예정비용"])

    p140 = plan_row("140")
    p160 = plan_row("160")
    p180 = plan_row("180")

    # 운영안 카드
    opt_html = []
    for o in summ["options"]:
        opt_html.append(
            f"""    <div class="opt">
      <h3>{esc(o['name'])}</h3>
      <p>{esc(o['desc'])}</p>
      <p class="basis">근거: {esc(o['basis'])}</p>
    </div>"""
        )
    opts = "\n".join(opt_html)

    follow = "\n".join(f"      <li>{esc(x)}</li>" for x in summ["follow_ups"])

    doc = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>빛담 가을사진전(E04) 운영 보고서</title>
<style>{CSS}</style>
</head><body>
  <h1>빛담 가을사진전(E04) 운영 보고서</h1>
  <p class="meta">생성일 {today} · 행사 ID E04</p>
  <p class="meta">읽은 행 수: 참가신청 {rows_read['참가신청']} · 회계내역 {rows_read['회계내역']} · 구매계획 {rows_read['구매계획']}</p>

  <section>
    <h2>개요</h2>
    <p>{esc(summ['overview'])}</p>
    <p class="meta">승인 정원 <b>{cap['승인_정원']}명</b>
       <span class="badge">근거 {esc(cap['근거'])}</span></p>
    <p class="meta warn">홍보 정원 {cap['홍보_정원']}명 — {esc(cap['180_승인여부'])}</p>
  </section>

  <section>
    <h2>참가 현황</h2>
    <table>
      <thead><tr><th>상태</th><th class="num">인원</th><th>비고</th></tr></thead>
      <tbody>
        <tr><td>확정</td><td class="num">{st['확정']}</td><td>물품 기본 인원 (CLUB-01 제1조)</td></tr>
        <tr><td>대기</td><td class="num">{st['대기']}</td><td>미리 더하지 않음 (CLUB-01 제3조)</td></tr>
        <tr><td>취소</td><td class="num">{st['취소']}</td><td>-</td></tr>
      </tbody>
    </table>
    <h3>확정자({agg['확정_인원']}명)의 선택</h3>
    <table>
      <thead><tr><th>항목</th><th class="num">신청</th><th class="num">미신청</th><th class="num">받지않음</th></tr></thead>
      <tbody>
        <tr><td>인화체험</td><td class="num">{ch['인화체험']['신청']}</td><td class="num">{ch['인화체험']['미신청']}</td><td class="num">{ch['인화체험']['받지않음']}</td></tr>
        <tr><td>식음료</td><td class="num">{ch['식음료']['신청']}</td><td class="num">{ch['식음료']['미신청']}</td><td class="num">{ch['식음료']['받지않음']}</td></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>회계 · 잔액</h2>
    <table>
      <thead><tr><th>재원</th><th class="num">기초잔액</th><th class="num">현재잔액</th><th class="num">E04 순지출</th></tr></thead>
      <tbody>
        <tr><td>학교지원금</td><td class="num">{won(acc['기초잔액']['학교지원금'])}</td><td class="num">{won(acc['재원별_현재잔액']['학교지원금'])}</td><td class="num">{won(acc['E04_재원별_순지출']['학교지원금'])}</td></tr>
        <tr><td>동아리회비</td><td class="num">{won(acc['기초잔액']['동아리회비'])}</td><td class="num">{won(acc['재원별_현재잔액']['동아리회비'])}</td><td class="num">{won(acc['E04_재원별_순지출']['동아리회비'])}</td></tr>
        <tr><td><b>합계</b></td><td class="num">-</td><td class="num">-</td><td class="num"><b>{won(acc['E04_순지출_합계'])}</b></td></tr>
      </tbody>
    </table>
    <p class="basis">{esc(acc['부호규칙'])} · {esc(acc['순지출규칙'])}</p>
  </section>

  <section>
    <h2>구매계획 비교 (140 · 160 · 180명)</h2>
    <table>
      <thead><tr><th>인원 시나리오</th><th class="num">학교지원금</th><th class="num">동아리회비</th><th class="num">총 예정비용</th></tr></thead>
      <tbody>
        <tr><td>140명 (확정 기준)</td><td class="num">{won(p140[0])}</td><td class="num">{won(p140[1])}</td><td class="num">{won(p140[2])}</td></tr>
        <tr><td>160명 (승인 정원)</td><td class="num">{won(p160[0])}</td><td class="num">{won(p160[1])}</td><td class="num">{won(p160[2])}</td></tr>
        <tr><td>180명 (홍보 정원)</td><td class="num">{won(p180[0])}</td><td class="num">{won(p180[1])}</td><td class="num">{won(p180[2])}</td></tr>
      </tbody>
    </table>
    <p class="basis">산식: '참가자'=인원×계수, '고정'=계수 자체 (ACCOUNT-01 제5조). 구매계획은 예정치이며 회계에 합산하지 않음 (제4조).</p>
  </section>

  <section>
    <h2>가능한 운영안</h2>
{opts}
  </section>

  <section>
    <h2>추가 확인 사항</h2>
    <ul class="review">
{follow}
    </ul>
  </section>

  <section>
    <h2>판단에 사용한 문서 근거</h2>
    <table>
      <thead><tr><th>문서 ID</th><th>사용 내용</th></tr></thead>
      <tbody>
        <tr><td>ACCOUNT-01</td><td>기초잔액 · 부호 규칙 · E04 순지출 · 구매계획 산식</td></tr>
        <tr><td>CLUB-01</td><td>확정/대기/취소 구분, 물품 기본 인원=확정, 대기자 미가산, 회비 기념품 요건</td></tr>
        <tr><td>RULE-01</td><td>지원금 대상/제외/증빙, 식음료 1인 4,000원 이내</td></tr>
        <tr><td>APPROVAL-SPACE-04 (+RULE-02)</td><td>승인 참가 정원 160명</td></tr>
        <tr><td>MEMO-04</td><td>홍보 180 vs 승인 160, 180 변경 '요청 예정'(승인 기록 없음), 외부인 참가 미결정</td></tr>
      </tbody>
    </table>
  </section>

  <footer>data-to-html 스킬 기반 운영 보고서 · 숫자=코드 집계, 문장=AI 요약 · {today}</footer>
</body></html>"""

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    print("saved:", OUT, len(doc), "bytes")


if __name__ == "__main__":
    main()
