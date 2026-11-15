"""
스마트 재고 DB 및 유통기한 산출, 차감 로직 유닛 테스트
"""
import json
import os
import tempfile
import pytest

from src.db.expiry_calculator import ExpiryCalculator
from src.db.inventory_manager import InventoryManager
from src.ocr.schema import ReceiptParseResult, ReceiptItem


@pytest.fixture
def temp_db():
    """임시 테스트용 DB 파일 생성 및 정리"""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_updated": "2026-11-15T00:00:00", "items": []}, f)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_expiry_calculator():
    calc = ExpiryCalculator()

    # 1. 특정 식재료 유통기한
    today_str = "2026-11-15"
    expiry_pork = calc.calculate_expiry_date("삼겹살", "육류", today_str)
    assert expiry_pork == "2026-11-20"

    # 2. 기본 양념 판별
    assert calc.is_seasoning("진간장") is True
    assert calc.is_seasoning("고춧가루") is True
    assert calc.is_seasoning("삼겹살") is False
    assert calc.is_seasoning("양파") is False

    # 3. D-day 계산
    assert calc.calculate_days_left("2026-11-18", "2026-11-15") == 3
    assert calc.calculate_days_left("2026-11-15", "2026-11-15") == 0
    assert calc.calculate_days_left("2026-11-10", "2026-11-15") == -5


def test_inventory_add_and_deduct(temp_db):
    manager = InventoryManager(db_path=temp_db)

    receipt = ReceiptParseResult(
        store_name="테스트 마트",
        purchase_date="2026-11-15",
        items=[
            ReceiptItem(
                name="삼겹살", quantity=2.0, unit="팩",
                category="육류", is_seasoning=False
            ),
            ReceiptItem(
                name="두부", quantity=2.0, unit="모",
                category="두부", is_seasoning=False
            ),
            ReceiptItem(
                name="진간장", quantity=1.0, unit="병",
                category="양념/조미료", is_seasoning=True
            ),
        ]
    )

    manager.add_items_from_receipt(receipt, reference_date="2026-11-15")
    items = manager.load_inventory(reference_date="2026-11-15")
    assert len(items) == 3

    # 진간장은 기본 양념이므로 차감에서 제외되어야 함
    dish_req = {"삼겹살": 1.0, "두부": 1.0, "진간장": 1.0}
    result = manager.deduct_for_dish(
        "돼지고기 김치찌개", dish_req, reference_date="2026-11-15"
    )

    assert len(result["deducted_items"]) == 2
    assert any(d["name"] == "삼겹살" for d in result["deducted_items"])
    assert any(d["name"] == "두부" for d in result["deducted_items"])

    assert len(result["skipped_seasonings"]) == 1
    assert result["skipped_seasonings"][0]["name"] == "진간장"

    updated_items = manager.load_inventory(reference_date="2026-11-15")
    pork = next(i for i in updated_items if i["name"] == "삼겹살")
    assert pork["quantity"] == 1.0

    soy_sauce = next(i for i in updated_items if i["name"] == "진간장")
    assert soy_sauce["quantity"] == 1.0


def test_get_expiring_items(temp_db):
    manager = InventoryManager(db_path=temp_db)

    receipt = ReceiptParseResult(
        store_name="테스트 마트",
        purchase_date="2026-11-15",
        items=[
            ReceiptItem(
                name="닭가슴살", quantity=1.0, unit="팩",
                category="닭고기", is_seasoning=False
            ),
            ReceiptItem(
                name="양파", quantity=1.0, unit="망",
                category="채소", is_seasoning=False
            ),
        ]
    )
    manager.add_items_from_receipt(receipt, reference_date="2026-11-15")

    # 닭가슴살은 3일 보관이므로 11-18 만료 -> D-3 임박
    expiring = manager.get_expiring_items(days=3, reference_date="2026-11-15")
    names = [i["name"] for i in expiring]
    assert "닭가슴살" in names
    assert "양파" not in names
