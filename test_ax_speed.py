"""
AX API 속도 벤치마크: 전체 vs 마지막 N행
"""
import time
import subprocess
import ApplicationServices as AS


def get_kakaotalk_pid():
    result = subprocess.run(['pgrep', '-x', 'KakaoTalk'], capture_output=True, text=True)
    if result.stdout.strip():
        return int(result.stdout.strip().split('\n')[0])
    return None


def get_attr(element, attr):
    err, value = AS.AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == 0 else None


def extract_texts(element, texts=None, depth=0, max_depth=5):
    if texts is None:
        texts = []
    if depth > max_depth:
        return texts
    value = get_attr(element, "AXValue")
    if value and isinstance(value, str) and value.strip():
        texts.append(value.strip())
    title = get_attr(element, "AXTitle")
    if title and isinstance(title, str) and title.strip():
        texts.append(title.strip())
    children = get_attr(element, "AXChildren")
    if children:
        for child in children:
            extract_texts(child, texts, depth + 1, max_depth)
    return texts


def find_chat_table(app, room_name):
    """채팅 AXTable 찾기"""
    windows = get_attr(app, "AXWindows")
    if not windows:
        return None
    for win in windows:
        title = get_attr(win, "AXTitle") or ""
        if room_name in str(title):
            children = get_attr(win, "AXChildren")
            if children:
                for child in children:
                    role = get_attr(child, "AXRole") or ""
                    if "ScrollArea" in str(role):
                        scroll_children = get_attr(child, "AXChildren")
                        if scroll_children:
                            for sc in scroll_children:
                                sc_role = get_attr(sc, "AXRole") or ""
                                if "Table" in str(sc_role):
                                    return sc
    return None


def read_last_n_rows(table, n=3):
    """마지막 N개 행의 텍스트만 읽기"""
    rows = get_attr(table, "AXRows")
    if not rows:
        return []
    target_rows = rows[-n:] if len(rows) >= n else rows
    texts = []
    for row in target_rows:
        extract_texts(row, texts)
    return texts


def read_all_rows(table):
    """전체 행 텍스트 읽기"""
    rows = get_attr(table, "AXRows")
    if not rows:
        return []
    texts = []
    for row in rows:
        extract_texts(row, texts)
    return texts


def main():
    pid = get_kakaotalk_pid()
    if not pid:
        print("카카오톡이 실행되고 있지 않습니다.")
        return

    app = AS.AXUIElementCreateApplication(pid)
    room_name = input("채팅방 이름: ").strip()

    table = find_chat_table(app, room_name)
    if not table:
        print("채팅 테이블을 찾을 수 없습니다.")
        return

    rows = get_attr(table, "AXRows")
    print(f"\n총 행 수: {len(rows)}")
    print("=" * 50)

    # 벤치마크: 마지막 1, 3, 5, 10행 vs 전체
    for n in [1, 3, 5, 10]:
        start = time.time()
        texts = read_last_n_rows(table, n)
        elapsed = (time.time() - start) * 1000
        print(f"\n마지막 {n}행: {elapsed:.1f}ms, 텍스트 {len(texts)}개")
        if texts:
            # 마지막 텍스트 3개만 미리보기
            for t in texts[-3:]:
                print(f"  → {t[:80]}")

    # 전체 읽기
    start = time.time()
    all_texts = read_all_rows(table)
    elapsed = (time.time() - start) * 1000
    print(f"\n전체 {len(rows)}행: {elapsed:.1f}ms, 텍스트 {len(all_texts)}개")

    print("\n" + "=" * 50)
    print("결론: 매크로에서는 마지막 3~5행이면 충분합니다.")


if __name__ == "__main__":
    main()
