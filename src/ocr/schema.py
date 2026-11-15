"""
식재료 및 영수증 데이터 스키마 정의 (Pydantic v2 호환 및 순수 Python Fallback 지원)
"""
import json
from typing import List, Optional, Any, Dict

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


if HAS_PYDANTIC:
    class ReceiptItem(BaseModel):
        """영수증에서 추출된 개별 식재료 항목"""
        name: str = Field(description="정제된 대표 식재료명 (예: 삼겹살, 양파, 우유)")
        raw_name: Optional[str] = Field(default=None, description="영수증에 기재된 원본 상품명")
        quantity: float = Field(default=1.0, description="구매 수량 (기본값 1.0)")
        unit: str = Field(default="개", description="단위 (예: 개, 팩, 봉, g, ml)")
        category: str = Field(
            default="기타",
            description="카테고리 (채소, 육류, 닭고기, 수산물, 유제품, 계란, 두부, 과일, 가공식품, 양념/조미료, 기타)"
        )
        is_seasoning: bool = Field(
            default=False,
            description="소금, 설탕, 간장 등 기본 양념/조미료 여부"
        )

    class ReceiptParseResult(BaseModel):
        """Gemini Vision OCR 영수증 파싱 최종 결과 구조체"""
        store_name: Optional[str] = Field(default=None, description="마트 또는 편의점 상호명")
        purchase_date: str = Field(
            description="구매 일자 (YYYY-MM-DD 형식). 영수증에 없거나 식별 불가능한 경우 오늘 날짜"
        )
        items: List[ReceiptItem] = Field(default_factory=list, description="인식된 식재료 목록")
        total_amount: Optional[int] = Field(default=None, description="총 결제 금액 (원)")

    class InventoryItem(BaseModel):
        """냉장고 재고 DB에 저장되는 식재료 항목"""
        id: str = Field(description="재고 항목 고유 식별자")
        name: str = Field(description="식재료명")
        quantity: float = Field(description="현재 잔여 수량")
        unit: str = Field(description="단위")
        category: str = Field(description="카테고리")
        purchase_date: str = Field(description="입고/구매 일자 (YYYY-MM-DD)")
        expiry_date: str = Field(description="산출된 유통/소비기한 (YYYY-MM-DD)")
        is_seasoning: bool = Field(default=False, description="기본 양념 여부")
        days_left: Optional[int] = Field(default=None, description="현재 날짜 기준 남은 유통기한 일수 (D-day)")

else:
    # Pydantic 미설치 환경에서도 테스트 및 실행이 가능하도록 순수 Python 클래스 제공
    class ReceiptItem:
        def __init__(
            self,
            name: str,
            raw_name: Optional[str] = None,
            quantity: float = 1.0,
            unit: str = "개",
            category: str = "기타",
            is_seasoning: bool = False
        ):
            self.name = name
            self.raw_name = raw_name
            self.quantity = float(quantity)
            self.unit = unit
            self.category = category
            self.is_seasoning = is_seasoning

        def to_dict(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "raw_name": self.raw_name,
                "quantity": self.quantity,
                "unit": self.unit,
                "category": self.category,
                "is_seasoning": self.is_seasoning
            }

    class ReceiptParseResult:
        def __init__(
            self,
            purchase_date: str,
            store_name: Optional[str] = None,
            items: Optional[List[ReceiptItem]] = None,
            total_amount: Optional[int] = None
        ):
            self.purchase_date = purchase_date
            self.store_name = store_name
            self.items = items or []
            self.total_amount = total_amount

        @classmethod
        def model_validate_json(cls, json_str: str) -> "ReceiptParseResult":
            data = json.loads(json_str)
            items = []
            for it in data.get("items", []):
                items.append(ReceiptItem(
                    name=it.get("name", ""),
                    raw_name=it.get("raw_name"),
                    quantity=float(it.get("quantity", 1.0)),
                    unit=it.get("unit", "개"),
                    category=it.get("category", "기타"),
                    is_seasoning=it.get("is_seasoning", False)
                ))
            return cls(
                purchase_date=data.get("purchase_date", ""),
                store_name=data.get("store_name"),
                items=items,
                total_amount=data.get("total_amount")
            )

        @classmethod
        def model_json_schema(cls) -> Dict[str, Any]:
            return {
                "type": "object",
                "properties": {
                    "store_name": {"type": "string"},
                    "purchase_date": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "raw_name": {"type": "string"},
                                "quantity": {"type": "number"},
                                "unit": {"type": "string"},
                                "category": {"type": "string"},
                                "is_seasoning": {"type": "boolean"}
                            },
                            "required": ["name", "quantity", "unit", "category", "is_seasoning"]
                        }
                    },
                    "total_amount": {"type": "integer"}
                },
                "required": ["purchase_date", "items"]
            }

    class InventoryItem:
        def __init__(
            self,
            id: str,
            name: str,
            quantity: float,
            unit: str,
            category: str,
            purchase_date: str,
            expiry_date: str,
            is_seasoning: bool = False,
            days_left: Optional[int] = None
        ):
            self.id = id
            self.name = name
            self.quantity = quantity
            self.unit = unit
            self.category = category
            self.purchase_date = purchase_date
            self.expiry_date = expiry_date
            self.is_seasoning = is_seasoning
            self.days_left = days_left
