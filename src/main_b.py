"""
팀원 B (OCR & 스마트 재고 DB) 메인 실행 및 테스트 CLI 스크립트
K-Refriger: 영수증 스캔 입고, 유통기한 자동 산출, 요리 차감(기본 양념 제외)
"""
import os
import sys
import argparse
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ocr.parser import ReceiptParser
from src.db.inventory_manager import InventoryManager
from src.db.expiry_calculator import ExpiryCalculator


def print_banner():
    print("=" * 65)
    print(" 🥬 K-Refriger: 팀원 B 파트 (Gemini OCR & 스마트 재고 DB 시스템) 🥩")
    print("=" * 65)


def display_inventory(items, title="현재 냉장고 재고 목록"):
    print(f"\n📦 [{title}] (총 {len(items)}개 품목)")
    if not items:
        print("  (냉장고가 비어 있습니다.)")
        return

    print("-" * 75)
    print(f"{'식재료명':<12} {'수량':<8} {'카테고리':<10} {'구매일':<12} {'유통기한':<12} {'상태(D-Day)':<10}")
    print("-" * 75)
    for it in items:
        days = it.get("days_left", 0)
        if days < 0:
            status = f"🚨 만료({abs(days)}일 지남)"
        elif days == 0:
            status = "🔥 D-DAY (오늘 만료)"
        elif days <= 3:
            status = f"⚠️ D-{days} (임박)"
        else:
            status = f"✅ D-{days}"

        seasoning_tag = " [양념]" if it.get("is_seasoning") else ""
        name_display = f"{it['name']}{seasoning_tag}"
        qty_display = f"{it['quantity']} {it.get('unit', '')}"

        print(f"{name_display:<12} {qty_display:<8} {it.get('category',''):<10} {it.get('purchase_date',''):<12} {it.get('expiry_date',''):<12} {status:<10}")
    print("-" * 75)


def run_demo():
    print_banner()
    print("🚀 [팀원 B 전체 파이프라인 데모 시뮬레이션 시작]\n")

    manager = InventoryManager()
    parser = ReceiptParser()

    print("Step 1. 영수증 사진 스캔 및 자동 OCR 파싱 시뮬레이션")
    # 샘플 이미지 경로 또는 mock 사용
    sample_img = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "receipts", "sample_receipt.jpg"))
    if not os.path.exists(sample_img):
        # 데모용 placeholder 생성
        with open(sample_img, "wb") as f:
            f.write(b"SAMPLE RECEIPT IMAGE PLACEHOLDER")

    receipt = parser.parse_receipt_image(sample_img, use_mock_if_no_key=True)
    print(f"  🏪 상호명: {receipt.store_name}")
    print(f"  📅 구매일자: {receipt.purchase_date}")
    print(f"  🧾 파싱된 품목 수: {len(receipt.items)}개")
    for idx, item in enumerate(receipt.items, 1):
        season_tag = "(기본 양념)" if item.is_seasoning else "(일반 식재료)"
        print(f"    {idx}. {item.name} ({item.quantity}{item.unit}) - {item.category} {season_tag}")

    print("\nStep 2. 스마트 재고 DB (inventory.json) 입고 및 유통기한 산출")
    added = manager.add_items_from_receipt(receipt)
    print(f"  ✨ {len(added)}개 품목이 성공적으로 등록되었습니다.")

    items = manager.load_inventory()
    display_inventory(items, "영수증 입고 후 냉장고 재고 현황")

    print("\nStep 3. D-3 유통기한 임박 품목 조회 (팀원 D 알림 및 팀원 C 식단 연계용)")
    expiring = manager.get_expiring_items(days=3)
    if expiring:
        print(f"  ⚠️ 유통기한 임박(D-3 이내) 품목 {len(expiring)}개 발견:")
        for exp in expiring:
            print(f"     - {exp['name']}: 잔여 {exp['quantity']}{exp.get('unit','')} (만료일: {exp['expiry_date']}, D-{exp['days_left']})")
    else:
        print("  ✅ D-3 이내 임박한 품목이 없습니다.")

    print("\nStep 4. 요리 실행 및 재고 차감 테스트 (PPT 핵심 기능: 기본 양념 제외 차감)")
    dish = "돼지고기 김치찌개"
    cook_ingredients = {
        "삼겹살": 1.0,      # 일반 식재료 -> 차감 대상
        "두부": 1.0,        # 일반 식재료 -> 차감 대상
        "대파": 1.0,        # 일반 식재료 -> 차감 대상
        "진간장": 1.0,      # 기본 양념 -> 차감 제외!
        "고춧가루": 1.0     # 기본 양념 -> 차감 제외!
    }
    print(f"  🍳 요리 시작: [{dish}]")
    print(f"  필요 재료: {list(cook_ingredients.keys())}")

    result = manager.deduct_for_dish(dish, cook_ingredients)
    print("\n  [차감 실행 결과 보고서]")
    print(f"  - 요리명: {result['dish_name']}")
    for d in result["deducted_items"]:
        print(f"    📉 [재고 차감] {d['name']} {d['deducted_quantity']} 차감 완료")
    for s in result["skipped_seasonings"]:
        print(f"    🛡️ [차감 제외] {s['name']}: {s['reason']}")
    for i in result["insufficient_items"]:
        print(f"    ❌ [재고 부족] {i['name']}: {i['message']}")

    final_items = manager.load_inventory()
    display_inventory(final_items, "요리 후 최종 냉장고 잔여 재고")

    print("\n🎉 [팀원 B 파트 시뮬레이션이 성공적으로 완료되었습니다!]")


def main():
    parser = argparse.ArgumentParser(description="K-Refriger 스마트 냉장고 OCR & 재고 관리 시스템 (팀원 B)")
    parser.add_argument("--demo", action="store_true", help="전체 파이프라인 데모 실행")
    parser.add_argument("--list", action="store_true", help="현재 재고 목록 조회")
    parser.add_argument("--scan", type=str, help="영수증 이미지 파일 경로를 입력받아 OCR 및 입고 처리")
    parser.add_argument("--cook", type=str, help="요리명 (예: '돼지고기 김치찌개')")
    parser.add_argument("--ingredients", type=str, help="사용할 재료 목록 (형식: '재료명:수량,재료명:수량' 예: '삼겹살:1,양파:1,간장:1')")
    parser.add_argument("--check-d3", action="store_true", help="D-3 이내 유통기한 임박 식재료 조회")
    parser.add_argument("--available", action="store_true", help="현재 요리 가능한 식재료 명칭 목록 조회 (팀원 C 연계)")

    args = parser.parse_args()
    manager = InventoryManager()

    if args.demo or len(sys.argv) == 1:
        run_demo()
        return

    if args.list:
        items = manager.load_inventory()
        display_inventory(items)

    elif args.scan:
        print_banner()
        receipt_parser = ReceiptParser()
        print(f"📸 영수증 스캔 중: {args.scan}")
        receipt = receipt_parser.parse_receipt_image(args.scan, use_mock_if_no_key=True)
        print(f"✅ 파싱 완료: {receipt.store_name} ({receipt.purchase_date})")
        added = manager.add_items_from_receipt(receipt)
        print(f"✨ {len(added)}개 품목이 재고 DB에 입고되었습니다.")
        display_inventory(manager.load_inventory())

    elif args.cook:
        if not args.ingredients:
            print("❌ 오류: --ingredients 인자가 필요합니다. (예: --ingredients '삼겹살:1,진간장:1')")
            return
        # 파싱
        ing_dict = {}
        for pair in args.ingredients.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                ing_dict[k.strip()] = float(v.strip())
            else:
                ing_dict[pair.strip()] = 1.0

        print_banner()
        print(f"🍳 요리 실행: {args.cook}")
        res = manager.deduct_for_dish(args.cook, ing_dict)
        print("결과:")
        for d in res["deducted_items"]:
            print(f"  📉 [차감] {d['name']} {d['deducted_quantity']}")
        for s in res["skipped_seasonings"]:
            print(f"  🛡️ [보존] {s['name']} ({s['reason']})")
        for i in res["insufficient_items"]:
            print(f"  ⚠️ [부족] {i['name']} ({i['message']})")

    elif args.check_d3:
        expiring = manager.get_expiring_items(days=3)
        print(f"⚠️ [D-3 임박 식재료] ({len(expiring)}개)")
        for item in expiring:
            print(f"  - {item['name']}: {item['quantity']}{item.get('unit','')} (만료일: {item['expiry_date']}, D-{item['days_left']})")

    elif args.available:
        avail = manager.get_available_ingredients()
        print(f"🥦 [가용 식재료 목록 (팀원 C 연계용)]")
        print(", ".join(avail))


if __name__ == "__main__":
    main()

