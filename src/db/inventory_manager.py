"""
스마트 냉장고 재고 관리자 (JSON 기반 로컬 DB)
- inventory.json 로드 및 저장
- 영수증 품목 자동 입고 및 유통기한 산출
- 요리 실행 시 재고 자동 차감 (기본 양념 제외)
- D-3 유통기한 임박 식재료 조회
"""
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from .expiry_calculator import ExpiryCalculator
from ..ocr.schema import ReceiptParseResult


class InventoryManager:
    """스마트 냉장고 재고 DB 관리 엔진"""

    _DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    DEFAULT_DB_PATH = os.path.abspath(
        os.path.join(_DATA_DIR, "inventory.json")
    )

    def __init__(
        self,
        db_path: Optional[str] = None,
        calculator: Optional[ExpiryCalculator] = None
    ):
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.calculator = calculator or ExpiryCalculator()
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """DB 디렉토리 및 inventory.json 파일 존재 보장"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_updated": datetime.now().isoformat(),
                        "items": []
                    },
                    f,
                    ensure_ascii=False,
                    indent=2
                )

    def load_inventory(
        self, reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """inventory.json 로드 및 남은 유통기한(days_left) 실시간 갱신"""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {"last_updated": datetime.now().isoformat(), "items": []}

        items = data.get("items", [])
        for item in items:
            expiry_date = item.get("expiry_date", "")
            if expiry_date:
                item["days_left"] = self.calculator.calculate_days_left(
                    expiry_date, reference_date
                )
            else:
                item["days_left"] = 999

        return items

    def save_inventory(self, items: List[Dict[str, Any]]):
        """변경된 재고 목록을 inventory.json에 저장"""
        data = {
            "last_updated": datetime.now().isoformat(),
            "items": items
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_items_from_receipt(
        self,
        receipt: ReceiptParseResult,
        reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """OCR 파싱된 영수증 결과를 재고 DB에 입고"""
        current_items = self.load_inventory(reference_date)
        purchase_date = (
            receipt.purchase_date or datetime.now().strftime("%Y-%m-%d")
        )
        newly_added = []

        for item in receipt.items:
            expiry_date = self.calculator.calculate_expiry_date(
                item_name=item.name,
                category=item.category,
                purchase_date_str=purchase_date
            )

            is_seasoning = (
                item.is_seasoning or self.calculator.is_seasoning(item.name)
            )

            merged = False
            for existing in current_items:
                if existing["name"] == item.name:
                    if existing["expiry_date"] == expiry_date:
                        existing["quantity"] += float(item.quantity)
                        existing["days_left"] = (
                            self.calculator.calculate_days_left(
                                expiry_date, reference_date
                            )
                        )
                        newly_added.append(existing)
                        merged = True
                        break

            if not merged:
                now_str = datetime.now().strftime('%Y%m%d%H%M%S')
                item_id = f"item_{now_str}_{uuid.uuid4().hex[:6]}"
                days_left = self.calculator.calculate_days_left(
                    expiry_date, reference_date
                )
                new_item = {
                    "id": item_id,
                    "name": item.name,
                    "quantity": float(item.quantity),
                    "unit": item.unit or "개",
                    "category": item.category or "기타",
                    "purchase_date": purchase_date,
                    "expiry_date": expiry_date,
                    "is_seasoning": is_seasoning,
                    "days_left": days_left
                }
                current_items.append(new_item)
                newly_added.append(new_item)

        self.save_inventory(current_items)
        return newly_added

    def deduct_for_dish(
        self,
        dish_name: str,
        ingredients: Union[List[Dict[str, Any]], Dict[str, float]],
        reference_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        요리 실행 시 재고 자동 차감 로직 (기본 양념 제외)
        """
        current_items = self.load_inventory(reference_date)

        target_ingredients = []
        if isinstance(ingredients, dict):
            for name, qty in ingredients.items():
                target_ingredients.append(
                    {"name": name, "quantity": float(qty)}
                )
        elif isinstance(ingredients, list):
            for ing in ingredients:
                target_ingredients.append({
                    "name": ing.get("name", ""),
                    "quantity": float(ing.get("quantity", 1.0))
                })

        deducted_records = []
        skipped_seasonings = []
        insufficient_warnings = []

        for req in target_ingredients:
            req_name = req["name"].strip()
            req_qty = float(req.get("quantity", 1.0))

            if self.calculator.is_seasoning(req_name):
                skipped_seasonings.append({
                    "name": req_name,
                    "reason": "기본 양념/조미료 항목이므로 "
                              "재고 차감에서 제외되었습니다."
                })
                continue

            matched_items = [
                item for item in current_items
                if item["name"] == req_name and item["quantity"] > 0
            ]
            matched_items.sort(key=lambda x: x.get("days_left", 999))

            remaining_to_deduct = req_qty
            total_deducted_for_this = 0.0

            for item in matched_items:
                if remaining_to_deduct <= 0:
                    break

                if item["quantity"] >= remaining_to_deduct:
                    item["quantity"] -= remaining_to_deduct
                    total_deducted_for_this += remaining_to_deduct
                    remaining_to_deduct = 0.0
                else:
                    total_deducted_for_this += item["quantity"]
                    remaining_to_deduct -= item["quantity"]
                    item["quantity"] = 0.0

            if total_deducted_for_this > 0:
                deducted_records.append({
                    "name": req_name,
                    "deducted_quantity": total_deducted_for_this
                })

            if remaining_to_deduct > 0:
                insufficient_warnings.append({
                    "name": req_name,
                    "requested": req_qty,
                    "shortage": remaining_to_deduct,
                    "message": f"재고가 부족합니다 (부족 수량: {remaining_to_deduct})"
                })

        active_items = [
            item for item in current_items if item["quantity"] > 0
        ]
        self.save_inventory(active_items)

        return {
            "dish_name": dish_name,
            "deducted_items": deducted_records,
            "skipped_seasonings": skipped_seasonings,
            "insufficient_items": insufficient_warnings,
            "remaining_total_items": len(active_items)
        }

    def get_expiring_items(
        self, days: int = 3, reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """D-day 기준 유통기한 임박 품목 조회 (D-3)"""
        items = self.load_inventory(reference_date)
        expiring = []
        for item in items:
            if item.get("is_seasoning", False):
                continue
            days_left = item.get("days_left", 999)
            if 0 <= days_left <= days:
                expiring.append(item)
        expiring.sort(key=lambda x: x.get("days_left", 999))
        return expiring

    def get_expired_items(
        self, reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """유통기한 지난 폐기 대상 품목 조회"""
        items = self.load_inventory(reference_date)
        return [item for item in items if item.get("days_left", 0) < 0]

    def get_available_ingredients(
        self, reference_date: Optional[str] = None
    ) -> List[str]:
        """추천 가능한 식재료 명칭 목록 (팀원 C 연계)"""
        items = self.load_inventory(reference_date)
        available = set()
        for item in items:
            if not item.get("is_seasoning", False):
                qty = item.get("quantity", 0)
                days_left = item.get("days_left", 0)
                if qty > 0 and days_left >= 0:
                    available.add(item["name"])
        return sorted(list(available))
