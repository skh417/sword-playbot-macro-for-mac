# 카카오톡 강화 매크로

카카오톡 채팅방 봇에 `/강화` 명령어를 자동 반복 전송하는 macOS 전용 매크로.
목표 레벨 도달 시 자동 종료. AX API로 채팅 텍스트를 직접 읽어 성공/파괴/유지를 판별한다.

## 요구사항

- **macOS** (Windows/Linux 미지원)
- **Python 3.8+**
- **카카오톡 macOS 앱** (실행 상태)

## 설치

### 1. 저장소 클론

```bash
git clone https://github.com/skh417/sword-playbot-macro-for-mac.git
cd sword-playbot-macro-for-mac
```

### 2. 의존성 설치

```bash
# 방법 A: AX API만 설치 (권장, 가볍고 빠름)
pip install pyobjc-framework-ApplicationServices

# 방법 B: 전체 설치 (OCR fallback 포함)
pip install -r requirements.txt
```

| 모드 | 설치 패키지 | 속도 | 정확도 | 권한 | 백그라운드 |
|------|-----------|:----:|:-----:|:----:|:---------:|
| **AX API** (기본) | `pyobjc-framework-ApplicationServices` | ~44ms | 100% | 불필요 | 읽기 가능 |
| OCR (fallback) | `pyautogui`, `easyocr`, `numpy`, `pillow` | 300~1000ms | 가변 | 화면 기록 | 불가 |

> AX API 모드는 pyobjc만 설치하면 되며, macOS 권한 설정이 **전혀 필요 없습니다.**
> OCR 라이브러리가 없어도 매크로가 정상 동작합니다.

## 실행

```bash
python3 enhance_macro.py
```

실행 후 흐름:
1. 카카오톡에서 채팅방 열기
2. 터미널에 채팅방 이름 입력
3. 메뉴에서 `5. goal`로 목표 레벨 확인/변경
4. `1. start` 입력
5. **현재 레벨 입력** (예: 지금 +7이면 `7` 입력)
6. 매크로 자동 진행 → 목표 레벨 도달 시 자동 종료
7. 수동 종료: `Ctrl+C`

> **현재 레벨 입력이 필요한 이유**: 입력하지 않으면 항상 0에서 시작하는 것으로 간주되어
> 이미 목표 레벨 이상인 경우에도 강화를 계속 전송합니다.

## 메뉴

| 입력 | 기능 |
|------|------|
| `1` / `start` | 매크로 시작 |
| `2` / `stats` | 통계 보기 |
| `3` / `reset` | 통계 초기화 |
| `4` / `room` | 채팅방 변경 |
| `5` / `goal` | 목표 레벨 변경 |
| `6` / `gold` | 골드 리밋 변경 |
| `7` / `quit` | 종료 |

## 주요 설정값

`enhance_macro.py` 상단에서 변경:

```python
TARGET_LEVEL = 15          # 이 레벨 도달 시 자동 종료
GOLD_LIMIT   = 0           # 이 골드 미만이 되면 종료 (0 = 기능 비활성화)
SUCCESS_TEXT = "강화에 성공"  # 봇 성공 메시지 키워드
FAIL_TEXT    = "강화 파괴"   # 봇 파괴 메시지 키워드
KEEP_TEXT    = "의 레벨이 유지되었습니다"  # 봇 유지 메시지 키워드
COMMAND      = "/강화"       # 채팅방에 전송할 명령어
MAX_LEVEL    = 20          # 강화 최대 레벨 (오인식 필터)
```

## macOS 권한 설정

| 권한 | AX API 모드 | OCR 모드 | 용도 |
|------|:-----------:|:--------:|------|
| 손쉬운 사용 (Accessibility) | **불필요** | **불필요** | AX API value 방식으로 우회 |
| 화면 기록 (Screen Recording) | **불필요** | **필요** | `pyautogui.screenshot()`으로 OCR 캡처 |

> **AX API 모드에서는 macOS 권한 설정이 전혀 필요 없습니다.**

### 화면 기록 권한 (OCR fallback 사용 시에만)

<details>
<summary>화면 기록 권한 추가 방법 (클릭하여 펼치기)</summary>

**macOS Ventura 이상 (13.0+)**

1. 애플 메뉴 → **시스템 설정** 클릭
2. 왼쪽 사이드바에서 **개인정보 보호 및 보안** 클릭
3. 오른쪽에서 스크롤 → **화면 기록 및 시스템 오디오** 클릭
4. 목록에서 **터미널** (또는 사용 중인 터미널 앱) 찾아 토글 **켜기**
   - 목록에 없으면 좌하단 `+` 버튼 → `/Applications/Utilities/Terminal.app` 선택
5. 터미널을 **완전히 종료 후 재시작**

**macOS Monterey 이하 (12.0 이하)**

1. 애플 메뉴 → **시스템 환경설정** 클릭
2. **보안 및 개인 정보 보호** → **개인 정보 보호** 탭 → **화면 기록**
3. 좌하단 자물쇠 아이콘 클릭 → 비밀번호 입력
4. **터미널** 체크박스 체크 → 터미널 **재시작**

| 터미널 앱 | 권한 부여 대상 |
|-----------|----------------|
| 기본 터미널 | Terminal.app |
| iTerm2 | iTerm.app |
| VS Code 터미널 | Visual Studio Code.app |
| PyCharm 터미널 | PyCharm.app |

</details>

## 파일 구조

```
kakao_macro/
├── enhance_macro.py       # 메인 스크립트
├── enhance_stats.json     # 통계 데이터 (자동 생성)
├── requirements.txt       # 의존성
├── README.md
└── CLAUDE.md              # 개발 문서
```

## 통계

매크로 실행 중 자동으로 `enhance_stats.json`에 기록된다.

- 레벨별 성공/파괴 횟수
- 전체 시도 횟수 및 최고 도달 레벨
- `+20` 도달 확률 몬테카를로 시뮬레이션 (10,000회)

## 트러블슈팅

**`[AX API 실패] OCR fallback으로 전환` 이 뜰 때**
- 카카오톡이 실행 중인지 확인
- 채팅방 창이 열려 있는지 확인 (최소화하면 AX API가 읽기 실패할 수 있음)
- OCR 라이브러리가 설치되지 않았으면 fallback도 불가 → `pip install -r requirements.txt`

**메시지가 전송되지 않을 때**
- 카카오톡 채팅방 창이 화면에 열려 있는지 확인
- 채팅방 이름이 정확한지 확인 (부분 일치도 동작)

**자동완성 팝업 타이밍 오류로 명령어가 일반 텍스트로 전송될 때**
- `send_command()` 내 `delay 0.25` 값을 `0.4 ~ 0.6`으로 늘린다

**목표 레벨 도달해도 안 멈출 때**
- 로그에서 `result`, `from`, `to` 값 확인
- `SUCCESS_TEXT` 키워드가 실제 봇 메시지와 일치하는지 확인
