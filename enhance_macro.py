"""
카카오톡 강화 매크로 (macOS 버전 - 수정본)
"""

import pyautogui
import pyperclip
import subprocess
import time
import random
import easyocr
import json
import os
import re
import numpy as np
import threading

# ============================================================
# 설정
# ============================================================
TARGET_CHAT_ROOM = ""
TARGET_LEVEL = 13              # 이 레벨 도달하면 정지 (예: 4면 +4 도달시 정지)
SUCCESS_TEXT = "강화에 성공"
FAIL_TEXT = "강화 파괴"
KEEP_TEXT  = "의 레벨이 유지되었습니다"
STATS_FILE = "enhance_stats.json"
COMMAND = "/강화"
GOLD_LIMIT = 0                 # 이 골드 미만이 되면 정지 (0 = 기능 비활성화, 예: 100_000_000)

# 전역 상태
stop_requested = False

# OCR 리더 초기화
print("OCR 모델 로딩 중...")
reader = easyocr.Reader(['ko', 'en'], gpu=False)
print("OCR 모델 로딩 완료!\n")


# ============================================================
# 통계 클래스
# ============================================================
class EnhanceStats:
    def __init__(self, filename=STATS_FILE):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            "level_stats": {},
            "total_attempts": 0,
            "total_destroys": 0,
            "max_level_reached": 0
        }

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def record_success(self, from_level, to_level):
        level_key = str(from_level)
        if level_key not in self.data["level_stats"]:
            self.data["level_stats"][level_key] = {"success": 0, "fail": 0}
        self.data["level_stats"][level_key]["success"] += 1
        self.data["total_attempts"] += 1
        if to_level > self.data["max_level_reached"]:
            self.data["max_level_reached"] = to_level
        self.save()

    def record_destroy(self, at_level):
        level_key = str(at_level)
        if level_key not in self.data["level_stats"]:
            self.data["level_stats"][level_key] = {"success": 0, "fail": 0}
        self.data["level_stats"][level_key]["fail"] += 1
        self.data["total_attempts"] += 1
        self.data["total_destroys"] += 1
        self.save()

    def get_success_rate(self, level):
        level_key = str(level)
        if level_key not in self.data["level_stats"]:
            return None
        stats = self.data["level_stats"][level_key]
        total = stats["success"] + stats["fail"]
        return stats["success"] / total if total > 0 else None

    def simulate_to_20(self, simulations=10000):
        if not self.data["level_stats"]:
            return None, None
        probabilities = {}
        for level in range(20):
            rate = self.get_success_rate(level)
            probabilities[level] = rate if rate else max(0.1, 1.0 - (level * 0.04))

        successes = 0
        attempts_list = []
        for _ in range(simulations):
            current = 0
            attempts = 0
            while current < 20 and attempts < 100000:
                attempts += 1
                if random.random() < probabilities.get(current, 0.5):
                    current += 1
                else:
                    current = 0
            if current >= 20:
                successes += 1
                attempts_list.append(attempts)

        rate = successes / simulations
        avg = sum(attempts_list) / len(attempts_list) if attempts_list else None
        return rate, avg

    def print_stats(self):
        print("\n" + "=" * 55)
        print("  강화 통계")
        print("=" * 55)
        print(f"  총 시도: {self.data['total_attempts']}")
        print(f"  총 파괴: {self.data['total_destroys']}")
        print(f"  최고 레벨: +{self.data['max_level_reached']}")

        if self.data["level_stats"]:
            print("\n  [레벨별 성공률]")
            print("  " + "-" * 51)
            for level in range(20):
                key = str(level)
                if key in self.data["level_stats"]:
                    s = self.data["level_stats"][key]
                    total = s["success"] + s["fail"]
                    rate = (s["success"] / total * 100) if total > 0 else 0
                    bar = "#" * int(rate/5) + "-" * (20 - int(rate/5))
                    print(f"  +{level:2d}->+{level+1:2d}: [{bar}] {rate:5.1f}% ({s['success']}/{total})")

            print("\n  [+20 도달 예측]")
            sr, avg = self.simulate_to_20()
            if sr:
                print(f"  성공률: {sr*100:.4f}%, 평균 시도: {avg:,.0f}회")
        print("=" * 55 + "\n")

    def reset(self):
        self.data = {"level_stats": {}, "total_attempts": 0, "total_destroys": 0, "max_level_reached": 0}
        self.save()
        print("  통계 초기화 완료\n")


# ============================================================
# AppleScript 유틸리티
# ============================================================
def run_applescript(script):
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return None


def find_kakao_window(room_name):
    script = f'''
    tell application "System Events"
        tell process "KakaoTalk"
            set winNames to name of every window
            repeat with wName in winNames
                if wName contains "{room_name}" then
                    return wName as text
                end if
            end repeat
        end tell
    end tell
    return ""
    '''
    result = run_applescript(script)
    return result if result else None


def activate_kakao_window(room_name):
    script = f'''
    tell application "System Events"
        tell process "KakaoTalk"
            set frontmost to true
            set wins to every window
            repeat with w in wins
                if name of w contains "{room_name}" then
                    perform action "AXRaise" of w
                    return true
                end if
            end repeat
        end tell
    end tell
    return false
    '''
    run_applescript(script)
    time.sleep(0.15)


def get_window_bounds(room_name):
    script = f'''
    tell application "System Events"
        tell process "KakaoTalk"
            set wins to every window
            repeat with w in wins
                if name of w contains "{room_name}" then
                    set pos to position of w
                    set sz to size of w
                    return (item 1 of pos as string) & "," & (item 2 of pos as string) & "," & (item 1 of sz as string) & "," & (item 2 of sz as string)
                end if
            end repeat
        end tell
    end tell
    return ""
    '''
    result = run_applescript(script)
    if result:
        try:
            parts = result.split(',')
            return {
                'left': int(float(parts[0])),
                'top': int(float(parts[1])),
                'width': int(float(parts[2])),
                'height': int(float(parts[3]))
            }
        except:
            pass
    return None


def capture_chat_area(bounds):
    if not bounds:
        return None
    left = bounds['left'] + 10
    top = bounds['top'] + 80
    width = bounds['width'] - 20
    height = bounds['height'] - 180
    return pyautogui.screenshot(region=(left, top, width, height))


def read_chat_text(screenshot):
    if screenshot is None:
        return []
    img_array = np.array(screenshot)
    results = reader.readtext(img_array)
    return [r[1] for r in results]


def send_command(command, room_name):
    """
    명령어 전송 - 자동완성 팝업 대기 후 2단계 엔터
    1단계: 텍스트 입력 -> 딜레이 -> Enter (자동완성에서 명령어 선택)
    2단계: 다시 딜레이 -> Enter (전송)
    """
    script = f'''
    tell application "System Events"
        tell process "KakaoTalk"
            set frontmost to true
            set wins to every window
            repeat with w in wins
                if name of w contains "{room_name}" then
                    perform action "AXRaise" of w
                    delay 0.2
                    set inputScroll to UI element 11 of w
                    set tf to UI element 1 of inputScroll
                    set value of tf to "{command}"
                    set focused of tf to true
                    delay 0.6
                    key code 36
                    delay 0.3
                    key code 36
                    exit repeat
                end if
            end repeat
        end tell
    end tell
    '''
    run_applescript(script)


def parse_level_change(texts):
    combined = ' '.join(texts)
    arrow_patterns = [
        r'\+(\d+)\s*→\s*\+(\d+)',
        r'\+(\d+)\s*->\s*\+(\d+)',
        r'\+(\d+)\s*▶\s*\+(\d+)',
    ]
    for pattern in arrow_patterns:
        match = re.search(pattern, combined)
        if match:
            return int(match.group(1)), int(match.group(2))
    if '강화에 성공' in combined or '성공하셨습니다' in combined:
        match = re.search(r'\[\+(\d+)\]', combined)
        if match:
            to_lvl = int(match.group(1))
            return to_lvl - 1, to_lvl
    return None, None


def scan_current_level(texts, current_level=None):
    """화면 전체 OCR 텍스트에서 현재 강화 레벨을 읽어 반환.
    '+N -> +M' 또는 '[+N]' 패턴 중 값을 사용. 못 찾으면 None 반환.
    current_level 전달 시 ±3 범위 밖 값은 오인식으로 간주해 무시.
    """
    combined = ' '.join(texts)
    arrow_patterns = [
        r'\+(\d+)\s*→\s*\+(\d+)',
        r'\+(\d+)\s*->\s*\+(\d+)',
        r'\+(\d+)\s*▶\s*\+(\d+)',
    ]
    last_to = None
    for pattern in arrow_patterns:
        for m in re.finditer(pattern, combined):
            last_to = int(m.group(2))
    if last_to is not None:
        if current_level is not None and abs(last_to - current_level) > 3:
            print(f"[동기화 무시] 화살표 패턴 +{last_to} (현재 +{current_level}에서 ±3 초과, 오인식 의심)")
            return None
        return last_to
    # '[+N]' 패턴 중 가장 큰 값
    matches = re.findall(r'\[\+(\d+)\]', combined)
    if matches:
        candidates = [int(x) for x in matches]
        if current_level is not None:
            candidates = [v for v in candidates if abs(v - current_level) <= 3]
            if not candidates:
                print(f"[동기화 무시] '[+N]' 패턴 모두 ±3 초과 (현재 +{current_level}, 오인식 의심)")
                return None
        return max(candidates)
    return None


def parse_remaining_gold(texts):
    """OCR 텍스트에서 '남은 골드: NNN,NNNG' 패턴을 찾아 정수 반환.
    못 찾으면 None 반환.
    """
    combined = ' '.join(texts)
    # '남은 골드: 273,400,000G' / '남은골드:273,400,000G' 등 대응
    match = re.search(r'남은\s*골드\s*[:\uff1a]\s*([0-9,]+)\s*G', combined)
    if match:
        gold_str = match.group(1).replace(',', '')
        try:
            return int(gold_str)
        except ValueError:
            pass
    return None

def check_response(texts, last_texts, current_level=None):
    """새로운 메시지만 확인"""
    # 새 메시지 추출 (이전에 없던 것)
    new_texts = [t for t in texts if t not in last_texts]
    if not new_texts:
        return 'waiting', None, None
    combined = ' '.join(new_texts)
    from_lvl, to_lvl = parse_level_change(new_texts)
    if SUCCESS_TEXT in combined:
        return 'success', from_lvl, to_lvl
    if FAIL_TEXT in combined:
        return 'destroy', from_lvl, to_lvl
    if KEEP_TEXT in combined:
        return 'keep', from_lvl, to_lvl
    # '강화 성공' 또는 '속보' 키워드: OCR이 SUCCESS_TEXT를 못 읽어도 성공으로 확정
    if '강화 성공' in combined or '속보' in combined:
        if from_lvl is not None and to_lvl is not None:
            return 'success', from_lvl, to_lvl
        if current_level is not None:
            return 'success', current_level, current_level + 1
        return 'success', from_lvl, to_lvl
    # '[+0]' 패턴: OCR이 '강화 파괴' 키워드를 못 읽어도 파괴 감지
    if re.search(r'\[\+0\]', combined):
        return 'destroy', from_lvl, None
    if from_lvl is not None and to_lvl is not None and to_lvl > from_lvl:
        return 'success', from_lvl, to_lvl
    # new_texts에서 레벨 파싱 실패 시 전체 texts에서 재시도
    from_lvl2, to_lvl2 = parse_level_change(texts)
    if from_lvl2 is not None and to_lvl2 is not None and to_lvl2 > from_lvl2:
        return 'success', from_lvl2, to_lvl2
    return 'unknown', None, None

# ============================================================
# 입력 스레드
# ============================================================
def input_thread_func():
    """별도 스레드에서 입력 받기"""
    global stop_requested
    while True:
        try:
            cmd = input().strip().lower()
            if cmd in ['stop', 's', '2']:
                stop_requested = True
                print("\n[정지 요청됨]")
                break
        except:
            break


# ============================================================
# 메인
# ============================================================
def main():
    global TARGET_CHAT_ROOM, TARGET_LEVEL, GOLD_LIMIT, stop_requested

    stats = EnhanceStats()

    print("=" * 55)
    print("  카카오톡 강화 매크로")
    print("=" * 55)

    # 채팅방 설정
    print("\n  카카오톡에서 채팅방을 열어주세요.")
    while True:
        room = input("  채팅방 이름: ").strip()
        if room and find_kakao_window(room):
            TARGET_CHAT_ROOM = room
            print(f"  -> '{room}' 감지됨!\n")
            break
        print("  -> 찾을 수 없음. 다시 입력하세요.\n")

    # 메뉴
    while True:
        print("-" * 55)
        gold_limit_str = f"{GOLD_LIMIT:,}G" if GOLD_LIMIT > 0 else "없음"
        print(f"  현재 설정: 채팅방={TARGET_CHAT_ROOM}, 목표=+{TARGET_LEVEL}, 골드리밋={gold_limit_str}")
        print("-" * 55)
        print("  1. start  - 매크로 시작")
        print("  2. stats  - 통계 보기")
        print("  3. reset  - 통계 초기화")
        print("  4. room   - 채팅방 변경")
        print("  5. goal   - 목표 레벨 변경")
        print("  6. gold   - 골드 리밋 변경")
        print("  7. quit   - 종료")
        print("-" * 55)

        cmd = input("\n입력: ").strip().lower()

        if cmd in ['1', 'start']:
            run_macro(stats)

        elif cmd in ['2', 'stats']:
            stats.print_stats()

        elif cmd in ['3', 'reset']:
            if input("초기화? (y/n): ").lower() == 'y':
                stats.reset()

        elif cmd in ['4', 'room']:
            new_room = input("새 채팅방: ").strip()
            if new_room and find_kakao_window(new_room):
                TARGET_CHAT_ROOM = new_room
                print(f"변경됨: {new_room}")
            else:
                print("찾을 수 없음")

        elif cmd in ['5', 'goal']:
            try:
                new_goal = int(input("목표 레벨 (숫자만): ").strip())
                TARGET_LEVEL = new_goal
                print(f"목표 변경: +{TARGET_LEVEL}")
            except:
                print("숫자를 입력하세요")

        elif cmd in ['6', 'gold']:
            try:
                val = input("골드 리밋 (숫자만, 0=비활성화): ").strip().replace(',', '')
                GOLD_LIMIT = int(val)
                if GOLD_LIMIT > 0:
                    print(f"골드 리밋 변경: {GOLD_LIMIT:,}G 미만이 되면 정지")
                else:
                    print("골드 리밋 비활성화")
            except:
                print("숫자를 입력하세요")

        elif cmd in ['7', 'quit', 'q']:
            print("\n종료합니다.")
            stats.print_stats()
            break


def run_macro(stats):
    """매크로 실행"""
    global stop_requested
    stop_requested = False

    print("\n" + "=" * 55)
    print(f"  매크로 시작 - 대상: {TARGET_CHAT_ROOM}")
    print(f"  목표: +{TARGET_LEVEL} 도달시 정지")
    if GOLD_LIMIT > 0:
        print(f"  골드 리밋: {GOLD_LIMIT:,}G 미만이 되면 정지")
    else:
        print("  골드 리밋: 없음")
    print("  정지: Ctrl+C")
    print("=" * 55 + "\n")
    # 현재 레벨 수동 입력
    while True:
        try:
            user_input = input(f"  현재 레벨 입력 (숫자만, 목표: +{TARGET_LEVEL}): ").strip()
            current_level = int(user_input)
            if current_level < 0:
                print("  0 이상의 숫자를 입력하세요.")
                continue
            if current_level >= TARGET_LEVEL:
                print(f"  [경고] 현재 레벨 +{current_level}이 이미 목표 +{TARGET_LEVEL} 이상입니다.")
                print(f"  목표 레벨을 변경하거나 (메뉴 5. goal), 다른 레벨을 입력하세요.")
                continue
            break
        except ValueError:
            print("  숫자를 입력하세요.")

    last_texts = []
    last_known_gold = None
    just_destroyed = False  # 파괴 직후 루프에서 OCR 스캔 동기화 스킵 플래깅

    try:
        while not stop_requested:
            # 창 확인
            bounds = get_window_bounds(TARGET_CHAT_ROOM)
            if not bounds:
                print("[오류] 채팅방 창을 찾을 수 없음")
                break

            # 명령어 전송 전: OCR로 현재 레벨 동기화
            pre_screenshot = capture_chat_area(bounds)
            pre_texts = read_chat_text(pre_screenshot)
            if just_destroyed:
                # 파괴 직후는 화면에 이전 레벨 메시지가 남아있어 OCR 오독 가능 -> 스킵
                just_destroyed = False
            else:
                scanned_level = scan_current_level(pre_texts, current_level)
                if scanned_level is not None and scanned_level != current_level:
                    if scanned_level > current_level:
                        print(f"[동기화] +{current_level} -> +{scanned_level} (OCR 스캔)")
                        current_level = scanned_level
                    else:
                        print(f"[동기화 무시] OCR 스캔 +{scanned_level} < 현재 +{current_level} (오독 의심)")
            last_texts = pre_texts

            # 목표 레벨 도달 확인 (전송 전)
            if current_level >= TARGET_LEVEL:
                print(f"\n{'='*55}")
                print(f"  목표 달성! +{current_level} (목표: +{TARGET_LEVEL})")
                print(f"{'='*55}\n")
                break
            # 명령어 전송
            gold_display = f", 골드: {last_known_gold:,}G" if last_known_gold is not None else ""
            print(f"[전송] {COMMAND} (현재: +{current_level}{gold_display})")
            send_command(COMMAND, TARGET_CHAT_ROOM)

            time.sleep(0.3)
            start_time = time.time()
            result = 'waiting'
            from_lvl, to_lvl = None, None
            texts = last_texts.copy()
            snapshot_texts = last_texts.copy()
            while result in ('waiting', 'unknown') and (time.time() - start_time) < 5:
                time.sleep(0.4)
                screenshot = capture_chat_area(bounds)
                texts = read_chat_text(screenshot)
                result, from_lvl, to_lvl = check_response(texts, snapshot_texts, current_level)
            last_texts = texts.copy()

            # 골드 파싱 (새 텍스트에서)
            new_texts_for_gold = [t for t in texts if t not in snapshot_texts]
            parsed_gold = parse_remaining_gold(new_texts_for_gold)
            if parsed_gold is not None:
                last_known_gold = parsed_gold
                gold_info = f"{last_known_gold:,}G"
                print(f"[골드] 남은 골드: {gold_info}")
                if GOLD_LIMIT > 0 and last_known_gold < GOLD_LIMIT:
                    print(f"\n{'='*55}")
                    print(f"  골드 리밋 도달! 남은 골드: {last_known_gold:,}G (리밋: {GOLD_LIMIT:,}G)")
                    print(f"{'='*55}\n")
                    break

            print(f"[DEBUG] OCR: {texts[-5:] if texts else 'None'}")
            print(f"[DEBUG] result={result}, from={from_lvl}, to={to_lvl}")

            if result == 'success':
                if from_lvl is not None and to_lvl is not None:
                    stats.record_success(from_lvl, to_lvl)
                    current_level = to_lvl
                    print(f"[성공] +{from_lvl} -> +{to_lvl}")
                else:
                    current_level += 1
                    print(f"[성공] 추정 +{current_level}")
                if current_level >= TARGET_LEVEL:
                    print(f"\n{'='*55}")
                    print(f"  목표 달성! +{current_level} (목표: +{TARGET_LEVEL})")
                    print(f"{'='*55}\n")
                    break
            elif result == 'destroy':
                destroy_lvl = from_lvl if from_lvl else current_level
                stats.record_destroy(destroy_lvl)
                print(f"[파괴] +{destroy_lvl}에서 파괴됨")
                current_level = 0
                just_destroyed = True  # 다음 루프 OCR 스캔 스킵
            elif result == 'keep':
                keep_lvl = from_lvl if from_lvl is not None else current_level
                print(f"[유지] +{keep_lvl} 레벨 유지됨")
            elif result == 'waiting':
                print("[시간초과] 응답 없음 - 화면 스캔으로 레벨 동기화")
                combined_all = ' '.join(texts)
                match = re.search(r'\[\+(\d+)\]', combined_all)
                if match:
                    scanned = int(match.group(1))
                    if scanned != current_level:
                        print(f"[동기화] +{current_level} -> +{scanned}")
                        current_level = scanned
                if current_level >= TARGET_LEVEL:
                    print(f"\n{'='*55}")
                    print(f"  목표 달성 (동기화)! +{current_level} (목표: +{TARGET_LEVEL})")
                    print(f"{'='*55}\n")
                    break
            time.sleep(random.uniform(0.3, 0.5))

    except KeyboardInterrupt:
        print("\n\n[중단됨]")

    print("\n매크로 종료")
    stats.print_stats()


if __name__ == "__main__":
    main()
