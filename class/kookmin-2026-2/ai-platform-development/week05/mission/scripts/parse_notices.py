#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_notices.py

mission/data/notices.md 파일을 읽어 각 공지를 구조화하여 파싱한다.

각 공지는 다음 필드를 가진다:
    - id                : 공지 ID (예: N01)
    - title             : 공지 제목
    - posted            : 게시 시각 (datetime)
    - department        : 게시 부서
    - work_id           : 업무/행사 ID (예: LIB-01, TALK-03)
    - body              : 본문 텍스트
    - schedules         : 본문에서 추출한 일정/일시 목록
    - deadline          : 신청/접수 마감일 (datetime 또는 None)
    - deadline_raw      : 마감 원문 표기 (시각 미기재 등 모호성 추적용)
    - is_correction     : 정정 공지 여부
    - correction_target : 정정 대상 공지 ID (정정 공지인 경우)
    - sw_relevant       : 소프트웨어 학부 학생 관련성 플래그
    - sw_relevant_reason: 관련성 판단 근거

결과를 표준출력(JSON) 및 scripts/parsed_notices.json 으로 출력한다.

주의: 과제 설명에는 경로가 mission/mission/data/notices.md 로 되어 있으나
실제 파일은 week05/mission/data/notices.md (단일 mission) 에 존재한다.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 경로 상수
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
MISSION_ROOT = SCRIPT_DIR.parent                      # .../week05/mission
NOTICES_PATH = MISSION_ROOT / "data" / "notices.md"   # 실제 파일 경로
OUTPUT_PATH = SCRIPT_DIR / "parsed_notices.json"
SOURCE_LABEL = "mission/data/notices.md"              # 출처 표기용 상대경로

# 소프트웨어 학부 관련성 판단에 사용할 키워드
SW_KEYWORDS = (
    "소프트웨어학부",
    "소프트웨어 학부",
    "ai",
    "포트폴리오",
    "프로젝트",
    "전시",
    "코드",
    "개발",
)

# 날짜/시각 패턴
DT_FULL_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})")   # YYYY-MM-DD HH:MM
DATE_ONLY_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")                      # YYYY-MM-DD

# 마감을 나타내는 문맥 키워드
DEADLINE_HINT_RE = re.compile(r"(까지)")
APPLY_HINT_RE = re.compile(r"(신청|접수|제출|모집\s*마감|마감)")


@dataclass
class Notice:
    id: str
    title: str
    posted: Optional[str] = None            # ISO 문자열 (JSON 직렬화용)
    department: Optional[str] = None
    work_id: Optional[str] = None
    body: str = ""
    schedules: list = field(default_factory=list)
    deadline: Optional[str] = None          # ISO 문자열 또는 None
    deadline_raw: Optional[str] = None
    is_correction: bool = False
    correction_target: Optional[str] = None
    sw_relevant: bool = False
    sw_relevant_reason: str = ""


def _parse_dt(text: str) -> Optional[datetime]:
    """텍스트에서 첫 번째 'YYYY-MM-DD HH:MM' 또는 'YYYY-MM-DD' 를 datetime 으로 파싱."""
    m = DT_FULL_RE.search(text)
    if m:
        y, mo, d, h, mi = (int(g) for g in m.groups())
        return datetime(y, mo, d, h, mi)
    m = DATE_ONLY_RE.search(text)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        return datetime(y, mo, d)
    return None


def _split_notices(md_text: str) -> list[tuple[str, str, str]]:
    """
    마크다운에서 '## N01 · 제목' 형태의 섹션별로 분할한다.
    반환: [(id, title, section_body), ...]
    """
    # 공지 헤더: '## N01 · 제목'
    header_re = re.compile(r"^##\s+(N\d+)\s*·\s*(.+?)\s*$", re.MULTILINE)
    matches = list(header_re.finditer(md_text))
    sections: list[tuple[str, str, str]] = []
    for i, m in enumerate(matches):
        nid = m.group(1).strip()
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        body = md_text[start:end].strip()
        sections.append((nid, title, body))
    return sections


def _extract_meta_line(body: str, label: str) -> Optional[str]:
    """'- 게시: 2026-09-07 10:00' 같은 메타 라인에서 label 뒤 값을 추출."""
    pat = re.compile(rf"^-\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.MULTILINE)
    m = pat.search(body)
    return m.group(1).strip() if m else None


def _detect_deadline(prose: str) -> tuple[Optional[datetime], Optional[str]]:
    """
    본문 산문에서 신청/접수 마감 일시를 탐지한다.
    '...까지' 와 신청/접수/제출/마감 키워드가 함께 등장하는 문장을 우선 사용.
    반환: (deadline datetime 또는 None, 원문 표기 문자열 또는 None)
    """
    # 문장 단위로 분해
    sentences = re.split(r"(?<=[.。])\s+|\n", prose)
    best_dt: Optional[datetime] = None
    best_raw: Optional[str] = None
    for s in sentences:
        if DEADLINE_HINT_RE.search(s) and APPLY_HINT_RE.search(s):
            dt = _parse_dt(s)
            # '까지' 바로 앞 날짜 토막을 raw 로 보존
            m = re.search(r"(\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?)\s*까지", s)
            raw = m.group(1) if m else (DT_FULL_RE.search(s) or DATE_ONLY_RE.search(s))
            if m:
                best_raw = m.group(1)
            if dt is not None:
                best_dt = dt
                if m:
                    best_raw = m.group(1)
                return best_dt, best_raw
            if best_raw is None and raw and not isinstance(raw, re.Match):
                best_raw = raw
    return best_dt, best_raw


def _extract_schedules(prose: str) -> list[str]:
    """본문에서 날짜/일시가 포함된 핵심 문장을 일정 목록으로 추출."""
    schedules: list[str] = []
    sentences = re.split(r"(?<=[.。])\s+|\n", prose)
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if DT_FULL_RE.search(s) or DATE_ONLY_RE.search(s):
            # 메타 라인(게시/부서/ID)은 제외
            if s.startswith("-") and ("게시" in s or "부서" in s or "ID" in s):
                continue
            schedules.append(s)
    return schedules


def _detect_correction(body: str) -> tuple[bool, Optional[str]]:
    """정정 공지 여부와 정정 대상 ID를 탐지."""
    target = _extract_meta_line(body, "정정 대상")
    if target:
        m = re.search(r"(N\d+)", target)
        return True, (m.group(1) if m else target)
    # 제목/본문에 '정정' 포함 시 백업 탐지
    if "정정" in body:
        m = re.search(r"N\d+에\s*기재", body) or re.search(r"(N\d+)", body)
        if m:
            return True, re.search(r"(N\d+)", m.group(0)).group(1)
    return False, None


def _detect_sw_relevance(title: str, body: str) -> tuple[bool, str]:
    """소프트웨어 학부 학생 관련성 판단."""
    text = (title + " " + body).lower()
    hits = [kw for kw in SW_KEYWORDS if kw.lower() in text]
    if "소프트웨어학부" in body or "소프트웨어 학부" in body:
        return True, "소프트웨어학부 주관/직접 언급"
    if hits:
        return True, f"관련 키워드 포함: {', '.join(sorted(set(hits)))}"
    return False, "소프트웨어 학부 특정 관련성 낮음(전교생 대상 일반 공지)"


def parse_notices(md_text: str) -> list[Notice]:
    results: list[Notice] = []
    for nid, title, body in _split_notices(md_text):
        posted_raw = _extract_meta_line(body, "게시")
        department = _extract_meta_line(body, "게시 부서")
        work_id = (
            _extract_meta_line(body, "업무 ID")
            or _extract_meta_line(body, "행사 ID")
        )

        posted_dt = _parse_dt(posted_raw) if posted_raw else None

        # 메타 라인을 제거한 산문 본문
        prose_lines = [
            ln for ln in body.splitlines()
            if not re.match(r"^-\s*(게시|게시 부서|업무 ID|행사 ID|정정 대상)\s*:", ln.strip())
        ]
        prose = "\n".join(prose_lines).strip()

        deadline_dt, deadline_raw = _detect_deadline(prose)
        schedules = _extract_schedules(prose)
        is_corr, corr_target = _detect_correction(body)
        sw_rel, sw_reason = _detect_sw_relevance(title, body)

        results.append(
            Notice(
                id=nid,
                title=title,
                posted=posted_dt.isoformat() if posted_dt else posted_raw,
                department=department,
                work_id=work_id,
                body=prose,
                schedules=schedules,
                deadline=deadline_dt.isoformat() if deadline_dt else None,
                deadline_raw=deadline_raw,
                is_correction=is_corr,
                correction_target=corr_target,
                sw_relevant=sw_rel,
                sw_relevant_reason=sw_reason,
            )
        )
    return results


def main(argv: list[str]) -> int:
    if not NOTICES_PATH.exists():
        print(f"ERROR: 공지 파일을 찾을 수 없습니다: {NOTICES_PATH}", file=sys.stderr)
        return 1

    md_text = NOTICES_PATH.read_text(encoding="utf-8")
    notices = parse_notices(md_text)

    payload = {
        "_meta": {
            "source": SOURCE_LABEL,
            "actual_path": str(NOTICES_PATH),
            "parsed_count": len(notices),
            "cutoff": "2026-09-14 09:00",
            "timezone": "Asia/Seoul",
        },
        "notices": [asdict(n) for n in notices],
    }

    out_json = json.dumps(payload, ensure_ascii=False, indent=2)

    # 중간 산출물로 저장
    OUTPUT_PATH.write_text(out_json, encoding="utf-8")

    # 표준출력에도 출력
    print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
