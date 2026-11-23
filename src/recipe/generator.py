"""
AI 맞춤형 식단 생성 엔진 (Gemini API 기반 및 Mock Fallback 지원)
- 잔여 식재료 및 D-3 임박 식재료를 반영한 맞춤형 레시피 동적 생성
- cuisine(한식, 양식, 중식, 일식 등) 옵션 확장 지원
- Pydantic 기반 구조화된 출력 및 팀원 D 텔레그램 알림 인터페이스 완벽 호환
"""
import json
import os
from typing import List, Dict, Any, Optional

from .schema import Recipe, RecipeResponse
from .prompts import (
    RECIPE_SYSTEM_PROMPT,
    build_recipe_prompt,
    SUPPORTED_CUISINES,
)

# google-genai SDK 로드 시도
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    HAS_GENAI = False

# .env 로드 시도
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".env")
)
if os.path.exists(_ENV_PATH):
    try:
        with open(_ENV_PATH, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip()
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass


class RecipeGenerator:
    """Gemini API 기반 맞춤형 AI 레시피 생성기"""

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model_name = model_name or self.DEFAULT_MODEL
        self.client: Any = None

        has_valid_key = bool(
            self.api_key and self.api_key != "your_gemini_api_key_here"
        )
        if HAS_GENAI and (genai is not None) and has_valid_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Gemini SDK 초기화 실패: {e}")

    def generate_recipes(
        self,
        available_ingredients: List[str],
        expiring_items: Optional[List[Dict[str, Any]]] = None,
        cuisine: Optional[str] = None,
        count: int = 2,
        use_mock_if_no_key: bool = True
    ) -> List[Dict[str, Any]]:
        """
        보유 식재료와 임박 재료를 바탕으로 맞춤형 레시피 카드 목록을 생성합니다.

        :param available_ingredients: 기본 양념이 제외된 보유 식재료 이름 리스트
        :param expiring_items: D-3 임박 식재료 dict 리스트 (name, days_left 등)
        :param cuisine: 요리 스타일 (한식, 양식, 중식, 일식 등)
        :param count: 추천받을 레시피 개수 (기본 2개)
        :param use_mock_if_no_key: API 키가 없거나 호출 실패 시 mock 데이터 사용 여부
        :return: 팀원 D의 notify_recipes 호환 dict 리스트
        """
        if expiring_items is None:
            expiring_items = []

        if not available_ingredients and not expiring_items:
            print("[Info] 보유 식재료 및 임박 식재료가 없어 레시피 생성을 생략합니다.")
            return []

        # API 클라이언트가 없을 경우
        if self.client is None:
            if use_mock_if_no_key:
                print("[Info] GEMINI_API_KEY 미설정으로 스마트 Mock 레시피를 생성합니다.")
                return self._generate_mock_recipes(
                    available_ingredients, expiring_items, cuisine, count
                )
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요."
            )

        prompt = build_recipe_prompt(
            available_ingredients=available_ingredients,
            expiring_items=expiring_items,
            cuisine=cuisine,
            count=count
        )

        try:
            assert types is not None
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    system_instruction=RECIPE_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=RecipeResponse,
                    temperature=0.7,
                )
            )

            result_text = response.text or "{}"
            parsed = RecipeResponse.model_validate_json(result_text)
            recipes_data = [r.model_dump() for r in parsed.recipes]
            return recipes_data

        except Exception as e:
            print(f"[Error] Gemini AI 레시피 생성 중 오류 발생: {e}")
            if use_mock_if_no_key:
                print("[Info] Fallback으로 스마트 Mock 레시피를 생성합니다.")
                return self._generate_mock_recipes(
                    available_ingredients, expiring_items, cuisine, count
                )
            raise

    def _generate_mock_recipes(
        self,
        available_ingredients: List[str],
        expiring_items: List[Dict[str, Any]],
        cuisine: Optional[str] = None,
        count: int = 2
    ) -> List[Dict[str, Any]]:
        """API 키가 없거나 테스트 시 사용할 지능형 Mock 레시피 생성기"""
        exp_names = [it.get("name", "") for it in expiring_items if it.get("name")]
        all_ings = list(dict.fromkeys(exp_names + available_ingredients))
        if not all_ings:
            all_ings = ["식재료"]

        selected_cuisine = cuisine if cuisine and cuisine != "전체" else "한식"

        mock_templates = {
            "한식": [
                {
                    "title": f"알뜰 {all_ings[0]} 된장찌개",
                    "cuisine": "한식",
                    "time": "20분",
                    "difficulty": "쉬움",
                    "description": f"냉장고 속 {all_ings[0]}와 구수한 된장이 어우러진 따뜻한 국물 요리",
                    "uses_expiring": exp_names[:2],
                    "ingredients": [
                        f"{all_ings[0]} 150g",
                        f"{all_ings[1]} 1/2개" if len(all_ings) > 1 else "양파 1/2개",
                        "된장 2큰술",
                        "다진 마늘 1작은술",
                        "물 500ml"
                    ],
                    "steps": [
                        "냄비에 물 500ml를 붓고 된장 2큰술을 체에 걸러 풀어줍니다.",
                        f"준비된 {all_ings[0]}와 부재료를 먹기 좋은 크기로 썰어 넣습니다.",
                        "중불에서 10~15분간 보글보글 끓인 뒤 다진 마늘로 풍미를 더해 완성합니다."
                    ],
                    "tips": "남은 찌개는 냉장 보관 후 다음 날 밥을 말아 드시면 더욱 깊은 맛이 납니다."
                },
                {
                    "title": f"매콤 {all_ings[0]} 볶음",
                    "cuisine": "한식",
                    "time": "15분",
                    "difficulty": "쉬움",
                    "description": f"기본 양념으로 뚝딱 완성하는 감칠맛 넘치는 밥도둑 볶음 요리",
                    "uses_expiring": [exp for exp in exp_names if exp != all_ings[0]][:2] or exp_names[:1],
                    "ingredients": [
                        f"{all_ings[0]} 200g",
                        f"{all_ings[-1]} 1개" if len(all_ings) > 1 else "대파 1대",
                        "진간장 1큰술",
                        "고춧가루 1큰술",
                        "설탕 1/2큰술",
                        "식용유 1큰술"
                    ],
                    "steps": [
                        "팬에 식용유를 두르고 중불에서 예열합니다.",
                        f"손질한 {all_ings[0]}를 넣고 센 불에서 빠르게 볶아 불향을 냅니다.",
                        "진간장, 고춧가루, 설탕을 넣고 양념이 골고루 배도록 3분간 더 볶아 마무리합니다."
                    ],
                    "tips": "마지막에 참기름 반 큰술과 깨를 뿌려주면 고소한 풍미가 극대화됩니다."
                }
            ],
            "양식": [
                {
                    "title": f"{all_ings[0]} 갈릭 버터 볶음 파스타",
                    "cuisine": "양식",
                    "time": "20분",
                    "difficulty": "보통",
                    "description": f"{all_ings[0]}의 고소함과 마늘의 알싸함이 어우러진 오일 파스타",
                    "uses_expiring": exp_names[:2],
                    "ingredients": [
                        f"{all_ings[0]} 150g",
                        "스파게티면 100g",
                        "다진 마늘 1큰술",
                        "식용유(또는 올리브유) 2큰술",
                        "소금, 후추 약간"
                    ],
                    "steps": [
                        "끓는 물에 소금을 넣고 스파게티면을 8분간 삶아 건져냅니다.",
                        "팬에 기름을 두르고 다진 마늘을 볶아 향을 냅니다.",
                        f"썰어둔 {all_ings[0]}를 넣고 노릇하게 볶은 후, 삶은 면과 면수 2국자를 넣고 소금·후추로 간을 맞춥니다."
                    ],
                    "tips": "면수를 조금씩 넣어가며 볶으면 소스가 면에 촉촉하게 흡수됩니다."
                },
                {
                    "title": f"프레시 {all_ings[0]} 웜 샐러드",
                    "cuisine": "양식",
                    "time": "15분",
                    "difficulty": "쉬움",
                    "description": f"가볍고 산뜻하게 즐기는 지중해풍 볶음 샐러드",
                    "uses_expiring": exp_names[:1],
                    "ingredients": [
                        f"{all_ings[0]} 150g",
                        "소금 1/2작은술",
                        "식용유 1큰술",
                        "후춧가루 약간"
                    ],
                    "steps": [
                        f"{all_ings[0]}를 한 입 크기로 썹니다.",
                        "달군 팬에 가볍게 볶아 숨을 죽입니다.",
                        "소금과 후추로 간을 하여 접시에 담아냅니다."
                    ],
                    "tips": "발사믹 식초나 레몬즙을 곁들이면 훨씬 상큼합니다."
                }
            ],
            "중식": [
                {
                    "title": f"{all_ings[0]} 굴소스 볶음밥",
                    "cuisine": "중식",
                    "time": "15분",
                    "difficulty": "쉬움",
                    "description": f"화력 넘치는 불맛과 {all_ings[0]}의 식감이 살아있는 중화풍 볶음밥",
                    "uses_expiring": exp_names[:2],
                    "ingredients": [
                        f"{all_ings[0]} 100g",
                        "밥 1공기",
                        "진간장 1작은술",
                        "식용유 2큰술",
                        "소금 한 꼬집"
                    ],
                    "steps": [
                        "팬에 기름을 두르고 다진 파와 마늘로 파기름을 만듭니다.",
                        f"{all_ings[0]}를 잘게 썰어 센 불에서 재빠르게 볶습니다.",
                        "밥을 넣고 주걱을 세워 고슬고슬 볶다가 진간장을 둘러 불맛을 냅니다."
                    ],
                    "tips": "찬밥을 사용하면 밥알이 뭉치지 않고 고슬고슬하게 볶아집니다."
                }
            ],
            "일식": [
                {
                    "title": f"{all_ings[0]} 간장 덮밥 (돈부리)",
                    "cuisine": "일식",
                    "time": "15분",
                    "difficulty": "쉬움",
                    "description": f"달콤 짭조름한 쯔유 소스에 졸여낸 {all_ings[0]}를 올린 든든한 한 그릇 덮밥",
                    "uses_expiring": exp_names[:2],
                    "ingredients": [
                        f"{all_ings[0]} 150g",
                        "밥 1공기",
                        "진간장 2큰술",
                        "설탕 1큰술",
                        "물 4큰술"
                    ],
                    "steps": [
                        "냄비에 간장, 설탕, 물을 넣고 약불에서 끓여 소스를 만듭니다.",
                        f"끓는 소스에 {all_ings[0]}를 넣고 양념이 배도록 5분간 조립니다.",
                        "따뜻한 밥 위에 조린 재료와 소스를 부어 완성합니다."
                    ],
                    "tips": "계란 노른자를 얹어 터뜨려 비벼 먹으면 더욱 부드럽습니다."
                }
            ]
        }

        pool = mock_templates.get(selected_cuisine, mock_templates["한식"])
        if len(pool) < count:
            # 부족하면 다른 카테고리에서 보충
            for c_name, c_recipes in mock_templates.items():
                if c_name != selected_cuisine:
                    pool.extend(c_recipes)
                if len(pool) >= count:
                    break

        selected = pool[:count]
        # Pydantic validation을 거쳐 안전한 dict로 반환
        validated = [Recipe.model_validate(item).model_dump() for item in selected]
        return validated


def generate_recipes(
    available_ingredients: List[str],
    expiring_items: Optional[List[Dict[str, Any]]] = None,
    cuisine: Optional[str] = None,
    count: int = 2,
    use_mock_if_no_key: bool = True
) -> List[Dict[str, Any]]:
    """팀원 A, 팀원 D 코드에서 간편하게 임포트해 사용할 수 있는 모듈 수준 함수"""
    generator = RecipeGenerator()
    return generator.generate_recipes(
        available_ingredients=available_ingredients,
        expiring_items=expiring_items,
        cuisine=cuisine,
        count=count,
        use_mock_if_no_key=use_mock_if_no_key
    )
