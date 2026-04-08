"""
카카오톡 AX API 텍스트 읽기 실험 스크립트
pyobjc를 사용하여 AppleScript 제약을 우회하고
채팅 영역의 텍스트를 직접 읽을 수 있는지 테스트합니다.
"""
import time
import ApplicationServices as AS
import Quartz


def get_kakaotalk_pid():
    """카카오톡 프로세스 ID 찾기"""
    import subprocess
    result = subprocess.run(['pgrep', '-x', 'KakaoTalk'], capture_output=True, text=True)
    if result.stdout.strip():
        return int(result.stdout.strip().split('\n')[0])
    return None


def get_element_attribute(element, attr):
    """AX 요소의 속성 값을 안전하게 가져오기"""
    err, value = AS.AXUIElementCopyAttributeValue(element, attr, None)
    if err == 0:
        return value
    return None


def get_element_attributes(element):
    """AX 요소의 모든 속성 이름 목록"""
    err, attrs = AS.AXUIElementCopyAttributeNames(element, None)
    if err == 0:
        return list(attrs)
    return []


def explore_element(element, depth=0, max_depth=6):
    """UI 요소를 재귀적으로 탐색하여 구조와 텍스트 출력"""
    indent = "  " * depth

    role = get_element_attribute(element, "AXRole") or "?"
    title = get_element_attribute(element, "AXTitle") or ""
    value = get_element_attribute(element, "AXValue") or ""
    desc = get_element_attribute(element, "AXDescription") or ""
    role_desc = get_element_attribute(element, "AXRoleDescription") or ""

    # 텍스트 정보 표시
    text_info = ""
    if title:
        text_info += f' title="{title[:50]}"'
    if value and isinstance(value, str):
        text_info += f' value="{value[:80]}"'
    if desc:
        text_info += f' desc="{desc[:50]}"'

    print(f"{indent}[{depth}] {role} ({role_desc}){text_info}")

    if depth >= max_depth:
        children = get_element_attribute(element, "AXChildren")
        if children and len(children) > 0:
            print(f"{indent}  ... ({len(children)} children, max depth reached)")
        return

    # 자식 요소 탐색
    children = get_element_attribute(element, "AXChildren")
    if children:
        for i, child in enumerate(children):
            if i > 30:  # 너무 많으면 제한
                print(f"{indent}  ... (and {len(children) - 30} more children)")
                break
            explore_element(child, depth + 1, max_depth)


def find_chat_window(app, room_name=None):
    """카카오톡 채팅 창 찾기"""
    windows = get_element_attribute(app, "AXWindows")
    if not windows:
        print("창을 찾을 수 없습니다.")
        return None

    print(f"\n총 {len(windows)}개의 창 발견:")
    for i, win in enumerate(windows):
        title = get_element_attribute(win, "AXTitle") or "(제목 없음)"
        print(f"  {i}: {title}")
        if room_name and room_name in str(title):
            print(f"  → 대상 채팅방 발견!")
            return win

    if room_name:
        print(f"\n'{room_name}' 채팅방을 찾지 못했습니다.")
    return windows[0] if windows else None


def extract_texts_from_element(element, texts=None, depth=0, max_depth=10):
    """요소에서 모든 텍스트를 재귀적으로 추출"""
    if texts is None:
        texts = []

    if depth > max_depth:
        return texts

    # 텍스트 값 추출
    value = get_element_attribute(element, "AXValue")
    if value and isinstance(value, str) and value.strip():
        texts.append(value.strip())

    title = get_element_attribute(element, "AXTitle")
    if title and isinstance(title, str) and title.strip():
        texts.append(title.strip())

    # 자식 요소 재귀 탐색
    children = get_element_attribute(element, "AXChildren")
    if children:
        for child in children:
            extract_texts_from_element(child, texts, depth + 1, max_depth)

    return texts


def test_chat_text_reading(app, room_name=None):
    """채팅 영역에서 텍스트 읽기 시도"""
    win = find_chat_window(app, room_name)
    if not win:
        return

    win_title = get_element_attribute(win, "AXTitle") or "(제목 없음)"
    print(f"\n{'='*60}")
    print(f"채팅창 분석: {win_title}")
    print(f"{'='*60}")

    # 1단계: 전체 UI 구조 탐색 (depth 4까지)
    print("\n[1] UI 구조 탐색 (depth=4):")
    print("-" * 40)
    explore_element(win, max_depth=4)

    # 2단계: 모든 텍스트 추출 시도
    print(f"\n[2] 텍스트 추출 시도:")
    print("-" * 40)
    start = time.time()
    texts = extract_texts_from_element(win)
    elapsed = time.time() - start

    if texts:
        print(f"  {len(texts)}개 텍스트 추출 완료 ({elapsed:.3f}초)")
        print(f"\n  추출된 텍스트:")
        for i, t in enumerate(texts):
            print(f"  [{i:3d}] {t[:100]}")
    else:
        print(f"  텍스트를 추출하지 못했습니다. ({elapsed:.3f}초)")

    # 3단계: 채팅 영역(첫 번째 AXScrollArea) 집중 탐색
    print(f"\n[3] 채팅 영역 집중 탐색:")
    print("-" * 40)
    children = get_element_attribute(win, "AXChildren")
    if children:
        for i, child in enumerate(children):
            role = get_element_attribute(child, "AXRole") or "?"
            if "ScrollArea" in str(role):
                print(f"\n  UI element {i+1}: {role}")
                # 이 스크롤 영역의 자식들을 깊게 탐색
                scroll_children = get_element_attribute(child, "AXChildren")
                if scroll_children:
                    for j, sc in enumerate(scroll_children):
                        sc_role = get_element_attribute(sc, "AXRole") or "?"
                        print(f"    자식 {j}: {sc_role}")

                        # Table이면 행/셀 탐색
                        if "Table" in str(sc_role) or "List" in str(sc_role):
                            rows = get_element_attribute(sc, "AXRows") or get_element_attribute(sc, "AXChildren")
                            if rows:
                                print(f"      행 수: {len(rows)}")
                                # 마지막 5개 행만 읽기
                                for k, row in enumerate(rows[-5:]):
                                    row_texts = extract_texts_from_element(row, max_depth=5)
                                    if row_texts:
                                        combined = ' | '.join(row_texts)
                                        print(f"      행[{len(rows)-5+k}]: {combined[:120]}")
                                    else:
                                        row_role = get_element_attribute(row, "AXRole") or "?"
                                        row_attrs = get_element_attributes(row)
                                        print(f"      행[{len(rows)-5+k}]: (텍스트 없음, role={row_role}, attrs={row_attrs[:5]})")

                        # 텍스트 직접 추출 시도
                        sc_texts = extract_texts_from_element(sc, max_depth=6)
                        if sc_texts:
                            print(f"    → 텍스트 {len(sc_texts)}개: {sc_texts[:5]}")


def main():
    pid = get_kakaotalk_pid()
    if not pid:
        print("카카오톡이 실행되고 있지 않습니다.")
        return

    print(f"카카오톡 PID: {pid}")

    # AX 앱 요소 생성
    app = AS.AXUIElementCreateApplication(pid)

    # 채팅방 이름 입력
    room_name = input("채팅방 이름 (빈칸=첫 번째 창): ").strip() or None

    test_chat_text_reading(app, room_name)


if __name__ == "__main__":
    main()
