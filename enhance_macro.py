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
STATS_FILE = "enhance_stats.json"
COMMAND = "/강화"

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


def check_response(texts, last_texts):
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
    if from_lvl is not None and to_lvl is not None and to_lvl > from_lvl:
        return 'success', from_lvl, to_lvl

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
    global TARGET_CHAT_ROOM, TARGET_LEVEL, stop_requested

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
        print(f"  현재 설정: 채팅방={TARGET_CHAT_ROOM}, 목표=+{TARGET_LEVEL}")
        print("-" * 55)
        print("  1. start  - 매크로 시작")
        print("  2. stats  - 통계 보기")
        print("  3. reset  - 통계 초기화")
        print("  4. room   - 채팅방 변경")
        print("  5. goal   - 목표 레벨 변경")
        print("  6. quit   - 종료")
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

        elif cmd in ['6', 'quit', 'q']:
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

    try:
        while not stop_requested:
            # 창 확인
            bounds = get_window_bounds(TARGET_CHAT_ROOM)
            if not bounds:
                print("[오류] 채팅방 창을 찾을 수 없음")
                break

            # 명령어 전송
            print(f"[전송] {COMMAND} (현재: +{current_level})")
            send_command(COMMAND, TARGET_CHAT_ROOM)

            time.sleep(0.3)
            start_time = time.time()
            result = 'waiting'
            from_lvl, to_lvl = None, None
            texts = last_texts.copy()
            snapshot_texts = last_texts.copy()
            while result == 'waiting' and (time.time() - start_time) < 5:
                time.sleep(0.8)
                screenshot = capture_chat_area(bounds)
                texts = read_chat_text(screenshot)
                result, from_lvl, to_lvl = check_response(texts, snapshot_texts)
            last_texts = texts.copy()

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
            time.sleep(random.uniform(0.4, 0.7))

    except KeyboardInterrupt:
        print("\n\n[중단됨]")

    print("\n매크로 종료")
    stats.print_stats()


if __name__ == "__main__":
    main()
