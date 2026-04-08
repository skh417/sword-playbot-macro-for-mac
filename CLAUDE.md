# 카카오톡 강화 매크로 - CLAUDE.md

## 프로젝트 개요

카카오톡 채팅방 봇에 `/강화` 명령어를 자동 반복 전송하는 macOS 전용 매크로.
목표 레벨 도달 시 자동 종료. pyobjc AX API로 채팅 텍스트를 직접 읽어 성공/파괴/유지를 판별한다.
AX API 실패 시 OCR(easyocr) fallback으로 자동 전환.
사용자 입력은 `escape_applescript()`로 AppleScript 인젝션을 방지한다.

## 파일 구조

```
kakao_macro/
├── enhance_macro.py     # 메인 스크립트 (전체 로직)
├── enhance_stats.json   # 통계 데이터 (자동 생성)
├── requirements.txt     # 의존성
├── README.md
└── CLAUDE.md
```

## 실행

```bash
python3 enhance_macro.py
```

실행 시 채팅방 이름 입력 → 메뉴에서 `1` 또는 `start` 입력 → **현재 레벨 수동 입력** → 매크로 시작.
종료: `Ctrl+C`

## 주요 설정값 (enhance_macro.py 상단)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TARGET_LEVEL` | `15` | 이 레벨 도달 시 매크로 자동 종료 |
| `GOLD_LIMIT` | `0` | 남은 골드가 이 값 미만이 되면 종료 (0 = 기능 비활성화) |
| `SUCCESS_TEXT` | `"강화에 성공"` | OCR로 감지할 성공 키워드 |
| `FAIL_TEXT` | `"강화 파괴"` | OCR로 감지할 파괴 키워드 |
| `KEEP_TEXT` | `"의 레벨이 유지되었습니다"` | OCR로 감지할 레벨 유지 키워드 |
| `COMMAND` | `"/강화"` | 채팅방에 전송할 명령어 |
| `STATS_FILE` | `"enhance_stats.json"` | 통계 저장 파일명 |
| `MAX_LEVEL` | `20` | 강화 최대 레벨 (OCR 오인식 필터용, 이 값 초과 레벨은 무시) |

## 핵심 구조

### 메인 루프 (`run_macro`)

```
시작 시:
    0. 현재 레벨 수동 입력 (current_level 초기화)
       - 입력값 >= TARGET_LEVEL 이면 경고 출력 후 재입력 요구
while not stop_requested:
    1. 카카오톡 창 위치 확인 (get_window_bounds)
    2. _read_texts()로 현재 레벨 동기화 (scan_current_level)
       - AX API 모드: read_chat_text_ax() (마지막 5행, ~44ms)
       - OCR 모드: capture_chat_area() + read_chat_text() (fallback)
       - just_destroyed 플래그가 True면 이 단계 스킵 (파괴 직후 오인식 방지)
       - 스캔 결과가 현재 레벨과 다르면 동기화 (단, 현재 레벨보다 낮으면 오독으로 무시)
    3. 목표 레벨 도달 확인 (전송 전 체크) → 도달 시 break
    4. /강화 명령어 전송 (send_command)
    5. 0.05초 대기 후 폴링 시작 (0.1초 간격, 최대 5초)
    6. 결과 판별 (success / destroy / keep / waiting / unknown)
    7. 봇 응답에서 남은 골드 파싱 → GOLD_LIMIT 미만이면 break
    8. 결과별 처리:
       - success: 레벨 증가, 목표 달성 시 break
       - destroy: 레벨 0으로 리셋, just_destroyed = True
       - keep: 레벨 유지 (로그만 출력)
       - waiting: 타임아웃 시 전체 텍스트에서 파괴/동기화 감지
    9. 0.05초 대기 후 다음 루프
```

### 명령어 전송 방식 (`send_command`)

**반드시 2단계 Enter가 필요하다.**  
카카오톡 봇 명령어는 입력 시 자동완성 팝업이 뜨고,
팝업에서 명령어를 선택(1번째 Enter)한 뒤 전송(2번째 Enter)해야 한다.

```
AXRaise로 창 활성화
→ 0.05초 대기
→ AX API로 입력창(UI element 11 → UI element 1)에 value 직접 설정
→ focused 설정
→ 0.25초 대기 (자동완성 팝업 뜨기까지)
→ key code 36  (Enter 1: 자동완성에서 명령어 선택)
→ 0.1초 대기
→ key code 36  (Enter 2: 전송)
```

**왜 이 방식인가:**
- `keystroke` + `Cmd+V` 방식: macOS 손쉬운 사용(Accessibility) 권한 필요 → 권한 없으면 무반응
- `AXConfirm` 액션: 카카오톡이 미지원
- `set value of tf` + `key code 36`: **권한 불필요**, 정상 동작 확인

**카카오톡 채팅창 UI 구조:**
```
window (채팅방명)
├── UI element 1  ~ 10  : 버튼들 (프로필, 검색, 보이스톡 등)
├── UI element 11 : AXScrollArea (채팅 메시지 영역 또는 입력창 스크롤)
│   └── UI element 1 : AXTextArea  ← 입력창 (여기에 value 설정)
├── UI element 12 : 추가기능 버튼
├── UI element 13 : 이모티콘 버튼
├── UI element 14 : 파일전송 버튼
└── UI element 15 : 전송 버튼 (title/help 없음)
```

> **주의:** UI element 인덱스(11번)는 카카오톡 버전/창 상태에 따라 바뀔 수 있다.
> 바뀐 경우 아래 AppleScript로 재탐색:
> ```applescript
> tell application "System Events"
>     tell process "KakaoTalk"
>         set wins to every window
>         repeat with w in wins
>             if name of w contains "채팅방이름" then
>                 set lvl1 to UI elements of w
>                 set idx to 0
>                 repeat with e in lvl1
>                     set idx to idx + 1
>                     try
>                         set lvl2 to UI elements of e
>                         repeat with e2 in lvl2
>                             if role of e2 is "AXTextArea" then
>                                 return "발견 idx=" & idx
>                             end if
>                         end repeat
>                     end try
>                 end repeat
>             end if
>         end repeat
>     end tell
> end tell
> ```

### 채팅 텍스트 읽기 (`_read_texts` / `read_chat_text_ax`)

두 가지 모드를 자동 전환하는 `_read_texts()` 헬퍼를 통해 채팅 텍스트를 읽는다.

**AX API 모드 (기본, 권장):**
- pyobjc의 `ApplicationServices`로 카카오톡 UI 요소에 직접 접근
- `AXScrollArea → AXTable → AXRow → AXCell` 구조에서 텍스트 추출
- 마지막 5행만 읽어 ~44ms 소요 (OCR 대비 7~20배 빠름)
- 100% 정확도 (OCR 오인식 없음)
- 창이 가려져 있어도 읽기 가능 (최소화 제외)
- PID/앱 요소는 `_ax_app`, `_ax_pid`로 캐싱하여 재생성 방지

**OCR 모드 (fallback):**
- `pyautogui.screenshot()` + `easyocr.readtext()`
- AX API 실패 시 자동 전환 (`use_ax_api = False`)
- 화면 기록 권한 필요, 화면 점유 필수

### 결과 판별 (`check_response`)

`snapshot_texts` (명령어 전송 직전 텍스트)와 현재 텍스트를 비교해
새로 추가된 텍스트만 추출한다.

```python
new_texts = [t for t in texts if t not in last_texts]
```

- `new_texts`가 비어있으면 → `'waiting'` (아직 봇 응답 안 옴)
- `"강화에 성공"` 포함 → `'success'`
- `"강화 파괴"` 포함 → `'destroy'`
- `"의 레벨이 유지되었습니다"` 포함 → `'keep'`
- `"강화 성공"` 또는 `"속보"` 키워드 → `'success'` (OCR이 정확한 키워드를 못 읽을 때 대체)
- `[+0]` 패턴 → `'destroy'` (FAIL_TEXT 없이도 파괴 감지)
- `[+N]` 패턴에서 to_lvl = N, from_lvl = N-1 으로 레벨 변화 추출
- `+N → +M` 패턴만 있고 M > N → `'success'`로 간주
- new_texts에서 레벨 파싱 실패 시 전체 texts에서 재시도
- 위 어느 것에도 해당하지 않으면 → `'unknown'`

**핵심: `snapshot_texts`는 전송 시점에 고정하고, 폴링 루프 안에서 갱신하지 않는다.**  
(갱신하면 봇 응답이 와도 항상 `waiting`으로 처리되어 목표 레벨 도달 감지 불가)

```python
snapshot_texts = last_texts.copy()   # 전송 직전 고정
while result in ('waiting', 'unknown') and ...:   # unknown도 폴링 계속
    texts = _read_texts()            # AX API 또는 OCR 자동 선택
    result, from_lvl, to_lvl = check_response(texts, snapshot_texts, current_level)
last_texts = texts.copy()            # 폴링 끝난 후에만 갱신
```

### 레벨 변화 파싱 (`parse_level_change`)

OCR 텍스트에서 아래 패턴을 감지:
- `+N → +M`
- `+N -> +M`
- `+N ▶ +M`

**검증 로직:**
- `MAX_LEVEL` 초과 값은 OCR 오인식으로 간주하여 무시
- `to_lvl != from_lvl + 1`이면 1단위 증가가 아니므로 무시
- 화살표 패턴 실패 시 `"강화에 성공"` + `[+N]` 패턴으로 fallback (to_lvl = N, from_lvl = N-1)

### 전송 전 레벨 동기화 (`scan_current_level`)

매 루프 전송 전에 `_read_texts()`로 현재 레벨을 확인하여 `current_level`과 동기화한다.

- 화살표 패턴(`+N → +M`)에서 마지막 to 값을 추출
- 없으면 `[+N]` 패턴에서 최대값 추출
- `current_level` 대비 ±3 범위 밖 값은 오인식으로 무시
- 파괴 직후(`just_destroyed = True`)에는 이 스캔을 스킵 (이전 메시지의 레벨이 남아있어 오독 가능)

### 남은 골드 파싱 (`parse_remaining_gold`)

OCR 텍스트에서 `남은 골드: NNN,NNNG` 패턴을 찾아 정수로 반환한다.
`남은골드:`, `남은 골드：` 등 공백/구두점 변형에 대응한다.

## 통계 (`EnhanceStats`)

- `enhance_stats.json`에 자동 저장
- 레벨별 성공/파괴 횟수 기록
- `simulate_to_20()`: 현재 성공률 기반으로 +20 도달 확률 몬테카를로 시뮬레이션 (10,000회)

### 메뉴 구성

| 번호 | 명령어 | 설명 |
|------|--------|------|
| 1 | `start` | 매크로 시작 |
| 2 | `stats` | 통계 보기 |
| 3 | `reset` | 통계 초기화 |
| 4 | `room` | 채팅방 변경 |
| 5 | `goal` | 목표 레벨 변경 |
| 6 | `gold` | 골드 리밋 변경 |
| 7 | `quit` | 종료 |

## 의존성

### 필수 (AX API 모드)

```
pyobjc-framework-ApplicationServices   # macOS AX API로 채팅 텍스트 직접 읽기
```

### 선택 (OCR fallback 모드)

```
pyautogui     # 화면 캡처
pillow        # pyautogui 스크린샷 의존 (간접 의존)
easyocr       # OCR (한국어/영어)
numpy         # OCR 이미지 배열 변환
```

설치:
```bash
# AX API 모드 (권장, 가볍고 빠름)
pip install pyobjc-framework-ApplicationServices

# OCR fallback도 함께 설치 (선택)
pip install -r requirements.txt
```

## macOS 권한

| 권한 | AX API 모드 | OCR 모드 | 용도 |
|------|:-----------:|:--------:|------|
| 손쉬운 사용 (Accessibility) | **불필요** | **불필요** | AX API value 방식으로 우회 |
| 화면 기록 (Screen Recording) | **불필요** | **필요** | `pyautogui.screenshot()`으로 OCR 캡처 |

AX API 모드에서는 macOS 권한이 **전혀 필요 없다.**
OCR fallback으로 전환된 경우에만 화면 기록 권한이 필요하다.

화면 기록 권한 설정 (OCR 모드에서만 필요):  
`시스템 설정 (Ventura+) / 시스템 환경설정 (Monterey-)` → `개인정보 보호 및 보안` → `화면 기록` → 터미널(또는 iTerm2) 추가 → **터미널 재시작 필수**

## 알려진 이슈 및 트러블슈팅

### OCR이 성공/파괴를 인식 못할 때
- `[DEBUG] OCR 인식:` 로그로 실제 읽힌 텍스트 확인
- `capture_chat_area()` 내 캡처 영역 오프셋(`top`, `height`) 조정
- 채팅창 크기를 키우면 OCR 정확도 향상

### 자동완성 팝업 타이밍이 안 맞을 때
- `send_command()` 내 첫 번째 `delay 0.25` 값을 늘린다 (0.4 ~ 0.6)
- 네트워크 지연이 있는 환경에서는 더 길게 설정 필요

### UI element 11이 입력창이 아닐 때
- 위 재탐색 AppleScript로 올바른 인덱스 확인 후 코드 수정

### 목표 레벨 도달해도 안 멈출 때
- `[DEBUG]` 로그에서 `result`, `from`, `to` 값 확인
- OCR이 레벨 변화 텍스트를 못 읽으면 `'waiting'` 상태로 계속 루프
- `SUCCESS_TEXT` 키워드가 실제 봇 메시지와 일치하는지 확인
- 타임아웃 후 전체 화면 OCR 스캔으로도 레벨 동기화 시도하므로, 보통은 자동 감지됨

### 보안 (`escape_applescript`)

채팅방 이름 등 사용자 입력이 AppleScript에 삽입될 때 `escape_applescript()`로
백슬래시(`\`)와 쌍따옴표(`"`)를 이스케이프하여 인젝션을 방지한다.
`find_kakao_window`, `activate_kakao_window`, `get_window_bounds`, `send_command` 4곳에서 사용.
