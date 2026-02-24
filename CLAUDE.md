# 카카오톡 강화 매크로 - CLAUDE.md

## 프로젝트 개요

카카오톡 채팅방 봇에 `/강화` 명령어를 자동 반복 전송하는 macOS 전용 매크로.
목표 레벨 도달 시 자동 종료. OCR로 채팅 결과를 읽어 성공/파괴를 판별한다.

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
| `TARGET_LEVEL` | `10` | 이 레벨 도달 시 매크로 자동 종료 |
| `SUCCESS_TEXT` | `"강화에 성공"` | OCR로 감지할 성공 키워드 (봇 메시지: "강화에 성공하셨습니다") |
| `FAIL_TEXT` | `"강화 파괴"` | OCR로 감지할 파괴 키워드 (봇 메시지: "〖💥강화 파괴💥〗") |
| `COMMAND` | `"/강화"` | 채팅방에 전송할 명령어 |
| `STATS_FILE` | `"enhance_stats.json"` | 통계 저장 파일명 |

## 핵심 구조

### 메인 루프 (`run_macro`)

```
시작 시:
    0. 현재 레벨 수동 입력 (current_level 초기화)
       - 입력값 >= TARGET_LEVEL 이면 경고 출력 후 재입력 요구
while not stop_requested:
    1. 카카오톡 창 위치 확인 (get_window_bounds)
    2. /강화 명령어 전송 (send_command)
    3. 0.3초 대기 후 OCR 폴링 시작 (최대 5초)
    4. 결과 판별 (success / destroy / waiting)
    5. 목표 레벨 도달 시 break
    6. 0.4~0.7초 랜덤 딜레이 후 다음 루프
```

### 명령어 전송 방식 (`send_command`)

**반드시 2단계 Enter가 필요하다.**  
카카오톡 봇 명령어는 입력 시 자동완성 팝업이 뜨고,
팝업에서 명령어를 선택(1번째 Enter)한 뒤 전송(2번째 Enter)해야 한다.

```
AX API로 입력창(UI element 11 → UI element 1)에 value 직접 설정
→ 0.6초 대기 (자동완성 팝업 뜨기까지)
→ key code 36  (Enter 1: 자동완성에서 명령어 선택)
→ 0.3초 대기
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

### OCR 결과 판별 (`check_response`)

`snapshot_texts` (명령어 전송 직전 화면 텍스트)와 현재 OCR 결과를 비교해
새로 추가된 텍스트만 추출한다.

```python
new_texts = [t for t in texts if t not in last_texts]
```

- `new_texts`가 비어있으면 → `'waiting'` (아직 봇 응답 안 옴)
- `"강화에 성공"` 포함 → `'success'`
- `"강화 파괴"` 포함 → `'destroy'`
- `[+N]` 패턴에서 to_lvl = N, from_lvl = N-1 으로 레벨 변화 추출
- `+N → +M` 패턴만 있고 M > N → `'success'`로 간주

**핵심: `snapshot_texts`는 전송 시점에 고정하고, 폴링 루프 안에서 갱신하지 않는다.**  
(갱신하면 봇 응답이 와도 항상 `waiting`으로 처리되어 목표 레벨 도달 감지 불가)

```python
snapshot_texts = last_texts.copy()   # 전송 직전 고정
while result == 'waiting' and ...:
    screenshot = capture_chat_area(bounds)
    texts = read_chat_text(screenshot)
    result, from_lvl, to_lvl = check_response(texts, snapshot_texts)  # snapshot 기준
last_texts = texts.copy()            # 폴링 끝난 후에만 갱신
```

### 레벨 변화 파싱 (`parse_level_change`)

OCR 텍스트에서 아래 패턴을 감지:
- `+N → +M`
- `+N -> +M`
- `+N ▶ +M`

## 통계 (`EnhanceStats`)

- `enhance_stats.json`에 자동 저장
- 레벨별 성공/파괴 횟수 기록
- `simulate_to_20()`: 현재 성공률 기반으로 +20 도달 확률 몬테카를로 시뮬레이션 (10,000회)
- 메뉴 `2` 또는 `stats`로 조회, `3` 또는 `reset`으로 초기화

## 의존성

```
pyautogui     # 화면 캡처
pyperclip     # (현재 미사용, 레거시 잔존)
easyocr       # OCR (한국어/영어)
numpy         # OCR 이미지 배열 변환
```

설치:
```bash
pip install -r requirements.txt
```

## macOS 권한

| 권한 | 필요 여부 | 용도 |
|------|-----------|------|
| 손쉬운 사용 (Accessibility) | **불필요** | AX API value 방식으로 우회 |
| 화면 기록 (Screen Recording) | **필요** | `pyautogui.screenshot()` 으로 OCR 캡처 |

화면 기록 권한 설정:  
`시스템 설정 (Ventura+) / 시스템 환경설정 (Monterey-)` → `개인정보 보호 및 보안` → `화면 기록` → 터미널(또는 iTerm2) 추가 → **터미널 재시작 필수**

## 알려진 이슈 및 트러블슈팅

### OCR이 성공/파괴를 인식 못할 때
- `[DEBUG] OCR 인식:` 로그로 실제 읽힌 텍스트 확인
- `capture_chat_area()` 내 캡처 영역 오프셋(`top`, `height`) 조정
- 채팅창 크기를 키우면 OCR 정확도 향상

### 자동완성 팝업 타이밍이 안 맞을 때
- `send_command()` 내 첫 번째 `delay 0.6` 값을 늘린다 (0.8 ~ 1.0)
- 네트워크 지연이 있는 환경에서는 더 길게 설정 필요

### UI element 11이 입력창이 아닐 때
- 위 재탐색 AppleScript로 올바른 인덱스 확인 후 코드 수정

### 목표 레벨 도달해도 안 멈출 때
- `[DEBUG]` 로그에서 `result`, `from`, `to` 값 확인
- OCR이 레벨 변화 텍스트를 못 읽으면 `'waiting'` 상태로 계속 루프
- `SUCCESS_TEXT` 키워드가 실제 봇 메시지와 일치하는지 확인
