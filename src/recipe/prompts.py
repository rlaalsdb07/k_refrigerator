"""
AI 식단 엔진 프롬프트 템플릿 및 설정
"""
from typing import List, Dict, Any, Optional

SUPPORTED_CUISINES = [
    "한식",
    "양식",
    "중식",
    "일식",
    "분식",
    "퓨전",
    "다이어트/건강식"
]

RECIPE_SYSTEM_PROMPT = """
당신은 냉장고 재고 관리 및 음식물 쓰레기 감축을 전문으로 하는 스마트 냉장고 'K-Refriger'의 수석 AI 셰프입니다.
사용자의 냉장고에 보관된 잔여 식재료와 유통기한 임박 식재료를 바탕으로, 실용적이고 맛있는 맞춤형 요리 레시피를 제안합니다.

[핵심 규칙]
1. **재고 우선 활용**: 제공된 [보유 식재료] 목록에 있는 재료를 주재료로 적극 활용하세요.
2. **유통기한 임박 재료 최우선 소비**: [유통기한 임박 식재료]가 있다면 반드시 레시피에 우선적으로 포함시키고, `uses_expiring` 필드에 실제로 사용한 임박 식재료명을 명시하세요.
3. **기본 양념 활용**: 가정에 상비되어 있는 기본 양념(간장, 된장, 고추장, 소금, 설탕, 식용유, 마늘, 후추, 참기름 등)은 보유 목록에 없더라도 자유롭게 활용할 수 있습니다.
4. **cuisine(요리 스타일) 반영**: 사용자가 지정한 요리 카테고리(한식, 양식, 중식, 일식 등)에 알맞은 메뉴를 제안하세요.
5. **명확하고 실현 가능한 조리법**: 요리 초보자도 쉽게 따라할 수 있도록 조리 단계(steps)를 구체적으로 작성하세요.
6. **형식 준수**: 반드시 요청된 JSON 스키마 형식에 맞춰 응답하세요.
"""


def build_recipe_prompt(
    available_ingredients: List[str],
    expiring_items: List[Dict[str, Any]],
    cuisine: Optional[str] = None,
    count: int = 2
) -> str:
    """사용자 조건에 맞는 레시피 생성 프롬프트 조립"""
    expiring_names = []
    for it in expiring_items:
        name = it.get("name", "")
        days_left = it.get("days_left")
        if name:
            if days_left is not None:
                expiring_names.append(f"{name}(D-{days_left})")
            else:
                expiring_names.append(name)

    avail_str = ", ".join(available_ingredients) if available_ingredients else "없음"
    exp_str = ", ".join(expiring_names) if expiring_names else "없음 (모든 재료 유통기한 여유)"

    cuisine_instruction = ""
    if cuisine and cuisine != "전체":
        cuisine_instruction = f"- 요리 카테고리(cuisine): 반드시 **[{cuisine}]** 스타일의 요리로 구성해 주세요."
    else:
        cuisine_instruction = "- 요리 카테고리(cuisine): 한식, 양식, 중식, 일식, 퓨전 등 다양하고 매력적인 스타일로 구성해 주세요."

    prompt = f"""
[냉장고 보유 식재료 (기본 양념 제외)]
{avail_str}

[유통기한 임박(D-3 이내) 우선 소비 권장 식재료]
{exp_str}

[요청 사항]
- 추천 레시피 개수: 총 {count}가지
{cuisine_instruction}
- 유통기한 임박 재료를 주재료로 알뜰하게 소비할 수 있는 메뉴를 제안해 주세요.
- 조리 시간, 난이도, 1인 가구 기준 명확한 계량(큰술, g 등), 단계별 조리 순서를 빠짐없이 작성해 주세요.
"""
    return prompt.strip()
