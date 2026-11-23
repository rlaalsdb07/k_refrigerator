"""
식단 엔진 Pydantic v2 데이터 스키마
- Recipe: 레시피 카드 1개에 대한 정형화된 모델
- RecipeResponse: AI 생성 응답용 레시피 목록 래퍼
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Recipe(BaseModel):
    """맞춤형 추천 레시피 카드 모델"""
    title: str = Field(
        description="요리 명칭 (예: '돼지고기 김치 두루치기', '두부 마파덮밥')"
    )
    cuisine: str = Field(
        default="한식",
        description="요리 카테고리 (한식, 양식, 중식, 일식, 분식, 퓨전, 다이어트/건강식 등)"
    )
    time: str = Field(
        description="예상 조리 시간 (예: '15분', '25분')"
    )
    difficulty: str = Field(
        default="보통",
        description="조리 난이도 (쉬움, 보통, 어려움)"
    )
    description: str = Field(
        default="",
        description="요리 한 줄 소개 및 추천 이유"
    )
    uses_expiring: List[str] = Field(
        default_factory=list,
        description="활용된 유통기한 임박(D-3 이내) 식재료 목록"
    )
    ingredients: List[str] = Field(
        description="필요한 식재료 및 양념 목록 (분량 포함, 예: '삼겹살 200g', '양파 1/2개', '진간장 1큰술')"
    )
    steps: List[str] = Field(
        description="순서별 조리 단계 (Step-by-step 설명)"
    )
    tips: Optional[str] = Field(
        default=None,
        description="셰프의 팁 또는 보관/조리 시 주의사항"
    )


class RecipeResponse(BaseModel):
    """Gemini API 구조화 응답용 레시피 목록 래퍼"""
    recipes: List[Recipe] = Field(
        description="생성된 추천 레시피 목록"
    )
