"""
조장(팀원 A) 전체 통합 오케스트레이션 스크립트 (main.py)
- 팀원 B(OCR & 재고 DB), 팀원 C(AI 식단 엔진), 팀원 D(텔레그램 알림) 모듈을 통합 지휘
- GitHub Actions(Cron / workflow_dispatch) 환경 변수 및 로컬 CLI 인자를 모두 지원
"""
import argparse
import json
import os
import sys
import google.generativeai as genai

# 팀원 B와 팀원 D가 구현한 실제 모듈 임포트
from src.ocr.parser import ReceiptParser
from src.db.inventory_manager import InventoryManager
from src.notify import notify_expiry
from src.notify.telegram import TelegramBot


def generate_ai_recipes_from_inventory(available_ingredients: list[str], expiring_items: list[dict]) -> list[dict]:
    """
    [팀원 C 로직 통합]
    기본 양념이 제외된 보유 식재료(available_ingredients)와 유통기한 임박 품목을 바탕으로
    Gemini AI를 호출해 맞춤형 레시피 카드 JSON 리스트를 생성합니다.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("⚠️ GEMINI_API_KEY가 설정되지 않아 기본 추천 레시피를 반환합니다.")
        return []

    if not available_ingredients:
        print("⚠️ 기본 양념 외에 사용 가능한 식재료가 없어 레시피 생성을 건너뜁니다.")
        return []

    genai.configure(api_key=api_key)
    expiring_names = [item["name"] for item in expiring_items]

    prompt = f"""
    당신은 스마트 냉장고 'K-Refriger<Action>'의 AI 셰프입니다.

    [현재 냉장고 보유 식재료 (기본 양념 제외됨)]
    {', '.join(available_ingredients)}

    [유통기한 임박(D-3 이내) 우선 소비 권장 재료]
    {', '.join(expiring_names) if expiring_names else '없음'}

    위 보유 식재료와 집에 있는 기본 양념(소금, 간장, 설탕, 마늘, 고추장 등)을 활용해
    만들 수 있는 최적의 요리 레시피 2가지를 추천해 주세요. 특히 유통기한 임박 재료를 우선 활용하세요.

    반드시 아래 JSON 배열 형식으로만 응답하세요:
    [
      {{
        "title": "요리 이름",
        "description": "요리 한 줄 소개 및 추천 이유",
        "ingredients": ["재료1", "재료2"],
        "steps": ["1. 조리 과정 1", "2. 조리 과정 2"]
      }}
    ]
    """

    try:
        model = genai.GenerativeModel("gemini-3.8-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        recipes = json.loads(response.text)
        return recipes if isinstance(recipes, list) else [recipes]
    except Exception as e:
        print(f"❌ Gemini AI 레시피 생성 중 오류 발생: {e}")
        return []


def run_daily_check(days: int = 3, dry_run: bool = False):
    """[모드 1: daily_check] D-3 유통기한 체크 -> AI 맞춤형 레시피 생성 -> 텔레그램 알림 발송"""
    print("=" * 60)
    print("🔄 [Pipeline 1] 일일 재고 점검 및 AI 식단 추천 파이프라인 시작")
    print("=" * 60)

    manager = InventoryManager()

    # 1. 팀원 B 모듈: D-3 임박 식재료 및 기본 양념 제외 가용 식재료 조회
    expiring = manager.get_expiring_items(days=days)
    available = manager.get_available_ingredients()
    print(f"📦 가용 식재료(양념 제외): {available}")
    print(f"⚠️ D-{days} 임박 품목 수: {len(expiring)}개")

    # 2. 팀원 C 모듈: 가용 식재료 기반 Gemini AI 레시피 생성
    recipes = generate_ai_recipes_from_inventory(available, expiring)
    if recipes:
        with open("recipes.json", "w", encoding="utf-8") as f:
            json.dump({"recipes": recipes}, f, ensure_ascii=False, indent=2)
        print(f"✨ AI 레시피 {len(recipes)}건 생성 완료 (recipes.json 저장)")

    # 3. 팀원 D 모듈: 유통기한 임박 알림 + 레시피 카드 텔레그램 전송
    notify_expiry(
        days=days,
        recipes=recipes,
        only_if_any=False,
        dry_run=dry_run,
    )
    print("✅ 일일 점검 및 알림 전송 파이프라인 완료!")


def run_cook_dish(dish_name: str, ingredients_str: str, dry_run: bool = False):
    """[모드 2: cook_dish] 요리 실행 -> 기본 양념 제외 재고 차감 -> 결과 텔레그램 보고"""
    print("=" * 60)
    print(f"🍳 [Pipeline 2] 요리 실행 및 스마트 재고 차감 파이프라인: [{dish_name}]")
    print("=" * 60)

    if not dish_name or not ingredients_str:
        raise ValueError("요리 이름(dish_name)과 사용 재료(ingredients)가 모두 필요합니다.")

    # '삼겹살:1,두부:1,진간장:1' 형태의 문자열을 딕셔너리로 파싱
    ing_dict = {}
    for pair in ingredients_str.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            ing_dict[k.strip()] = float(v.strip())
        elif pair.strip():
            ing_dict[pair.strip()] = 1.0

    # 1. 팀원 B 모듈: 재고 차감 (기본 양념은 자동 스킵)
    manager = InventoryManager()
    res = manager.deduct_for_dish(dish_name, ing_dict)

    # 2. 결과 메시지 조립 후 팀원 D 텔레그램 봇으로 전송
    lines = ["🍳 *[요리 완료 & 재고 자동 업데이트]*", f"• 메뉴: *{res['dish_name']}*"]
    if res["deducted_items"]:
        deducted_txt = ", ".join(f"{d['name']}(-{d['deducted_quantity']})" for d in res["deducted_items"])
        lines.append(f"• 📉 차감된 재고: {deducted_txt}")
    if res["skipped_seasonings"]:
        skipped_txt = ", ".join(s["name"] for s in res["skipped_seasonings"])
        lines.append(f"• 🛡️ 기본 양념 보존: {skipped_txt}")
    if res["insufficient_items"]:
        insuff_txt = ", ".join(i["name"] for i in res["insufficient_items"])
        lines.append(f"• ⚠️ 재고 부족 알림: {insuff_txt}")

    summary_msg = "\n".join(lines)
    print(summary_msg)
    TelegramBot(dry_run=dry_run).send_message(summary_msg)
    print("✅ 요리 차감 및 알림 전송 완료!")


def run_scan_receipt(receipt_path: str, dry_run: bool = False):
    """[모드 3: scan_receipt] 영수증 OCR 스캔 -> 재고 DB 자동 입고 -> 입고 내역 텔레그램 전송"""
    print("=" * 60)
    print(f"🧾 [Pipeline 3] 영수증 OCR 스캔 및 자동 입고 파이프라인: {receipt_path}")
    print("=" * 60)

    parser = ReceiptParser()
    manager = InventoryManager()

    # 1. 팀원 B 모듈: 영수증 파싱 및 재고 DB 등록
    receipt = parser.parse_receipt_image(receipt_path, use_mock_if_no_key=True)
    added = manager.add_items_from_receipt(receipt)

    # 2. 입고 결과 텔레그램 전송
    lines = [
        "🧾 *[영수증 자동 입고 완료]*",
        f"• 구매처: {receipt.store_name} ({receipt.purchase_date})",
        f"• 등록 품목 ({len(added)}개): " + ", ".join(f"{item['name']}({item['quantity']})" for item in added),
    ]
    summary_msg = "\n".join(lines)
    print(summary_msg)
    TelegramBot(dry_run=dry_run).send_message(summary_msg)
    print("✅ 영수증 스캔 입고 및 알림 전송 완료!")


def main():
    # 윈도우 콘솔 UTF-8 출력 보장
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="K-Refriger<Action> 통합 실행 오케스트레이터")
    parser.add_argument(
        "--mode",
        type=str,
        default=os.environ.get("ACTION_MODE", "daily_check"),
        choices=["daily_check", "cook_dish", "scan_receipt"],
        help="실행 모드 선택",
    )
    parser.add_argument("--dish", type=str, default=os.environ.get("DISH_NAME", ""), help="요리 이름")
    parser.add_argument("--ingredients", type=str, default=os.environ.get("INGREDIENTS", ""), help="사용 재료 (예: 삼겹살:1,두부:1)")
    parser.add_argument("--receipt", type=str, default=os.environ.get("RECEIPT_PATH", "data/receipts/sample_receipt.jpg"), help="영수증 이미지 경로")
    parser.add_argument("--dry-run", action="store_true", help="텔레그램 실제 전송 없이 콘솔 출력만 테스트")

    args = parser.parse_args()

    if args.mode == "daily_check":
        run_daily_check(dry_run=args.dry_run)
    elif args.mode == "cook_dish":
        run_cook_dish(args.dish, args.ingredients, dry_run=args.dry_run)
    elif args.mode == "scan_receipt":
        run_scan_receipt(args.receipt, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
