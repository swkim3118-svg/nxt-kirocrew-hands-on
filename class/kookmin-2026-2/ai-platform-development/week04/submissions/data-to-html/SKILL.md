---
name: data-to-html
description: 여러 개의 md·csv 파일을 읽고 정해진 형식의 HTML로 정리·요약한다.
triggers: 문서 요약, 파일 정리, md csv 정리, 자료 취합, 문서 취합, html 요약
---

# 문서 취합 요약

지정한 폴더(또는 파일 목록)의 `.md`와 `.csv`를 읽어, **매번 같은 형식**으로 정리·요약한다.

역할을 나눈다. **숫자·구조는 코드가, 문장 요약은 AI가** 맡는다.

- **Python 스크립트**가 파일을 수집·파싱해 기계적 사실(파일 목록, csv 행·열·수치 합계, md 제목·섹션)을 JSON으로 뽑는다.
- **AI**는 그 JSON을 읽고 아래 출력 형식에 맞춰 문장으로 요약한다. 파일 원문 판독은 필요할 때만 보조로 쓴다.

읽기 어렵거나 의미가 애매한 부분은 추측하지 말고 "확인 필요"에 남긴다.

## 출력 형식 (고정)

결과는 **하나의 HTML 파일**로 낸다. 문서마다 다르지 않게, 아래 네 섹션을 항상 같은 순서로 담는다.

1. **개요** — 대상 폴더, 전체 파일 수(md N개 / csv M개), 한두 문장 총평
2. **문서 요약** — 파일마다 한 줄: 무엇에 대한 파일인지 + 핵심 내용. 표는 파일명·요약 두 열만 담는다. (AI가 문장으로 채운다.)
3. **핵심 표** — csv에서 집계된 합계·평균·개수를 표로. 수치가 없으면 "해당 없음".
4. **확인 필요** — 비어 있거나 깨진 파일, 파싱 실패, 의미가 애매해 사람이 봐야 하는 항목. 없으면 "없음".

저장 위치(기본): `week04\mission\submissions\` 아래에 `data-to-html_YYYY-MM-DD.html`.
폴더가 없으면 스크립트가 만든다. 다른 곳에 저장하려면 `--out`으로 경로를 준다.

## 실행 절차

1. **Python 스크립트가 수집·파싱**한다. 폴더를 훑어 `.md`/`.csv`를 찾고 사실 JSON을 만든다.

   ```bash
   cd scripts

   # 폴더 하나를 통째로 훑기 (하위 폴더 포함)
   python collect_docs.py --dir "<대상 폴더>" --out facts.json

   # 특정 파일만 지정
   python collect_docs.py --files a.md b.csv c.md --out facts.json

   # 하위 폴더 제외
   python collect_docs.py --dir "<대상 폴더>" --no-recursive --out facts.json
   ```

2. **AI가 `facts.json`을 읽고** 개요 총평과 문서 요약 문장을 작성해 `summaries.json`으로 저장한다.
   `{"overview": "총평 문장", "files": {"상대경로": "그 파일 한 줄 요약", ...}}`
   - csv의 수치 합계·평균은 스크립트가 계산한 값을 그대로 쓴다. AI가 다시 암산하지 않는다.
   - 파싱에 실패했거나 내용이 비어 있다고 표시된 파일은 반드시 "확인 필요"에 옮긴다.

3. **Python 스크립트가 HTML을 렌더링·저장**한다. facts + AI 요약을 합쳐 표와 섹션을 만든다.

   ```bash
   # week04\mission\submissions 아래에 자동 저장 (파일명 data-to-html_YYYY-MM-DD.html)
   python render_html.py --facts facts.json --summaries summaries.json --title "주간 자료 요약" --submissions "<...>\week04\mission\submissions"

   # summaries 없이 구조·표만 렌더링 (요약 자리는 "(요약 미작성)"으로 남음)
   python render_html.py --facts facts.json --submissions "<...>\week04\mission\submissions"

   # 저장 경로/파일명 직접 지정
   python render_html.py --facts facts.json --out "<경로>\result.html"
   ```

   - 핵심 표·파일 목록·확인 필요 섹션은 스크립트가 facts.json에서 그대로 그린다.
   - `--summaries`를 주면 개요 총평과 문서 요약 한 줄이 채워진다.

## 스크립트가 뽑는 사실 (facts.json 구조)

```json
{
  "dir": "대상 경로 또는 null",
  "counts": { "md": 3, "csv": 2, "skipped": 0 },
  "files": [
    {
      "path": "상대경로",
      "type": "md",
      "title": "첫 번째 # 제목 또는 파일명",
      "headings": ["섹션 제목", "..."],
      "word_count": 123,
      "preview": "본문 앞부분 일부",
      "error": null
    },
    {
      "path": "상대경로",
      "type": "csv",
      "rows": 42,
      "columns": ["이름", "수량", "..."],
      "numeric_summary": { "수량": { "sum": 100, "mean": 2.38, "count": 42 } },
      "preview_rows": [["..."], ["..."]],
      "error": null
    }
  ],
  "needs_review": ["빈 파일이거나 파싱 실패한 파일 경로 + 사유"]
}
```

- csv 인코딩은 UTF-8 → CP949(euc-kr) 순으로 시도한다(한글 파일 대비).
- 파일을 못 읽으면 그 파일의 `error`에 사유를 담고 `needs_review`에도 추가한다. 전체 실행을 멈추지 않는다.
- 숫자 컬럼만 `numeric_summary`에 합계·평균·개수를 넣는다.

> Python 실행 파일 이름은 환경마다 다르다(`python` / `py` / `python3`).
> 이 컴퓨터에서는 KiroCrew 번들 인터프리터
> `%LOCALAPPDATA%\Programs\KiroCrew\resources\backend-dist\kirocrew-backend\python.exe`
> (Python 3.12)로 실행을 확인했다.
> 한글 경로가 깨지면 `PYTHONUTF8=1`을 켜고 실행한다.
