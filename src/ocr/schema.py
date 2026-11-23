"""
식재료 및 영수증 데이터 스키마 정의 (Pydantic v2)
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ReceiptItem(BaseModel):
    """영수증에서 추출된 개별 품목 (식재료 또는 간식)"""
    name: str = Field(
        description="정제된 대표 명칭 (예: 삼겹살, 양파, 우유, 콜라, 초코파이)"
    )
    raw_name: Optional[str] = Field(
        default=None, description="영수증에 기재된 원본 상품명"
    )
    quantity: float = Field(
        default=1.0, description="구매 수량 (기본값 1.0)"
    )
    unit: str = Field(
        default="개", description="단위 (예: 개, 팩, 봉, g, ml, 캔, 병 등)"
    )
    category: str = Field(
        default="기타",
        description="카테고리 (채소, 육류, 닭고기, 수산물, 유제품, 계란, "
                    "두부, 과일, 가공식품, 간식, 양념/조미료, 기타)"
    )
    is_seasoning: bool = Field(
        default=False,
        description="소금, 설탕, 간장 등 기본 양념/조미료 여부"
    )


class ReceiptParseResult(BaseModel):
    """Gemini Vision OCR 영수증 파싱 최종 결과 구조체"""
    store_name: Optional[str] = Field(
        default=None, description="마트 또는 편의점 상호명"
    )
    purchase_date: str = Field(
        description="구매 일자 (YYYY-MM-DD 형식). "
                    "영수증에 없거나 식별 불가능한 경우 오늘 날짜"
    )
    items: List[ReceiptItem] = Field(
        default_factory=list, description="인식된 식재료 및 간식 목록"
    )
    total_amount: Optional[int] = Field(
        default=None, description="총 결제 금액 (원)"
    )


class InventoryItem(BaseModel):
    """냉장고 재고 DB에 저장되는 품목"""
    id: str = Field(description="재고 항목 고유 식별자")
    name: str = Field(description="품목명")
    quantity: float = Field(description="현재 잔여 수량")
    unit: str = Field(description="단위")
    category: str = Field(description="카테고리")
    purchase_date: str = Field(description="입고/구매 일자 (YYYY-MM-DD)")
    expiry_date: str = Field(
        description="산출된 유통/소비기한 (YYYY-MM-DD)"
    )
    is_seasoning: bool = Field(
        default=False, description="기본 양념 여부"
    )
    days_left: Optional[int] = Field(
        default=None,
        description="현재 날짜 기준 남은 유통기한 일수 (D-day)"
    )
