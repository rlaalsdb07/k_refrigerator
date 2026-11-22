"""
팀원 C (AI 식단 엔진) 패키지
- RecipeGenerator: Gemini Vision/Text 기반 스마트 레시피 생성기
- Recipe, RecipeResponse: Pydantic v2 데이터 모델
- generate_recipes: 모듈 최상위 간편 호출 함수
"""
from .generator import RecipeGenerator, generate_recipes
from .schema import Recipe, RecipeResponse
from .prompts import SUPPORTED_CUISINES

__all__ = [
    "RecipeGenerator",
    "generate_recipes",
    "Recipe",
    "RecipeResponse",
    "SUPPORTED_CUISINES",
]
