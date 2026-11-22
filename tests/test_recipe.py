"""
팀원 C (AI 식단 엔진) 유닛 테스트
- Pydantic 스키마 검증
- RecipeGenerator 지능형 Mock 생성 및 cuisine 확장 검증
- D-3 임박 식재료 우선 반영 검증
- 팀원 D 텔레그램 메시지 카드 포맷과의 호환성 검증
- CLI 실행 및 파일 저장 검증
"""
import json
import os
import sys
from unittest import mock
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.recipe.schema import Recipe, RecipeResponse  # noqa: E402
from src.recipe.generator import RecipeGenerator, generate_recipes  # noqa: E402
from src.recipe.prompts import build_recipe_prompt, SUPPORTED_CUISINES  # noqa: E402
from src.notify.messages import recipe_card, recipes_message  # noqa: E402
from src.main_c import main as main_c  # noqa: E402


def test_recipe_schema_validation():
    """Recipe Pydantic 모델의 유효성 검증"""
    data = {
        "title": "돼지고기 김치찌개",
        "cuisine": "한식",
        "time": "25분",
        "difficulty": "쉬움",
        "description": "묵은지와 삼겹살로 끓여낸 깊고 진한 맛",
        "uses_expiring": ["두부", "대파"],
        "ingredients": ["삼겹살 200g", "두부 1/2모", "대파 1대", "고춧가루 1큰술"],
        "steps": ["1. 삼겹살을 볶는다.", "2. 물을 붓고 두부와 대파를 넣는다."],
        "tips": "쌀뜨물을 사용하면 더욱 맛있습니다."
    }
    recipe = Recipe.model_validate(data)
    assert recipe.title == "돼지고기 김치찌개"
    assert recipe.cuisine == "한식"
    assert "두부" in recipe.uses_expiring
    assert len(recipe.steps) == 2

    response = RecipeResponse(recipes=[recipe])
    assert len(response.recipes) == 1
    dumped = response.model_dump()
    assert "recipes" in dumped
    assert dumped["recipes"][0]["title"] == "돼지고기 김치찌개"


def test_build_recipe_prompt():
    """프롬프트 생성 함수 검증"""
    available = ["삼겹살", "양파", "두부"]
    expiring = [{"name": "두부", "days_left": 1}]
    prompt = build_recipe_prompt(available, expiring, cuisine="양식", count=3)

    assert "삼겹살" in prompt
    assert "양파" in prompt
    assert "두부(D-1)" in prompt
    assert "양식" in prompt
    assert "3가지" in prompt


def test_recipe_generator_mock_default():
    """API 키가 없을 때 기본 Mock 레시피 생성 검증"""
    generator = RecipeGenerator(api_key=None)
    available = ["삼겹살", "양파", "두부"]
    expiring = [{"name": "두부", "days_left": 1}]

    recipes = generator.generate_recipes(
        available_ingredients=available,
        expiring_items=expiring,
        cuisine="한식",
        count=2,
        use_mock_if_no_key=True
    )

    assert len(recipes) == 2
    for r in recipes:
        assert "title" in r
        assert "cuisine" in r
        assert r["cuisine"] == "한식"
        assert "ingredients" in r
        assert "steps" in r
        assert isinstance(r["uses_expiring"], list)


def test_recipe_generator_cuisines():
    """다양한 cuisine 옵션(양식, 일식, 중식) Mock 생성 검증"""
    generator = RecipeGenerator(api_key=None)
    available = ["삼겹살", "대파"]
    expiring = [{"name": "삼겹살", "days_left": 2}]

    for cuisine in ["양식", "일식", "중식"]:
        recipes = generator.generate_recipes(
            available_ingredients=available,
            expiring_items=expiring,
            cuisine=cuisine,
            count=1,
            use_mock_if_no_key=True
        )
        assert len(recipes) == 1
        assert recipes[0]["cuisine"] == cuisine
        assert "삼겹살" in recipes[0]["title"] or any("삼겹살" in ing for ing in recipes[0]["ingredients"])


def test_recipe_generator_empty_ingredients():
    """재고가 없을 때 빈 목록 반환 검증"""
    generator = RecipeGenerator(api_key=None)
    recipes = generator.generate_recipes(
        available_ingredients=[],
        expiring_items=[],
        use_mock_if_no_key=True
    )
    assert recipes == []


def test_notify_recipes_compatibility():
    """팀원 C가 생성한 레시피가 팀원 D의 텔레그램 카드 포맷과 100% 호환되는지 검증"""
    generator = RecipeGenerator(api_key=None)
    recipes = generator.generate_recipes(
        available_ingredients=["두부", "대파"],
        expiring_items=[{"name": "두부", "days_left": 1}],
        cuisine="한식",
        count=2
    )

    # 1. 단일 카드 렌더링 확인
    card_html = recipe_card(recipes[0])
    assert f"🍳 <b>{recipes[0]['title']}</b>" in card_html
    assert "🌏 한식" in card_html
    assert "<b>재료</b>" in card_html
    assert "<b>만드는 법</b>" in card_html

    # 2. 복수 레시피 메시지 분할선 확인
    full_message = recipes_message(recipes)
    assert "━━━━━━━━━━" in full_message
    assert recipes[0]["title"] in full_message
    assert recipes[1]["title"] in full_message


def test_generate_recipes_convenience_function():
    """최상위 간편 함수 generate_recipes 검증"""
    recipes = generate_recipes(
        available_ingredients=["계란", "양파"],
        expiring_items=[{"name": "계란", "days_left": 0}],
        cuisine="한식",
        count=1
    )
    assert len(recipes) == 1
    assert recipes[0]["cuisine"] == "한식"


def test_main_c_cli_ingredients(capsys):
    """CLI에서 직접 식재료 입력 실행 테스트"""
    ret = main_c(["--ingredients", "삼겹살,양파", "--cuisine", "한식", "--count", "1"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "K-Refriger: 팀원 C 파트" in out
    assert "삼겹살" in out


def test_main_c_cli_save_json(tmp_path):
    """CLI에서 --save 옵션으로 JSON 저장 테스트"""
    save_file = str(tmp_path / "test_recipes.json")
    ret = main_c(["--ingredients", "두부", "--save", save_file, "--count", "1"])
    assert ret == 0
    assert os.path.exists(save_file)

    with open(save_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "recipes" in data
    assert len(data["recipes"]) == 1
    assert "두부" in data["recipes"][0]["title"] or any("두부" in i for i in data["recipes"][0]["ingredients"])


def test_main_c_cli_notify_dry_run(capsys):
    """CLI에서 --notify --dry-run 옵션 연동 테스트"""
    ret = main_c(["--ingredients", "두부", "--notify", "--dry-run", "--count", "1"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out.lower()
    assert "텔레그램 알림 전송 완료" in out
