# AX API Migration Plan

## Executive Summary

| 관점 | 내용 |
|------|------|
| **Problem** | 현재 OCR 방식(pyautogui + easyocr)은 화면 캡처 필수 → 다른 작업 불가, OCR 오인식 발생, 처리 속도 느림 |
| **Solution** | pyobjc AX API로 카카오톡 채팅 텍스트를 직접 읽어 OCR 대체. 100% 정확도 + 반백그라운드 실행 |
| **Function UX Effect** | 매크로 실행 중 다른 작업 가능 (전송 순간 ~0.4초만 포커스), OCR 오인식 제거로 안정성 대폭 향상 |
| **Core Value** | 속도·정확도·사용성 3가지 동시 개선. easyocr 의존성 제거로 설치 간소화 |

## Context Anchor

| 항목 | 내용 |
|------|------|
| **WHY** | OCR은 화면 점유 필수 + 오인식 위험. AX API는 원문 그대로 읽어 100% 정확 |
| **WHO** | 매크로 사용자 (macOS + 카카오톡) |
| **RISK** | 카카오톡 업데이트 시 UI 구조(AXTable) 변경 가능 → fallback 필요 |
| **SUCCESS** | 응답 감지 44ms (OCR 대비 7~20배), 오인식 0건, 반백그라운드 실행 가능 |
| **SCOPE** | 채팅 텍스트 읽기(check_response) 부분만 AX API로 교체. 명령어 전송(send_command)은 현행 유지 |

---

## 1. 배경 및 문제 정의

### 현재 방식의 한계

```
현재 흐름: send_command → time.sleep → pyautogui.screenshot() → easyocr.readtext() → check_response
```

| 문제 | 영향 |
|------|------|
| **화면 점유 필수** | 매크로 실행 중 다른 작업 불가. 창이 가려지면 OCR 실패 |
| **OCR 오인식** | `+N → +M` 숫자 오독, `MAX_LEVEL` 초과 감지, `±3 범위` 필터 등 방어 코드 필요 |
| **속도** | 스크린샷 캡처 + OCR 처리에 0.3~1초 소요 |
| **의존성** | easyocr(~100MB 모델 다운로드), numpy, pillow 필요 |

### AX API 실험 결과 (2026-04-08)

```python
# pyobjc로 카카오톡 채팅 텍스트 직접 읽기 성공
# UI 구조: Window → AXScrollArea(1번) → AXTable → AXRow → AXCell → 텍스트
# 결과: 509행, 1,606개 텍스트 추출 완료
```

**확인된 사실:**
- `AXTable`의 모든 행(AXRow)에 접근 가능 (AppleScript는 -10003 에러로 실패했으나 pyobjc는 성공)
- 메시지 텍스트가 **원문 그대로** 추출됨 (이모지, 한글, 숫자 포함)
- 강화 결과 키워드 완벽 인식: `〖✨강화 성공✨ +7 → +8〗`, `〖💥강화 파괴💥〗`, `〖💦강화 유지💦〗`
- `[+N]` 패턴, 골드 금액, 아이템 이름 등 모든 정보 정확
- 전체 채팅 히스토리 접근 가능 (화면에 보이지 않는 메시지도 포함)

---

## 2. 요구사항

### 기능 요구사항

| ID | 요구사항 | 우선순위 |
|----|----------|:--------:|
| FR-01 | pyobjc AX API로 채팅 영역 텍스트를 읽는 함수 구현 | 필수 |
| FR-02 | **마지막 5행만 읽기** (전체 520행 중 5행 = 44ms, 충분한 정보량) | 필수 |
| FR-03 | 기존 `check_response` 로직과 호환되는 텍스트 리스트 반환 | 필수 |
| FR-04 | AX API 실패 시 기존 OCR로 자동 fallback | 필수 |
| FR-05 | `scan_current_level`도 AX API 텍스트 활용 | 권장 |
| FR-06 | `parse_remaining_gold`도 AX API 텍스트 활용 | 권장 |
| FR-07 | easyocr/pyautogui 의존성을 선택적으로 변경 (AX 모드에서는 불필요) | 선택 |

### 비기능 요구사항

| ID | 요구사항 |
|----|----------|
| NFR-01 | 응답 감지 속도: **44ms 이내** (OCR 300~1000ms 대비 7~20배 향상, 벤치마크 확인 완료) |
| NFR-02 | 정확도: OCR 오인식 방어 코드 불필요한 수준 (100%) |
| NFR-03 | 카카오톡 창이 가려져 있어도 텍스트 읽기 가능 (최소화 제외) |
| NFR-04 | 기존 매크로 동작과 100% 호환 (결과 동일) |

---

### 벤치마크 결과 (2026-04-08)

| 범위 | 속도 | 텍스트 수 | 비고 |
|------|-----:|:---------:|------|
| 마지막 1행 | 4.6ms | 0개 | 빈 행 (구분선 등) |
| 마지막 3행 | 77ms | 8개 | 봇 응답 포함 |
| **마지막 5행** | **44ms** | **12개** | **채택 (최적)** |
| 마지막 10행 | 495ms | 30개 | 과다, 불필요 |
| 전체 520행 | 수초 | 1,600+개 | 초기 로딩에만 사용 |
| OCR (현재) | 300~1,000ms | 가변 | 오인식 포함 |

---

## 3. 기술 설계 방향

### 핵심 변경 범위

```
변경 대상:
  - read_chat_text()     → AX API로 대체 (핵심)
  - capture_chat_area()  → AX API 모드에서는 호출 불필요
  - check_response()     → 입력 형식 동일, 변경 불필요
  - run_macro() 폴링 루프 → AX API 호출로 교체

유지 대상:
  - send_command()       → 현행 AppleScript 방식 유지
  - parse_level_change() → 변경 불필요 (텍스트 입력 동일)
  - EnhanceStats         → 변경 불필요
```

### 새로 구현할 함수

```python
def read_chat_text_ax(room_name, last_n=10):
    """AX API로 채팅 텍스트를 직접 읽어 리스트로 반환.
    
    Args:
        room_name: 채팅방 이름
        last_n: 마지막 N개 행만 읽기 (성능 최적화)
    
    Returns:
        list[str]: 텍스트 리스트 (기존 read_chat_text와 동일 형식)
    """
```

### UI 구조 매핑

```
Window (채팅방명)
├── [0] AXScrollArea → AXTable (채팅 메시지 영역) ← 여기서 텍스트 읽기
│       └── AXRow → AXCell → 텍스트 요소들
├── [1] AXButton (프로필)
├── [2] AXStaticText (채팅방 이름)
├── ...
├── [10] AXScrollArea → AXTextArea (입력창) ← 기존 send_command 대상
├── [11~14] AXButton (추가기능, 이모티콘, 파일전송, 전송)
└── ...
```

> **주의:** 실험 결과 채팅 영역은 **UI element 1 (인덱스 0)**의 AXScrollArea.
> 기존 CLAUDE.md의 "UI element 11"은 입력창이 아닌 채팅 영역으로 오해될 수 있음.
> 실제로는 Window의 **첫 번째 자식**이 채팅 영역.

---

## 4. 구현 계획

### Phase 1: AX API 읽기 함수 구현 (핵심)

1. `read_chat_text_ax(room_name, last_n)` 함수 작성
2. 카카오톡 PID 캐싱 (매 루프마다 pgrep 호출 방지)
3. AXTable에서 마지막 N행만 읽는 최적화
4. 각 행의 텍스트를 리스트로 반환 (기존 `read_chat_text`와 호환 형식)

### Phase 2: 메인 루프 통합

1. `run_macro` 폴링 루프에서 `capture_chat_area` + `read_chat_text` → `read_chat_text_ax`로 교체
2. `snapshot_texts` / `last_texts` 비교 로직은 그대로 유지
3. 전송 전 레벨 동기화(`scan_current_level`)도 AX API 텍스트 활용

### Phase 3: Fallback 및 안정화

1. AX API 실패 시 자동 OCR fallback 구현
2. 카카오톡 프로세스 없음 / 창 없음 에러 처리
3. UI 구조 변경 감지 (AXTable 미발견 시 경고)

### Phase 4: 정리 (선택)

1. easyocr/pyautogui를 선택적 의존성으로 변경
2. `--mode ax|ocr` 실행 옵션 추가
3. CLAUDE.md 갱신

---

## 5. 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 |
|--------|:----:|:----:|------|
| 카카오톡 업데이트로 UI 구조 변경 | 중 | 높음 | AXTable 미발견 시 OCR fallback 자동 전환 |
| AXRow 접근 시 간헐적 에러 | 낮 | 중 | try/except + 재시도 |
| 최소화된 창에서 AX API 미작동 | 높 | 중 | 최소화 감지 → 복원 요청 메시지 |
| pyobjc 미설치 환경 | 낮 | 중 | pyobjc 없으면 자동 OCR 모드 |

---

## 6. 성공 기준

| 기준 | 측정 방법 |
|------|-----------|
| SC-01: AX API로 최신 메시지 텍스트 읽기 성공 | 강화 결과 키워드 100% 감지 |
| SC-02: OCR 대비 속도 3배 이상 향상 | 응답 감지까지 소요 시간 측정 (목표: <0.1초) |
| SC-03: 창이 가려진 상태에서도 텍스트 읽기 가능 | 다른 앱을 앞에 둔 상태로 매크로 실행 |
| SC-04: AX API 실패 시 OCR fallback 동작 | 카카오톡 종료 후 재시작 시나리오 |
| SC-05: 기존 통계 기록과 동일한 결과 | 동일 시나리오에서 성공/파괴/유지 카운트 비교 |
