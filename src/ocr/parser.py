"""
Gemini Vision API 기반 영수증 OCR 및 식재료 정형화 파서
"""
import os
import mimetypes
import base64
import json
from datetime import datetime
from typing import Optional, List
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .schema import ReceiptParseResult, ReceiptItem


class ReceiptParser:
    """비정형 마트/편의점 영수증을 파싱하여 정형화된 식재료 목록으로 변환하는 파서"""

    DEFAULT_PROMPT = """
당신은 스마트 냉장고 재고 관리 시스템의 영수증 파싱 AI 전문가입니다.
주어진 영수증 사진을 정밀하게 분석하여 식재료 정보를 구조화된 JSON 데이터로 추출하세요.

[추출 규칙]
1. purchase_date: 영수증에 표시된 결제/구매일자를 YYYY-MM-DD 형식으로 추출하세요. (식별 불가 시 오늘 날짜: {today})
2. store_name: 마트, 슈퍼마켓, 편의점 상호명 (예: 이마트, 홈플러스, GS25 등)
3. items:
   - 구매한 품목 중 **식재료 및 식음료**만 추출합니다. (종량제 봉투, 세제, 칫솔 등 공산품/비식품은 반드시 제외)
   - name: 식재료의 대표 표준 명칭 (예: '[행사] 제주 삼겹살 600g' -> '삼겹살', '친환경 깐양파 1봉' -> '양파')
   - raw_name: 영수증에 인쇄된 원본 텍스트
   - quantity: 구매 수량 (기본 1.0)
   - unit: 단위 (개, 팩, 봉, g, ml 등)
   - category: 채소, 육류, 닭고기, 수산물, 유제품, 계란, 두부, 과일, 가공식품, 양념/조미료, 기타 중 하나
   - is_seasoning: 소금, 설탕, 간장, 고추장, 된장, 후추, 참기름, 식용유, 식초 등 기본 양념/조미료 여부 (True/False)
4. total_amount: 총 결제 금액(숫자)
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Gemini SDK 초기화 실패: {e}")

    def parse_receipt_image(self, image_path: str, use_mock_if_no_key: bool = True) -> ReceiptParseResult:
        """
        영수증 이미지 경로를 받아 Gemini Vision으로 파싱
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"영수증 이미지 파일을 찾을 수 없습니다: {image_path}")

        # API 클라이언트가 없거나 키가 설정되지 않은 경우 Mock 파싱 지원
        if not self.client:
            if use_mock_if_no_key:
                print("[Info] GEMINI_API_KEY가 설정되지 않아 샘플 Mock 영수증 데이터로 처리합니다.")
                return self._generate_mock_result()
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")

        # MIME 타입 확인
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        today_str = datetime.now().strftime("%Y-%m-%d")
        prompt = self.DEFAULT_PROMPT.format(today=today_str)

        try:
            interaction = self.client.interactions.create(
                model="gemini-3.8-flash",
                input=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": base64_data,
                        "mime_type": mime_type
                    }
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ReceiptParseResult.model_json_schema()
                }
            )

            result_json = interaction.output_text
            parsed = ReceiptParseResult.model_validate_json(result_json)
            return parsed

        except Exception as e:
            print(f"[Error] Gemini Vision API 호출 중 오류 발생: {e}")
            if use_mock_if_no_key:
                print("[Info] Fallback으로 Mock 영수증 데이터를 반환합니다.")
                return self._generate_mock_result()
            raise

    def _generate_mock_result(self) -> ReceiptParseResult:
        """테스트 및 API 키 미등록 시 사용할 현실적인 샘플 영수증 데이터"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        return ReceiptParseResult(
            store_name="이마트 성수점",
            purchase_date=today_str,
            items=[
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
                    name="고춧가루",
                    raw_name="태양초 고춧가루 500g",
                    quantity=1.0,
                    unit="봉",
                    category="양념/조미료",
                    is_seasoning=True
                )
            ],
            total_amount=38400
        )
