#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_notices.py

parse_notices.py 로 구조화한 공지 목록을 입력받아
기준 시각(2026-09-14 09:00, Asia/Seoul) 기준으로 가공한다.

이 모듈의 책임 범위(Task 3):
    - 기준 시각 상수 정의
    - 기준 시각 기준 이미 마감된 공지를 제외하는 필터 구현
      · 마감일이 명시되지 않은 공지는 유지한다.
      · 마감일에 시각이 명시되지 않은(날짜만 있는) 공지는
        해당 날짜의 '마감(= 그 날의 끝)'으로 보아 23:59:59 로 간주한다.
        → '2026-09-14까지' 신청 공지는 09-14 09:00 기준 아직 유효(미마감).

이 모듈의 책임 범위(Task 4 — 정정 병합):
    - 동일 공지 건(동일 업무/행사 work_id, 또는 correction_target 로 지목된 원본)의
      정정 공지를 하나의 항목으로 병합한다.
    - 정정으로 '변경된 사항'만 결과에 반영한다.
      · 정정 공지에 명시된 새 일정/일시·장소 등은 반영한다.
      · 정정 공지가 "나머지는 N03과 동일" 이라고 하면 원본 값을 유지한다.
    - 출처(source_ids)에 원본 ID와 정정 ID를 모두 수집한다(원본 → 정정 순).
    - 병합 결과는 원본 공지 항목을 기준으로 삼되, 변경 필드만 덮어쓴다.

정렬(Task 5)과 렌더링(Task 6)은 아래에 구현되어 있다.
Task 6: 각 공지를 지정된 출력 형식(제목 / 핵심 안내 / 관련 일정 / 출처 / 선택적 확인 필요)
으로 렌더링하는 render_notice·render_briefing 함수를 제공한다.

주의: 과제 설명 경로는 mission/mission/data/notices.md 이나
실제 파일은 week05/mission/data/notices.md (단일 mission) 에 있다.
parse_notices.py 가 이를 처리하므로 여기서는 그 산출물을 사용한다.
"""

from __future__ import annotations

import json
from datetime import datetime, time
from pathlib import Path
from typing import Optional

# 같은 scripts 디렉터리의 파서를 재사용
from parse_notices import (  # noqa: E402
    NOTICES_PATH,
    SOURCE_LABEL,
    parse_notices,
)

# ---------------------------------------------------------------------------
# 기준 시각 상수 (Asia/Seoul, 2026-09-14 09:00)
# ---------------------------------------------------------------------------
# 공지 원문의 모든 시각이 KST(Asia/Seoul) 기준이고 서로 동일 시간대이므로,
# 비교 목적상 naive datetime 으로 둔다(모든 값이 같은 로컬 시간대).
CUTOFF = datetime(2026, 9, 14, 9, 0)
CUTOFF_LABEL = "2026-09-14 09:00"
TIMEZONE = "Asia/Seoul"

SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_deadline(notice: dict) -> Optional[datetime]:
    """
    공지 dict 에서 비교 가능한 마감 datetime 을 산출한다.

    - deadline(ISO 문자열) 이 있으면 그것을 사용한다.
    - 단, 원문 표기(deadline_raw)에 시각이 없고 날짜만 있는 경우
      '그 날까지' 를 의미하므로 해당 날짜의 끝(23:59:59)으로 보정한다.
    - 마감 정보가 없으면 None.
    """
    raw_iso = notice.get("deadline")
    if not raw_iso:
        return None

    dt = datetime.fromisoformat(raw_iso)

    deadline_raw = notice.get("deadline_raw") or ""
    has_explicit_time = ":" in deadline_raw  # 'YYYY-MM-DD HH:MM' 형태면 시각 명시
    if not has_explicit_time:
        # 날짜만 명시된 '…까지' 마감 → 해당 일자 종료 시점으로 간주
        dt = datetime.combine(dt.date(), time(23, 59, 59))
    return dt


def is_open_at(notice: dict, cutoff: datetime = CUTOFF) -> bool:
    """
    기준 시각(cutoff)에 해당 공지가 아직 '유효(미마감)' 인지 여부.

    - 마감일이 없으면 항상 유효(True).
    - 마감일이 cutoff 이상(>=)이면 유효(True).
      (cutoff 와 정확히 같은 순간은 아직 마감 전으로 본다.)
    - 마감일이 cutoff 미만이면 이미 마감(False).
    """
    deadline = _resolve_deadline(notice)
    if deadline is None:
        return True
    return deadline >= cutoff


def filter_open_notices(notices: list[dict], cutoff: datetime = CUTOFF) -> list[dict]:
    """기준 시각 기준으로 이미 마감된 공지를 제외한 목록을 반환한다."""
    return [n for n in notices if is_open_at(n, cutoff)]


# ---------------------------------------------------------------------------
# 정정 병합 (Task 4)
# ---------------------------------------------------------------------------
def _ensure_source_ids(notice: dict) -> list[str]:
    """공지 항목에 source_ids(출처 ID 목록)를 보장하고 반환한다."""
    sids = notice.get("source_ids")
    if not sids:
        sids = [notice["id"]]
        notice["source_ids"] = sids
    return sids


def _find_base_notice(
    correction: dict, by_id: dict[str, dict], notices: list[dict]
) -> Optional[dict]:
    """
    정정 공지가 가리키는 원본 공지를 찾는다.

    1순위: correction_target 으로 지목된 ID
    2순위: 동일 work_id(업무/행사 ID)를 가진 비(非)정정 원본
    """
    target_id = correction.get("correction_target")
    if target_id and target_id in by_id:
        return by_id[target_id]

    work_id = correction.get("work_id")
    if work_id:
        for n in notices:
            if (
                n is not correction
                and not n.get("is_correction")
                and n.get("work_id") == work_id
            ):
                return n
    return None


def _apply_correction(base: dict, correction: dict) -> None:
    """
    정정 공지(correction)의 '변경된 사항'을 원본(base)에 반영한다.

    - 변경된 일정/일시: 정정 본문의 schedules 를 '변경 반영' 형태로 base.schedules 에
      대체 적용한다(원본의 옛 일정은 '취소'로 대체).
    - 변경 요약: base['correction_summary'] 에 정정 내용을 기록한다.
    - 그 외 '동일' 로 명시된 항목(장소/대상/신청/준비물 등)은 원본 값을 유지한다.
    - 출처: base['source_ids'] 에 정정 ID를 추가한다(중복 방지, 원본→정정 순서 유지).
    """
    base_ids = _ensure_source_ids(base)
    corr_id = correction["id"]
    if corr_id not in base_ids:
        base_ids.append(corr_id)

    # 행사/업무 ID(work_id)도 원본·정정 양쪽에서 수집한다(중복 제거, 순서 보존).
    work_ids = base.setdefault("work_ids", [])
    for wid in (base.get("work_id"), correction.get("work_id")):
        if wid and wid not in work_ids:
            work_ids.append(wid)

    # 정정으로 바뀐 일정은 정정 본문의 일정으로 대체한다.
    corr_schedules = correction.get("schedules") or []
    if corr_schedules:
        # 마크다운 강조(**...**) 제거하여 깔끔히 반영
        cleaned = [s.replace("**", "").strip() for s in corr_schedules]
        base["schedules"] = cleaned
        base["schedule_corrected"] = True

    # 정정 본문/마감 등 변경 필드 반영 (정정에 값이 있을 때만 덮어씀)
    if correction.get("deadline"):
        base["deadline"] = correction["deadline"]
        base["deadline_raw"] = correction.get("deadline_raw")

    # 변경 요약 기록 (렌더링 단계에서 '변경된 사항'을 명확히 표기하기 위함)
    summary = correction.get("body", "").replace("**", "").strip()
    base["correction_summary"] = summary
    base["is_corrected"] = True

    # 정정 공지의 게시 시각이 더 최신이면 반영
    if correction.get("posted"):
        base["last_updated"] = correction["posted"]


def merge_corrections(notices: list[dict]) -> list[dict]:
    """
    동일 공지 건의 정정 사항을 하나의 항목으로 병합한다.

    - 정정 공지(is_correction=True)를 찾아 대응하는 원본에 변경사항을 반영하고
      정정 공지 자체는 결과 목록에서 제거한다.
    - 출처 ID(source_ids)에는 원본 ID와 정정 ID가 모두 수집된다.
    - 원본이 (예: 마감되어) 목록에 없는데 정정만 남은 경우에는, 정정 공지를
      독립 항목으로 유지하되 source_ids 에 correction_target 도 함께 수집한다.

    입력 목록을 변형하지 않도록 깊은 복사본에서 작업한다.
    """
    import copy

    work = copy.deepcopy(notices)
    by_id = {n["id"]: n for n in work}

    merged_out: list[str] = []  # 병합되어 사라진 정정 공지 ID
    for n in work:
        _ensure_source_ids(n)

    for n in work:
        if not n.get("is_correction"):
            continue
        base = _find_base_notice(n, by_id, work)
        if base is not None:
            _apply_correction(base, n)
            merged_out.append(n["id"])
        else:
            # 원본을 못 찾은 정정: 독립 항목으로 두되 대상 ID도 출처에 수집
            tgt = n.get("correction_target")
            if tgt and tgt not in n["source_ids"]:
                n["source_ids"].insert(0, tgt)
            n["is_corrected"] = True
            n["correction_summary"] = n.get("body", "").replace("**", "").strip()

    result = [n for n in work if n["id"] not in merged_out]
    return result


# ---------------------------------------------------------------------------
# 독자 우선 정렬 (Task 5)
# ---------------------------------------------------------------------------
# 대상 독자: 소프트웨어 학부 학생.
# 정렬 규칙(우선순위 순):
#   1) 소프트웨어 학부 학생과 관련된 공지(sw_relevant=True)를 먼저 배치한다.
#   2) 같은 관련성 그룹 안에서는 '마감 임박' 공지를 먼저 배치한다.
#      - 기준 시각(CUTOFF) 대비 남은 기간이 짧을수록(= 마감이 가까울수록) 앞.
#      - 마감 정보가 없는 공지는 임박도가 가장 낮은 것으로 보아 뒤로 보낸다.
#   3) 위 기준이 모두 같으면 공지 ID 순으로 안정 정렬한다.

# "마감 없음" 을 가장 뒤로 보내기 위한 충분히 큰 상수(일 단위)
_FAR_FUTURE_DAYS = 10 ** 9


def _time_remaining_days(notice: dict, cutoff: datetime = CUTOFF) -> float:
    """
    기준 시각(cutoff) 대비 마감까지 남은 기간(일 단위)을 반환한다.

    - 값이 작을수록 마감이 임박했다는 뜻이다(앞에 배치).
    - 마감 정보가 없으면 매우 큰 값(_FAR_FUTURE_DAYS)을 반환하여 맨 뒤로 보낸다.
    - 유효 공지(필터 통과)만 정렬 대상이므로 음수(이미 마감)는 통상 없으나,
      안전하게 그대로 비교에 사용한다.
    """
    deadline = _resolve_deadline(notice)
    if deadline is None:
        return float(_FAR_FUTURE_DAYS)
    return (deadline - cutoff).total_seconds() / 86400.0


def _sort_key(notice: dict, cutoff: datetime = CUTOFF) -> tuple:
    """
    정렬 키.
    - 1차: sw_relevant → 관련 공지가 먼저 오도록 False(0 뒤) 보다 True 를 앞세운다.
           (not True == False == 0 < not False == 1)
    - 2차: 남은 기간(일) 오름차순 → 마감 임박 우선.
    - 3차: ID 오름차순(안정적 tie-break).
    """
    return (
        not bool(notice.get("sw_relevant")),  # 관련(True) → 0, 비관련 → 1
        _time_remaining_days(notice, cutoff),  # 임박할수록 작은 값 → 앞
        notice.get("id", ""),
    )


def sort_for_reader(notices: list[dict], cutoff: datetime = CUTOFF) -> list[dict]:
    """
    소프트웨어 학부 학생 독자 기준으로 공지 목록을 정렬한 '새 리스트'를 반환한다.

    sorted() 는 안정 정렬이므로, 동일 키 공지는 입력 순서를 보존한다.
    """
    return sorted(notices, key=lambda n: _sort_key(n, cutoff))


# ---------------------------------------------------------------------------
# 브리핑 렌더링 (Task 6)
# ---------------------------------------------------------------------------
# 각 공지를 지정된 출력 형식으로 렌더링한다:
#
#   [선별한 공지 제목]
#
#   - 핵심 안내: [독자가 알아야 할 내용]
#   - 관련 일정: [원문에 있는 일정·마감과 현재 상태]
#   - 출처: mission/data/notices.md의 [공지 ID. 병합했다면 관련 ID 모두]
#   - 확인 필요: [필요하지만 원문에 없는 정보. 없으면 이 줄 삭제]
#
# 규칙:
#   - 필요하지만 원문에 없는 정보는 '확인 필요'로 표기한다.
#   - 해당 정보(확인 필요 사항)가 아예 없으면 '- 확인 필요:' 줄 자체를 생략한다.
#   - '관련 일정'에는 원문 일정·마감과 더불어, 정정으로 변경된 경우 그 상태를 함께 표기한다.

# 출처 라벨(과제 지정 경로 표기). 실제 파일은 week05/mission/data/notices.md 이나
# 과제 명세의 출력 형식이 'mission/data/notices.md의 [ID]' 를 요구한다.
BRIEFING_SOURCE_LABEL = "mission/data/notices.md"


def _clean(text: str) -> str:
    """마크다운 강조(**..**)를 제거하고 공백을 정리한다."""
    return (text or "").replace("**", "").strip()


def _format_schedule_status(notice: dict, cutoff: datetime = CUTOFF) -> str:
    """
    공지의 마감 상태를 사람이 읽을 수 있는 짧은 문구로 반환한다.
    - 마감 정보가 없으면 빈 문자열.
    """
    deadline = _resolve_deadline(notice)
    if deadline is None:
        return ""
    remaining = (deadline - cutoff).total_seconds() / 86400.0
    raw = notice.get("deadline_raw") or deadline.strftime("%Y-%m-%d")
    if remaining < 0:
        return f"신청 마감({raw}) 지남"
    days = int(remaining)
    if days <= 0:
        return f"신청 마감 임박({raw}, 당일)"
    if days <= 3:
        return f"신청 마감 임박({raw}까지, 약 {days}일 남음)"
    return f"신청 마감 {raw}까지"


def _build_core_guidance(notice: dict) -> str:
    """
    '핵심 안내' 문구를 구성한다.

    정정으로 일정이 바뀐 공지는 원본 본문(body)에 남아 있는 '취소된 옛 일정'을
    그대로 안내하면 관련 일정(정정된 일시)과 모순된다. 따라서 핵심 안내에서는
    원본 본문의 옛 일정 표기를 제거하고, 정정된 새 일정으로 안내 문장을 재구성한다.
    """
    body = _clean(notice.get("body", ""))

    if not notice.get("is_corrected"):
        return body

    # 정정으로 일정이 바뀐 경우: 옛 일정 문구를 새 일정으로 대체한다.
    if notice.get("schedule_corrected"):
        import re

        new_sched = "; ".join(_clean(s) for s in (notice.get("schedules") or []))
        # 원본 본문에 박힌 옛 일시 패턴(YYYY-MM-DD HH:MM[–HH:MM])을 새 일정으로 치환하여
        # 취소된 일정이 핵심 안내에 그대로 노출되지 않도록 한다.
        new_time = new_sched
        m = re.search(
            r"\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}(?:[–\-~]\d{2}:\d{2})?", new_sched
        )
        if m:
            new_time = m.group(0)
        rewritten = re.sub(
            r"\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}(?:[–\-~]\d{2}:\d{2})?",
            new_time,
            body,
        )
        return f"(일정 정정 반영) {rewritten}"

    # 일정 외 변경(혹은 일정 미기재) 정정은 변경 사실만 앞에 명시한다.
    return f"(일정 정정 반영) {body}"


def _build_schedule_lines(notice: dict, cutoff: datetime = CUTOFF) -> list[str]:
    """'관련 일정' 항목에 들어갈 세부 줄 목록을 구성한다."""
    lines: list[str] = []
    for s in notice.get("schedules") or []:
        lines.append(_clean(s))

    status = _format_schedule_status(notice, cutoff)
    if status:
        lines.append(f"현재 상태: {status} (기준 {CUTOFF_LABEL})")

    if notice.get("is_corrected"):
        lines.append("변경 사항: 기존 일정은 취소되고 위 정정 일정으로 변경됨")

    return lines


def _build_followups(notice: dict) -> list[str]:
    """
    '확인 필요' 항목(원문에 없지만 독자가 알아야 할 정보)을 구성한다.
    없으면 빈 목록을 반환하여 렌더링 시 해당 줄을 생략하게 한다.

    본 데이터셋의 공지는 신청 방법·접수처·문의처가 모두 원문에 명시되어 있다.
    따라서 '확인 필요' 사항이 없는 공지에서는 이 줄이 생략되어야 한다.
    (명세: 해당 정보가 아예 없으면 그 줄을 삭제한다.)
    """
    followups: list[str] = []
    body = notice.get("body", "")

    # '신청/접수가 필요'하면서(= 별도 신청 없음이 아니면서)
    # 접수처·담당 부서·문의처가 원문에 전혀 명시되지 않은 경우에만 확인 필요로 둔다.
    no_application = ("별도 신청" in body) or ("신청 없이" in body) or ("신청은 없" in body)
    needs_apply = (("신청" in body) or ("접수" in body) or ("모집" in body)) and not no_application
    has_contact = any(
        kw in body
        for kw in ("문의", "사무실", "지원팀", "학생회실", "센터", "접수로", "방문 접수")
    )
    if needs_apply and not has_contact:
        followups.append("신청·문의 담당 부서 및 연락처(원문에 명시되지 않음)")

    return followups


def render_notice(notice: dict, cutoff: datetime = CUTOFF) -> str:
    """
    단일 공지를 지정된 출력 형식의 문자열로 렌더링한다.

    형식:
        [제목]

        - 핵심 안내: ...
        - 관련 일정: ...
        - 출처: mission/data/notices.md의 N0x[, N0y]
        - 확인 필요: ...   (해당 정보가 없으면 이 줄 생략)
    """
    title = _clean(notice.get("title", "")) or "(제목 없음)"

    lines: list[str] = [title, ""]

    # 핵심 안내
    core = _build_core_guidance(notice)
    lines.append(f"- 핵심 안내: {core}")

    # 관련 일정 (여러 줄이면 세미콜론/들여쓰기로 묶음)
    schedule_lines = _build_schedule_lines(notice, cutoff)
    if schedule_lines:
        lines.append(f"- 관련 일정: {schedule_lines[0]}")
        for extra in schedule_lines[1:]:
            lines.append(f"  · {extra}")
    else:
        lines.append("- 관련 일정: 확인 필요(원문에 구체 일정 없음)")

    # 출처 (병합 시 관련 ID 모두 + 행사/업무 ID)
    source_ids = notice.get("source_ids") or [notice.get("id", "")]
    ids_str = ", ".join(source_ids)
    # 행사/업무 ID: 병합 공지는 work_ids, 단일 공지는 work_id. 중복 제거·순서 보존.
    work_ids = notice.get("work_ids") or (
        [notice["work_id"]] if notice.get("work_id") else []
    )
    seen: set[str] = set()
    uniq_work_ids = [w for w in work_ids if not (w in seen or seen.add(w))]
    if uniq_work_ids:
        lines.append(
            f"- 출처: {BRIEFING_SOURCE_LABEL}의 {ids_str} (행사/업무 ID: {', '.join(uniq_work_ids)})"
        )
    else:
        lines.append(f"- 출처: {BRIEFING_SOURCE_LABEL}의 {ids_str}")

    # 확인 필요 (있을 때만)
    followups = _build_followups(notice)
    if followups:
        lines.append(f"- 확인 필요: {'; '.join(followups)}")

    return "\n".join(lines)


def render_briefing(
    notices: list[dict],
    cutoff: datetime = CUTOFF,
    audience: str = "소프트웨어 학부 학생",
) -> str:
    """
    정렬된 공지 목록 전체를 하나의 브리핑 문서(markdown)로 렌더링한다.
    """
    header = [
        f"# {audience}를 위한 공지 브리핑",
        "",
        f"기준 시각: {CUTOFF_LABEL}, {TIMEZONE}",
        "",
    ]
    blocks = [render_notice(n, cutoff) for n in notices]
    body = "\n\n".join(blocks)
    return "\n".join(header) + body + "\n"


def load_notices() -> list[dict]:
    """notices.md 를 파싱하여 dict 목록으로 반환한다."""
    from dataclasses import asdict

    md_text = NOTICES_PATH.read_text(encoding="utf-8")
    return [asdict(n) for n in parse_notices(md_text)]


def main() -> int:
    notices = load_notices()
    kept = filter_open_notices(notices)
    dropped = [n for n in notices if n not in kept]
    merged = merge_corrections(kept)
    ordered = sort_for_reader(merged)

    print(f"기준 시각(cutoff): {CUTOFF_LABEL} ({TIMEZONE})")
    print(f"전체 공지: {len(notices)}건 / 유효(유지): {len(kept)}건 / 마감(제외): {len(dropped)}건")
    print(f"정정 병합 후: {len(merged)}건")
    print("-" * 60)
    print("[유지]")
    for n in kept:
        dl = _resolve_deadline(n)
        dl_s = dl.isoformat() if dl else "마감 없음"
        print(f"  {n['id']} · {n['title']}  (마감: {dl_s})")
    print("[제외 — 이미 마감]")
    for n in dropped:
        dl = _resolve_deadline(n)
        dl_s = dl.isoformat() if dl else "마감 없음"
        print(f"  {n['id']} · {n['title']}  (마감: {dl_s})")
    print("[정정 병합 결과]")
    for n in merged:
        flag = " (정정 병합됨)" if n.get("is_corrected") else ""
        print(f"  {' / '.join(n.get('source_ids', [n['id']]))} · {n['title']}{flag}")
        if n.get("is_corrected"):
            print(f"      변경 반영: {'; '.join(n.get('schedules', []))}")
    print("[독자 우선 정렬 결과 — 소프트웨어 학부 학생]")
    for rank, n in enumerate(ordered, start=1):
        rel = "관련" if n.get("sw_relevant") else "일반"
        rem = _time_remaining_days(n)
        rem_s = "마감 없음" if rem >= _FAR_FUTURE_DAYS else f"D{rem:+.1f}일"
        print(f"  {rank:>2}. [{rel}] {n['id']} · {n['title']}  (남은기간: {rem_s})")

    print("-" * 60)
    print("[브리핑 렌더링 미리보기]")
    print(render_briefing(ordered))

    # 중간 산출물로 저장
    out = {
        "_meta": {
            "source": SOURCE_LABEL,
            "cutoff": CUTOFF_LABEL,
            "timezone": TIMEZONE,
            "total": len(notices),
            "kept": len(kept),
            "dropped": len(dropped),
            "merged": len(merged),
        },
        "kept": kept,
        "dropped": [n["id"] for n in dropped],
        "merged": merged,
        "ordered": ordered,
    }
    (SCRIPT_DIR / "filtered_notices.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
