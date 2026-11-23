"""
Gemini Vision API 기반 영수증 OCR 및 식재료/간식 정형화 파서
- 식재료(요리용)와 간식(완제품 디저트/음료) 명확 분류
- 비식품/공산품/생활잡화 등 이상한 제품은 100% 쳐내기(제외)
"""
import mimetypes
import os
from datetime import datetime
from typing import Optional, Any, List

from .schema import ReceiptParseResult, ReceiptItem
from ..db.expiry_calculator import ExpiryCalculator

# google-genai SDK 로드
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


class ReceiptParser:
    """비정형 마트/편의점 영수증을 파싱하여 정형화된 식재료/간식 목록 변환"""

    DEFAULT_PROMPT = """
당신은 스마트 냉장고 재고 관리 시스템의 영수증 파싱 AI 전문가입니다.
주어진 영수증 사진을 정밀하게 분석하여 식재료 및 간식 정보를 구조화된
JSON 데이터로 추출하세요.

[추출 및 분류 규칙]
1. purchase_date: 결제/구매일자를 YYYY-MM-DD 형식으로 추출하세요.
   (영수증에 명시된 날짜를 추출하되, 식별 불가 시: {today})
2. store_name: 마트, 슈퍼마켓, 편의점 상호명 (예: 이마트, 홈플러스, GS25 등)
3. items:
   - 구매한 품목 중 **식재료 및 간식/음료만** 추출합니다.

   ★ [핵심 규칙: 비식품 및 이상한 잡화 제품은 100% 쳐내기(제외)!]
     냄비, 국자, 스푼, 포크, 젓가락, 식기, 면봉, 화장지, 물티슈, 세제,
     샴푸, 린스, 비누, 치약, 칫솔, 쓰레기봉투/종량제봉투, 건전지,
     차량용품(불스원샷, 워셔액 등), 호일, 랩, 고무장갑, 수세미 등
     **먹을 수 없는 모든 공산품/생활용품/잡화는 반드시 쳐내고 절대 추출 마세요!**

   ★ [식재료 vs 간식 명확한 구분]
     - **요리용 식재료**: 채소, 육류, 닭고기, 수산물, 유제품, 계란,
       두부, 과일, 가공식품, 양념/조미료
     - **간식 파트**: 과자, 스낵, 빵, 호빵, 호떡, 떡, 초콜릿, 사탕,
       젤리, 아이스크림, 음료수(콜라, 주스 등), 주류(맥주, 소주 등) 등
       조리 없이 바로 먹는 완제품은 **반드시 category를 '간식'으로 지정**하세요.

   - name: 표준 대표 명칭 (예: '제주 삼겹살' -> '삼겹살', '포키 초코' -> '포키')
   - raw_name: 영수증에 인쇄된 원본 텍스트
   - quantity: 구매 수량 (기본 1.0)
   - unit: 단위 (개, 팩, 봉, g, ml, 단, 모, 캔, 병 등)
   - category: 채소, 육류, 닭고기, 수산물, 유제품, 계란, 두부, 과일,
     가공식품, 간식, 양념/조미료, 기타
   - is_seasoning: 소금, 간장, 고추장, 참기름 등 기본 양념 여부 (True/False)
4. total_amount: 총 결제 금액(숫자)
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.calculator = ExpiryCalculator()
        self.client: Any = None
        has_valid_key = bool(
            self.api_key and self.api_key != "your_gemini_api_key_here"
        )
        if HAS_GENAI and (genai is not None) and has_valid_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Gemini SDK 초기화 실패: {e}")

    def filter_and_clean_items(
        self, items: List[ReceiptItem]
    ) -> List[ReceiptItem]:
        """비식품(이상한 것들) 쳐내기 및 간식류 자동 정제"""
        cleaned: List[ReceiptItem] = []
        for it in items:
            raw = it.raw_name or ""
            name = it.name or ""

            # 1. 이상한 것들 (비식품/생활잡화) 100% 쳐내기
            if self.calculator.is_non_food(name, raw):
                print(f"🚫 [쳐내기 필터링] 비식품 잡화 제외: {name} ({raw})")
                continue

            # 2. 간식류 자동 재분류 (과자, 빵, 초콜릿, 음료, 주류 등)
            if self.calculator.is_snack(name, it.category):
                it.category = "간식"
                it.is_seasoning = False
            elif self.calculator.is_seasoning(name):
                it.is_seasoning = True

            cleaned.append(it)
        return cleaned

    def parse_receipt_image(
        self, image_path: str, use_mock_if_no_key: bool = True
    ) -> ReceiptParseResult:
        """영수증 이미지 경로를 받아 Gemini Vision으로 파싱"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(
                f"영수증 이미지 파일을 찾을 수 없습니다: {image_path}"
            )

        if self.client is None:
            if use_mock_if_no_key:
                print("[Info] 샘플 Mock 영수증 데이터로 처리합니다.")
                return self._generate_mock_result()
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."
            )

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        today_str = datetime.now().strftime("%Y-%m-%d")
        prompt = self.DEFAULT_PROMPT.format(today=today_str)

        try:
            assert types is not None
            response = self.client.models.generate_content(
                model="gemini-3.5-flash",
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=image_bytes, mime_type=mime_type
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ReceiptParseResult
                )
            )

            result_json = response.text or "{}"
            parsed = ReceiptParseResult.model_validate_json(result_json)
            # 2차 후처리 필터 적용 (이상한 잡화 쳐내기 & 간식 분류)
            parsed.items = self.filter_and_clean_items(parsed.items)
            return parsed

        except Exception as e:
            print(f"[Error] Gemini Vision API 호출 중 오류 발생: {e}")
            if use_mock_if_no_key:
                print("[Info] Fallback으로 Mock 영수증 데이터를 반환합니다.")
                return self._generate_mock_result()
            raise

    def _generate_mock_result(self) -> ReceiptParseResult:
        """테스트 및 API 키 미등록 시 사용할 샘플 영수증 데이터"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        raw_items = [
            ReceiptItem(
                name="삼겹살",
                raw_name="국내산 생삼겹살(구이용) 600g",
                quantity=1.0,
                unit="팩",
                category="육류",
                is_seasoning=False
            ),
            ReceiptItem(
                name="양파",
                raw_name="햇양파(대) 1.5kg망",
                quantity=1.0,
                unit="망",
                category="채소",
                is_seasoning=False
            ),
            ReceiptItem(
                name="두부",
                raw_name="찌개용 부침두부 300g",
                quantity=2.0,
                unit="모",
                category="두부",
                is_seasoning=False
            ),
            ReceiptItem(
                name="대파",
                raw_name="흙대파 1단",
                quantity=1.0,
                unit="단",
                category="채소",
                is_seasoning=False
            ),
            ReceiptItem(
                name="진간장",
                raw_name="샘표 진간장 금F3 860ml",
                quantity=1.0,
                unit="병",
                category="양념/조미료",
                is_seasoning=True
            ),
            ReceiptItem(
                name="초코파이",
                raw_name="오리온 초코파이 情 12입",
                quantity=1.0,
                unit="상자",
                category="간식",
                is_seasoning=False
            ),
            ReceiptItem(
                name="콜라",
                raw_name="코카콜라 1.5L",
                quantity=1.0,
                unit="병",
                category="간식",
                is_seasoning=False
            )
        ]
        return ReceiptParseResult(
            store_name="이마트 성수점",
            purchase_date=today_str,
            items=self.filter_and_clean_items(raw_items),
            total_amount=43800
        )
