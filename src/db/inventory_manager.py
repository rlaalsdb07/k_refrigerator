"""
스마트 냉장고 재고 관리자 (JSON 기반 로컬 DB)
- inventory.json 로드 및 저장
- 영수증 품목 자동 입고 및 유통기한 산출
- 요리 실행 시 재고 자동 차감 (기본 양념 제외)
- 식재료(요리용)와 간식/음료 분리 관리
- 비식품(이상한 것들) 100% 쳐내기(제외)
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
        """inventory.json 로드 및 데이터 정제(간식 분류, 비식품 쳐내기, 유통기한 갱신)"""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {"last_updated": datetime.now().isoformat(), "items": []}

        items = data.get("items", [])
        cleaned_items = []

        for item in items:
            name = item.get("name", "")
            raw = item.get("raw_name", "")

            # 1. 이상한 것들 (비식품/생활잡화) 쳐내기
            if self.calculator.is_non_food(name, raw):
                continue

            # 2. 간식류 자동 재분류
            if self.calculator.is_snack(name, item.get("category", "")):
                item["category"] = "간식"
                item["is_seasoning"] = False
            elif self.calculator.is_seasoning(name):
                item["is_seasoning"] = True

            # 3. 유통기한 남은 일수 계산
            expiry_date = item.get("expiry_date", "")
            if expiry_date:
                item["days_left"] = self.calculator.calculate_days_left(
                    expiry_date, reference_date
                )
            else:
                item["days_left"] = 999

            cleaned_items.append(item)

        return cleaned_items

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
            # 1. 이상한 것들 (비식품 잡화) 쳐내기
            if self.calculator.is_non_food(item.name, item.raw_name or ""):
                print(f"🚫 [입고 쳐내기] 비식품 제외: {item.name}")
                continue

            # 2. 간식류 및 양념 여부 자동 보정
            if self.calculator.is_snack(item.name, item.category):
                item.category = "간식"
                is_seasoning = False
            elif item.is_seasoning or self.calculator.is_seasoning(item.name):
                is_seasoning = True
            else:
                is_seasoning = False

            expiry_date = self.calculator.calculate_expiry_date(
                item_name=item.name,
                category=item.category,
                purchase_date_str=purchase_date
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
        """
        추천 가능한 요리용 식재료 명칭 목록 (간식 및 기본 양념 제외, 팀원 C 연계)
        - 식재료 파트만 있도록 간식(과자, 음료, 빵, 주류 등)은 엄격히 제외
        """
        items = self.load_inventory(reference_date)
        available = set()
        for item in items:
            name = item.get("name", "")
            cat = item.get("category", "")

            # 기본 양념 제외
            if item.get("is_seasoning", False):
                continue
            # 간식/음료 제외 (요리 레시피 식재료에서 배제)
            if cat == "간식" or self.calculator.is_snack(name, cat):
                continue
            # 비식품 제외
            if self.calculator.is_non_food(name, item.get("raw_name", "")):
                continue

            qty = item.get("quantity", 0)
            days_left = item.get("days_left", 0)
            if qty > 0 and days_left >= 0:
                available.add(name)

        return sorted(list(available))

    def get_cooking_ingredients(
        self, reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """순수 요리용 식재료 목록 조회 (간식 및 양념 제외)"""
        items = self.load_inventory(reference_date)
        result = []
        for it in items:
            name = it.get("name", "")
            cat = it.get("category", "")
            if it.get("is_seasoning", False):
                continue
            if cat == "간식" or self.calculator.is_snack(name, cat):
                continue
            if self.calculator.is_non_food(name, it.get("raw_name", "")):
                continue
            result.append(it)
        return result

    def get_snack_items(
        self, reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """간식 파트 품목 목록 조회 (과자, 스낵, 빵, 음료, 주류 등)"""
        items = self.load_inventory(reference_date)
        result = []
        for it in items:
            name = it.get("name", "")
            cat = it.get("category", "")
            if cat == "간식" or self.calculator.is_snack(name, cat):
                result.append(it)
        return result

    def get_seasoning_items(
        self, reference_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """기본 양념/조미료 목록 조회"""
        items = self.load_inventory(reference_date)
        return [it for it in items if it.get("is_seasoning", False)]
