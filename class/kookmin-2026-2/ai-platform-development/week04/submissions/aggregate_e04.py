# -*- coding: utf-8 -*-
"""
빛담 가을사진전(E04) 집계 스크립트
- data/의 CSV 3개(참가신청, 회계내역, 구매계획)를 전체 읽어 집계한다.
- 원본은 수정하지 않는다(읽기 전용). 결과 JSON은 submissions/에 저장한다.

근거 문서/조항:
- ACCOUNT-01 제1조: 기초잔액(학교지원금 0, 동아리회비 800,000), 처리완료 120건, E01~E04 혼재
- ACCOUNT-01 제2조: 부호 = 수입/환불입금(+), 지출/환불지급(-)
- ACCOUNT-01 제3조: 현재잔액 = 기초 + 수입 + 환불입금 - 지출 - 환불지급
                    E04 순지출 = 지출 + 환불지급 - 환불입금 (수입 제외)
- ACCOUNT-01 제5조: 구매계획 '참가자'=확정인원*계수, '고정'=계수 자체. 회계에 합산하지 않음
- CLUB-01 제1조/제3조: 물품 기본 인원 = 확정 인원. 대기자는 미리 더하지 않음
- APPROVAL-SPACE-04 + RULE-02: 승인 정원 160명
- MEMO-04: 홍보 180명 vs 승인 160명, 180 변경은 '요청 예정'(승인 기록 없음 → 확인 필요)
"""
import csv
import json
import os
from datetime import datetime, timezone, timedelta

BASE = os.path.join(
    os.environ["USERPROFILE"], "Desktop", "nxt-kirocrew-hands-on",
    "class", "kookmin-2026-2", "ai-platform-development", "week04",
)
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "submissions")
EVENT = "E04"

# ACCOUNT-01 제1조: 기초 잔액
OPENING = {"학교지원금": 0, "동아리회비": 800000}


def read_csv(name):
    path = os.path.join(DATA, name)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, path


def main():
    apps, apps_path = read_csv("참가신청.csv")
    acct, acct_path = read_csv("회계내역.csv")
    plan, plan_path = read_csv("구매계획.csv")

    rows_read = {"참가신청": len(apps), "회계내역": len(acct), "구매계획": len(plan)}
    needs_review = []

    # ---- 1) 참가 상태별 인원 (E04만) ----
    e04_apps = [r for r in apps if r["행사_ID"] == EVENT]
    status_count = {"확정": 0, "대기": 0, "취소": 0, "기타": 0}
    for r in e04_apps:
        s = r["신청상태"].strip()
        if s in status_count:
            status_count[s] += 1
        else:
            status_count["기타"] += 1
            needs_review.append(f"참가신청 {r['신청_ID']}: 알 수 없는 신청상태 '{s}' (확인 필요)")

    confirmed = [r for r in e04_apps if r["신청상태"].strip() == "확정"]
    confirmed_n = len(confirmed)  # CLUB-01 제1조: 물품 기본 인원 = 확정 인원

    # ---- 2) 확정자의 선택 (인화체험 / 식음료) ----
    def choice_breakdown(field):
        c = {"신청": 0, "미신청": 0, "받지않음": 0, "기타": 0}
        for r in confirmed:
            v = r.get(field, "").strip()
            if v in c:
                c[v] += 1
            else:
                c["기타"] += 1
                needs_review.append(f"참가신청 {r['신청_ID']}: '{field}' 이상값 '{v}' (확인 필요)")
        return c

    confirmed_choices = {
        "인화체험": choice_breakdown("인화체험"),
        "식음료": choice_breakdown("식음료"),
    }

    # ---- 3) 회계: 재원별 현재 잔액 + E04 순지출 ----
    # ACCOUNT-01 제2조 부호. 유형: 수입/지출/환불입금/환불지급
    def to_int(v, rid):
        try:
            return int(v)
        except (ValueError, TypeError):
            needs_review.append(f"회계내역 {rid}: 금액 파싱 불가 '{v}' (확인 필요)")
            return 0

    # 재원별 현재 잔액 (전체 행사 E01~E04 합산, 기초잔액 포함)
    balance = {k: v for k, v in OPENING.items()}
    unknown_types = set()
    for r in acct:
        fund = r["재원"].strip()
        typ = r["유형"].strip()
        amt = to_int(r["금액"], r["거래_ID"])
        balance.setdefault(fund, OPENING.get(fund, 0))
        if typ in ("수입", "환불입금"):
            balance[fund] += amt
        elif typ in ("지출", "환불지급"):
            balance[fund] -= amt
        else:
            unknown_types.add(typ)
            needs_review.append(f"회계내역 {r['거래_ID']}: 알 수 없는 유형 '{typ}' (부호 미적용, 확인 필요)")

    # E04 재원별 순지출 = 지출 + 환불지급 - 환불입금 (수입 제외)
    e04_net = {}
    for r in acct:
        if r["행사_ID"].strip() != EVENT:
            continue
        fund = r["재원"].strip()
        typ = r["유형"].strip()
        amt = to_int(r["금액"], r["거래_ID"])
        e04_net.setdefault(fund, 0)
        if typ in ("지출", "환불지급"):
            e04_net[fund] += amt
        elif typ == "환불입금":
            e04_net[fund] -= amt
        # 수입은 순지출에서 제외 (ACCOUNT-01 제3조)
    e04_net_total = sum(e04_net.values())

    # ---- 4) 구매계획: 140 / 160 / 180 시나리오 ----
    # ACCOUNT-01 제5조: '참가자'=인원*계수, '고정'=계수 자체. 단가*수량=예정비용
    scenarios = {"140": 140, "160": 160, "180": 180, "확정인원": confirmed_n}
    plan_result = {}
    for label, n in scenarios.items():
        by_fund = {}
        items = []
        for p in plan:
            coef = int(p["계수"])
            unit = int(p["단가"])
            basis = p["수량기준"].strip()
            if basis == "참가자":
                qty = n * coef
            elif basis == "고정":
                qty = coef
            else:
                qty = coef
                needs_review.append(f"구매계획 {p['항목_ID']}: 알 수 없는 수량기준 '{basis}' (고정 처리, 확인 필요)")
            cost = qty * unit
            fund = p["예정재원"].strip()
            by_fund[fund] = by_fund.get(fund, 0) + cost
            items.append({
                "항목_ID": p["항목_ID"], "물품": p["물품"], "수량기준": basis,
                "수량": qty, "단가": unit, "예정비용": cost, "예정재원": fund,
            })
        plan_result[label] = {
            "인원": n,
            "재원별_예정비용": by_fund,
            "총_예정비용": sum(by_fund.values()),
            "항목": items,
        }

    # ---- 정원 근거 (주입된 지식 기반만 사용) ----
    capacity = {
        "승인_정원": 160,
        "근거": "APPROVAL-SPACE-04(장소 승인 정원) + 공간이용안내 RULE-02",
        "홍보_정원": 180,
        "홍보_근거": "홍보 안내 180명 (승인서 아님)",
        "변경요청_180": "MEMO-04(2026-09-18): 180명 변경 요청 '예정', 변경 승인 기록 없음",
        "180_승인여부": "확인 필요 — 주입된 지식만으로는 정원변경 승인 확인 불가",
    }

    KST = timezone(timedelta(hours=9))
    result = {
        "행사_ID": EVENT,
        "생성시각_KST": datetime.now(KST).isoformat(),
        "읽은_행수": rows_read,
        "정원": capacity,
        "참가상태별_인원_E04": status_count,
        "확정_인원": confirmed_n,
        "확정자_선택": confirmed_choices,
        "회계": {
            "기초잔액": OPENING,
            "재원별_현재잔액": balance,
            "E04_재원별_순지출": e04_net,
            "E04_순지출_합계": e04_net_total,
            "부호규칙": "수입/환불입금(+), 지출/환불지급(-) [ACCOUNT-01 제2조]",
            "순지출규칙": "E04 순지출 = 지출 + 환불지급 - 환불입금, 수입 제외 [ACCOUNT-01 제3조]",
        },
        "구매계획": plan_result,
        "근거문서": {
            "ACCOUNT-01": "회계 기초잔액·부호·순지출·구매계획 산식",
            "CLUB-01": "확정/대기/취소 구분, 물품 기본 인원=확정, 대기자 미리 더하지 않음",
            "RULE-01": "지원금 대상/제외/증빙",
            "APPROVAL-SPACE-04": "승인 정원 160 (RULE-02와 함께)",
            "MEMO-04": "정원변경 '요청 예정' 기록(승인 전 단계), 외부인 참가 미결정",
        },
        "확인필요": needs_review,
    }

    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, "E04_집계.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 콘솔 요약 (UTF-8) + 파일 로그 (셸 인코딩 우회)
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    lines = []
    lines.append(f"== 읽은 행 수 == {rows_read}")
    lines.append(f"== 참가상태별(E04) == {status_count} 확정={confirmed_n}")
    lines.append(f"== 확정자 선택 == {confirmed_choices}")
    lines.append(f"== 재원별 현재잔액 == {balance}")
    lines.append(f"== E04 순지출 == {e04_net} 합계={e04_net_total}")
    for k in ("140", "160", "180", "확정인원"):
        v = plan_result[k]
        lines.append(f"== 구매계획 {k}({v['인원']}명) == {v['재원별_예정비용']} 총={v['총_예정비용']}")
    lines.append(f"== 확인필요 == {needs_review if needs_review else '없음'}")
    lines.append(f"saved: {out_path}")
    text = "\n".join(lines)
    log_path = os.path.join(OUT, "E04_실행결과.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
