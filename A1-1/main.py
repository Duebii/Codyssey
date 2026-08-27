"""나만의 프롬프트 관리 프로그램."""

import json
from pathlib import Path

# ============================================================
# 1. 기본 데이터
# ============================================================

CATEGORIES = [
    "텍스트 생성",
    "이미지 생성",
    "영상 생성",
    "페르소나",
    "자동화",
    "기타",
]

REQUIRED_PROMPT_FIELDS = {"title", "content", "category", "favorite", "view_count"}
DATA_FILE = Path("prompts.json")
EXPORT_DIRECTORY = Path("exports")

# 프로그램을 실행하는 동안 관리하는 프롬프트 목록
prompts = [
    {
        "title": "블로그 글 작성 도우미",
        "content": "주어진 주제에 대해 SEO를 고려한 블로그 글을 작성해 주세요.",
        "category": "텍스트 생성",
        "favorite": True,
        "view_count": 0,
    },
    {
        "title": "제품 소개 이미지 생성",
        "content": "제품의 특징이 잘 드러나는 광고용 이미지를 생성해 주세요.",
        "category": "이미지 생성",
        "favorite": False,
        "view_count": 0,
    },
    {
        "title": "IT 콘텐츠 페르소나",
        "content": "초보자도 이해하기 쉽게 설명하는 IT 콘텐츠 전문가 역할을 해 주세요.",
        "category": "페르소나",
        "favorite": False,
        "view_count": 0,
    },
]

MENU_NAMES = {
    "1": "프롬프트 추가",
    "2": "프롬프트 목록",
    "3": "카테고리별 조회",
    "4": "프롬프트 검색",
    "5": "프롬프트 상세 보기",
    "6": "즐겨찾기 관리",
    "7": "즐겨찾기 목록",
    "8": "JSON 저장",
    "9": "JSON 불러오기",
    "10": "카테고리별 Markdown 내보내기",
    "11": "프롬프트 수정",
    "12": "프롬프트 삭제",
    "13": "조회수 Top 3 목록",
}


# ============================================================
# 2. 데이터 검증 함수
# ============================================================

def is_valid_prompt(prompt):
    """프롬프트가 필수 정보와 올바른 자료형을 갖췄는지 확인한다."""
    return (
        isinstance(prompt, dict)
        and set(prompt) == REQUIRED_PROMPT_FIELDS
        and isinstance(prompt["title"], str)
        and isinstance(prompt["content"], str)
        and isinstance(prompt["category"], str)
        and isinstance(prompt["favorite"], bool)
        and type(prompt["view_count"]) is int
        and prompt["view_count"] >= 0
    )


def is_valid_prompt_list(prompt_list):
    """프롬프트 전체 데이터가 딕셔너리 목록으로 구성됐는지 확인한다."""
    return isinstance(prompt_list, list) and all(
        is_valid_prompt(prompt) for prompt in prompt_list
    )


def add_missing_view_counts(prompt_list):
    """이전 저장 파일의 프롬프트에 조회수 기본값을 추가한다."""
    if not isinstance(prompt_list, list):
        return

    for prompt in prompt_list:
        if isinstance(prompt, dict) and "view_count" not in prompt:
            prompt["view_count"] = 0


# ============================================================
# 3. 입력 보조 함수
# ============================================================

def get_required_input(field_name):
    """비어 있지 않은 입력값을 받을 때까지 반복한다."""
    while True:
        value = input(f"{field_name}: ").strip()
        if value:
            return value
        print(f"{field_name}은(는) 비워 둘 수 없습니다. 다시 입력해 주세요.")


def select_category():
    """카테고리 목록에서 선택하거나 새 카테고리를 직접 입력받는다."""
    print("\n카테고리 선택:")
    for index, category in enumerate(CATEGORIES, start=1):
        print(f"{index}. {category}")

    while True:
        choice = input("번호 또는 새 카테고리 입력: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            return CATEGORIES[int(choice) - 1]
        if choice:
            return choice

        print("카테고리는 비워 둘 수 없습니다. 다시 입력해 주세요.")


# ============================================================
# 4. 프롬프트 기능
# ============================================================

def add_prompt():
    """입력받은 프롬프트를 목록에 추가한다."""
    print("\n=== 프롬프트 추가 ===")
    title = get_required_input("제목")
    content = get_required_input("내용")
    category = select_category()

    # 새 항목은 실행 중인 prompts 리스트에 저장되고 즐겨찾기는 기본 해제다.
    new_prompt = {
        "title": title,
        "content": content,
        "category": category,
        "favorite": False,
        "view_count": 0,
    }
    prompts.append(new_prompt)

    print(f"'{title}' 프롬프트가 추가되었습니다.")
    return new_prompt


def show_list():
    """번호, 제목, 카테고리, 즐겨찾기 여부와 함께 목록을 출력한다."""
    print("\n=== 프롬프트 목록 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return

    for index, prompt in enumerate(prompts, start=1):
        favorite_mark = "★" if prompt["favorite"] else "☆"
        print(
            f"{index}. [{prompt['category']}] {prompt['title']} {favorite_mark}"
        )


def show_categories():
    """카테고리별 조회에 사용할 카테고리 목록을 출력한다."""
    print("\n=== 카테고리별 조회 ===")
    for index, category in enumerate(CATEGORIES, start=1):
        print(f"{index}. {category}")


def select_category_for_search():
    """조회할 카테고리를 번호로 선택받는다."""
    while True:
        choice = input("카테고리 번호 선택: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            return CATEGORIES[int(choice) - 1]

        print("올바른 카테고리 번호를 입력해 주세요.")


def show_prompts_by_category():
    """선택한 카테고리에 속하는 프롬프트만 출력한다."""
    show_categories()
    category = select_category_for_search()
    filtered_prompts = [
        prompt for prompt in prompts if prompt["category"] == category
    ]

    print(f"\n=== [{category}] 카테고리 프롬프트 ===")
    if not filtered_prompts:
        print(f"'{category}' 카테고리에 등록된 프롬프트가 없습니다.")
        return

    for index, prompt in enumerate(filtered_prompts, start=1):
        favorite_mark = "★" if prompt["favorite"] else "☆"
        print(f"{index}. {prompt['title']} {favorite_mark}")


def search_prompt():
    """검색어가 제목 또는 내용에 포함된 프롬프트를 찾는다."""
    print("\n=== 프롬프트 검색 ===")
    keyword = get_required_input("검색어")
    keyword_lower = keyword.lower()
    matched_prompts = [
        prompt
        for prompt in prompts
        if keyword_lower in prompt["title"].lower()
        or keyword_lower in prompt["content"].lower()
    ]
    print(f"\n=== '{keyword}' 검색 결과 ===")
    if not matched_prompts:
        print("검색 결과가 없습니다.")
        return matched_prompts

    for index, prompt in enumerate(matched_prompts, start=1):
        favorite_mark = "★" if prompt["favorite"] else "☆"
        print(
            f"{index}. [{prompt['category']}] {prompt['title']} {favorite_mark}"
        )

    return matched_prompts


def show_prompt_detail():
    """선택한 프롬프트의 상세 정보를 출력한다."""
    print("\n=== 프롬프트 상세 보기 ===")
    selected_prompt = get_prompt_by_number()
    if selected_prompt is None:
        return

    favorite_mark = "★" if selected_prompt["favorite"] else "☆"
    selected_prompt["view_count"] += 1

    print("-" * 40)
    print(f"제목: {selected_prompt['title']}")
    print(f"카테고리: {selected_prompt['category']}")
    print(f"즐겨찾기: {favorite_mark}")
    print(f"상세 보기 횟수: {selected_prompt['view_count']}회")
    print("내용:")
    print(selected_prompt["content"])
    print("-" * 40)
    return selected_prompt


def get_prompt_index_by_number():
    """올바른 프롬프트 번호를 입력받아 목록의 위치를 반환한다."""
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return None

    while True:
        prompt_number = input("프롬프트 번호: ").strip()
        if prompt_number.isdigit():
            prompt_index = int(prompt_number) - 1
            if 0 <= prompt_index < len(prompts):
                return prompt_index

        print("존재하지 않는 프롬프트 번호입니다. 다시 입력해 주세요.")


def get_prompt_by_number():
    """올바른 프롬프트 번호를 입력받아 해당 프롬프트를 반환한다."""
    prompt_index = get_prompt_index_by_number()
    if prompt_index is None:
        return None
    return prompts[prompt_index]


def toggle_favorite():
    """프롬프트 번호를 입력받아 즐겨찾기 상태를 반대로 바꾼다."""
    print("\n=== 즐겨찾기 관리 ===")
    selected_prompt = get_prompt_by_number()
    if selected_prompt is None:
        return

    selected_prompt["favorite"] = not selected_prompt["favorite"]

    if selected_prompt["favorite"]:
        print(f"'{selected_prompt['title']}'을(를) 즐겨찾기에 추가했습니다.")
    else:
        print(f"'{selected_prompt['title']}'을(를) 즐겨찾기에서 해제했습니다.")

    return selected_prompt


def select_category_for_edit(current_category):
    """수정할 카테고리를 선택받고 빈 입력이면 기존 값을 유지한다."""
    print("\n카테고리 선택 (Enter를 누르면 기존 카테고리를 유지합니다):")
    for index, category in enumerate(CATEGORIES, start=1):
        print(f"{index}. {category}")

    while True:
        choice = input(f"번호 또는 새 카테고리 입력 ({current_category} 유지): ").strip()
        if not choice:
            return current_category
        if choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES):
            return CATEGORIES[int(choice) - 1]
        if choice:
            return choice


def edit_prompt():
    """선택한 프롬프트의 제목, 내용, 카테고리를 수정한다."""
    print("\n=== 프롬프트 수정 ===")
    show_list()
    prompt_index = get_prompt_index_by_number()
    if prompt_index is None:
        return

    selected_prompt = prompts[prompt_index]
    title = input(f"새 제목 (Enter: {selected_prompt['title']} 유지): ").strip()
    content = input("새 내용 (Enter: 기존 내용 유지): ").strip()
    category = select_category_for_edit(selected_prompt["category"])

    if title:
        selected_prompt["title"] = title
    if content:
        selected_prompt["content"] = content
    selected_prompt["category"] = category

    print(f"'{selected_prompt['title']}' 프롬프트를 수정했습니다.")
    return selected_prompt


def delete_prompt():
    """선택한 프롬프트를 확인 후 목록에서 삭제한다."""
    print("\n=== 프롬프트 삭제 ===")
    show_list()
    prompt_index = get_prompt_index_by_number()
    if prompt_index is None:
        return

    selected_prompt = prompts[prompt_index]
    confirmation = input(
        f"'{selected_prompt['title']}' 프롬프트를 삭제할까요? (y/N): "
    ).strip().lower()
    if confirmation != "y":
        print("삭제를 취소했습니다.")
        return

    deleted_prompt = prompts.pop(prompt_index)
    print(f"'{deleted_prompt['title']}' 프롬프트를 삭제했습니다.")
    return deleted_prompt


def show_favorites():
    """즐겨찾기로 표시된 프롬프트만 목록으로 출력한다."""
    print("\n=== 즐겨찾기 목록 ===")
    favorite_prompts = [prompt for prompt in prompts if prompt["favorite"]]

    if not favorite_prompts:
        print("즐겨찾기한 프롬프트가 없습니다.")
        return

    for index, prompt in enumerate(favorite_prompts, start=1):
        print(f"{index}. [{prompt['category']}] {prompt['title']} ★")


def show_top_viewed_prompts():
    """상세 보기 횟수가 많은 프롬프트 상위 3개를 출력한다."""
    print("\n=== 조회수 Top 3 프롬프트 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return []

    sorted_prompts = sorted(
        prompts,
        key=lambda prompt: prompt["view_count"],
        reverse=True,
    )
    top_prompts = sorted_prompts[:3]

    for rank, prompt in enumerate(top_prompts, start=1):
        favorite_mark = "★" if prompt["favorite"] else "☆"
        print(
            f"{rank}위. [{prompt['category']}] {prompt['title']} "
            f"{favorite_mark} - 조회 {prompt['view_count']}회"
        )

    return top_prompts


def save_prompts_to_json():
    """현재 프롬프트 목록을 JSON 파일로 저장한다."""
    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(prompts, file, ensure_ascii=False, indent=2)

    print(f"{len(prompts)}개의 프롬프트를 '{DATA_FILE}' 파일에 저장했습니다.")


def load_prompts_from_json():
    """JSON 파일의 프롬프트 목록을 현재 목록으로 불러온다."""
    if not DATA_FILE.exists():
        print(f"'{DATA_FILE}' 파일이 없습니다. 먼저 저장해 주세요.")
        return

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            loaded_prompts = json.load(file)
    except (OSError, json.JSONDecodeError):
        print("JSON 파일을 불러오지 못했습니다.")
        return

    add_missing_view_counts(loaded_prompts)
    if not is_valid_prompt_list(loaded_prompts):
        print("올바른 프롬프트 데이터 형식이 아닙니다.")
        return

    prompts.clear()
    prompts.extend(loaded_prompts)
    print(f"{len(prompts)}개의 프롬프트를 불러왔습니다.")


def get_safe_filename(category):
    """카테고리를 Windows에서 사용할 수 있는 파일명으로 바꾼다."""
    invalid_characters = '\\/:*?"<>|'
    return "".join("_" if char in invalid_characters else char for char in category)


def export_prompts_by_category():
    """프롬프트를 카테고리별 Markdown 파일로 내보낸다."""
    if not prompts:
        print("내보낼 프롬프트가 없습니다.")
        return

    EXPORT_DIRECTORY.mkdir(exist_ok=True)
    prompts_by_category = {}
    for prompt in prompts:
        category = prompt["category"]
        prompts_by_category.setdefault(category, []).append(prompt)

    for category, category_prompts in prompts_by_category.items():
        file_path = EXPORT_DIRECTORY / f"{get_safe_filename(category)}.md"
        lines = [f"# {category} 프롬프트", ""]

        for index, prompt in enumerate(category_prompts, start=1):
            favorite_text = "예" if prompt["favorite"] else "아니오"
            lines.extend(
                [
                    f"## {index}. {prompt['title']}",
                    f"- 즐겨찾기: {favorite_text}",
                    f"- 내용: {prompt['content']}",
                    "",
                ]
            )

        file_path.write_text("\n".join(lines), encoding="utf-8")

    print(
        f"{len(prompts_by_category)}개 카테고리의 Markdown 파일을 "
        f"'{EXPORT_DIRECTORY}' 폴더에 저장했습니다."
    )


# ============================================================
# 5. 메뉴 함수
# ============================================================

def show_menu():
    """프로그램에서 선택할 수 있는 메뉴를 출력한다."""
    print("\n=== 나만의 프롬프트 관리 ===")
    for number, name in MENU_NAMES.items():
        print(f"{number}. {name}")
    print("0. 종료")


def handle_menu_choice(choice):
    """선택한 메뉴의 기능을 실행하거나 안내를 출력한다."""
    if choice == "1":
        add_prompt()
        return

    if choice == "2":
        show_list()
        return

    if choice == "3":
        show_prompts_by_category()
        return

    if choice == "4":
        search_prompt()
        return

    if choice == "5":
        show_prompt_detail()
        return

    if choice == "6":
        toggle_favorite()
        return

    if choice == "7":
        show_favorites()
        return

    if choice == "8":
        save_prompts_to_json()
        return

    if choice == "9":
        load_prompts_from_json()
        return

    if choice == "10":
        export_prompts_by_category()
        return

    if choice == "11":
        edit_prompt()
        return

    if choice == "12":
        delete_prompt()
        return

    if choice == "13":
        show_top_viewed_prompts()
        return

    if choice not in MENU_NAMES:
        print("잘못된 메뉴 번호입니다. 다시 선택해 주세요.")
        return

    print(f"'{MENU_NAMES[choice]}' 기능은 준비 중입니다.")


# ============================================================
# 6. 프로그램 실행
# ============================================================

def main():
    """메뉴를 반복 출력하고 사용자 선택을 처리한다."""
    print("나만의 프롬프트 관리 프로그램을 시작합니다.")

    while True:
        show_menu()
        choice = input("선택: ").strip()

        if choice == "0":
            print("프로그램을 종료합니다.")
            break

        handle_menu_choice(choice)


if __name__ == "__main__":
    main()


