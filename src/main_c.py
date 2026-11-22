"""
팀원 C (AI 식단 엔진) 메인 실행 및 테스트 CLI 스크립트
K-Refriger: 잔여 식재료 및 D-3 임박 식재료 기반 맞춤형 레시피 생성, cuisine 확장

사용 예:
  python src/main_c.py --demo                      # 전체 추천 데모 (재고 DB 연동)
  python src/main_c.py --cuisine 양식               # 특정 요리 스타일 지정
  python src/main_c.py --ingredients "두부,대파"     # 직접 식재료 입력
  python src/main_c.py --demo --save data/recipes.json
  python src/main_c.py --demo --notify --dry-run   # 생성 후 텔레그램 알림 테스트
"""
import argparse
import json
import os
import sys

# 프로젝트 루트를 sys.path에 추가
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.db.inventory_manager import InventoryManager  # noqa: E402
from src.recipe.generator import RecipeGenerator  # noqa: E402
from src.recipe.prompts import SUPPORTED_CUISINES  # noqa: E402
from src.notify import notify_recipes  # noqa: E402


def print_banner():
    print("=" * 65)
    print(" 🍳 K-Refriger: 팀원 C 파트 (Gemini AI 맞춤형 식단 엔진) 🥗")
    print("=" * 65)


def display_recipes(recipes: list[dict], title: str = "추천 AI 레시피 목록"):
    print(f"\n✨ [{title}] (총 {len(recipes)}가지 제안)")
    if not recipes:
        print("  (추천 가능한 레시피가 없습니다.)")
        return

    for idx, r in enumerate(recipes, 1):
        print("\n" + "=" * 65)
        print(f" 🍳 [레시피 #{idx}] {r.get('title', '추천 요리')}")
        print("=" * 65)
        print(f"  • 스타일: {r.get('cuisine', '기타')} | 조리시간: {r.get('time', '미정')} | 난이도: {r.get('difficulty', '보통')}")
        if r.get("description"):
            print(f"  • 소  개: {r.get('description')}")
        if r.get("uses_expiring"):
            print(f"  • ♻️ 임박 재료 우선 활용: {', '.join(r.get('uses_expiring'))}")
        
        print("\n  [필요 식재료 및 양념]")
        for ing in r.get("ingredients", []):
            print(f"    - {ing}")

        print("\n  [조리 순서]")
        for step in r.get("steps", []):
            print(f"    {step}")

        if r.get("tips"):
            print(f"\n  💡 [셰프의 팁] {r.get('tips')}")
    print("\n" + "=" * 65)


def run_demo(cuisine: str = "한식", count: int = 2, save_path: str = None, notify: bool = False, dry_run: bool = False):
    print_banner()
    print("🚀 [팀원 C AI 식단 엔진 데모 시뮬레이션 시작]\n")

    manager = InventoryManager()

    print("Step 1. 스마트 재고 DB (inventory.json)에서 가용 식재료 및 임박 품목 조회")
    available = manager.get_available_ingredients()
    expiring = manager.get_expiring_items(days=3)

    print(f"  📦 추천용 가용 식재료 (기본 양념 제외): {', '.join(available) if available else '없음'}")
    print(f"  ⚠️ D-3 임박 식재료: {len(expiring)}개 품목 감지")
    for exp in expiring:
        print(f"     - {exp['name']} (잔여: {exp.get('quantity')}{exp.get('unit','')}, D-{exp.get('days_left')})")

    print(f"\nStep 2. Gemini AI 레시피 생성 (카테고리: {cuisine}, 요청 수: {count}개)")
    generator = RecipeGenerator()
    recipes = generator.generate_recipes(
        available_ingredients=available,
        expiring_items=expiring,
        cuisine=cuisine,
        count=count,
        use_mock_if_no_key=True
    )

    display_recipes(recipes)

    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump({"recipes": recipes}, f, ensure_ascii=False, indent=2)
        print(f"\n💾 레시피 결과가 성공적으로 저장되었습니다: {save_path}")

    if notify:
        print("\nStep 3. 팀원 D 텔레그램 봇으로 레시피 카드 알림 전송")
        notify_recipes(recipes, dry_run=dry_run)
        print("  ✅ 텔레그램 알림 전송 완료!")

    print("\n🎉 [팀원 C 파트 시뮬레이션이 성공적으로 완료되었습니다!]")


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="K-Refriger AI 식단 엔진 (팀원 C)"
    )
    parser.add_argument("--demo", action="store_true", help="재고 DB 기반 전체 데모 실행")
    parser.add_argument(
        "--cuisine",
        type=str,
        default="한식",
        help=f"요리 카테고리 ({', '.join(SUPPORTED_CUISINES)})"
    )
    parser.add_argument("--count", type=int, default=2, help="추천받을 레시피 개수 (기본 2)")
    parser.add_argument("--ingredients", type=str, help="가용 식재료 직접 입력 (쉼표 구분: '삼겹살,양파,두부')")
    parser.add_argument("--expiring", type=str, help="임박 식재료 직접 입력 (쉼표 구분: '두부,대파')")
    parser.add_argument("--save", type=str, help="생성된 레시피를 JSON 파일로 저장할 경로 (예: data/recipes.json)")
    parser.add_argument("--notify", action="store_true", help="팀원 D 텔레그램 봇으로 레시피 카드 발송")
    parser.add_argument("--dry-run", action="store_true", help="알림 전송 시 콘솔 출력만 수행")

    args = parser.parse_args(argv)

    if args.demo or (len(sys.argv) == 1 and not args.ingredients):
        run_demo(
            cuisine=args.cuisine,
            count=args.count,
            save_path=args.save,
            notify=args.notify,
            dry_run=args.dry_run
        )
        return 0

    # 직접 식재료 인자를 지정한 경우
    avail = [s.strip() for s in args.ingredients.split(",") if s.strip()] if args.ingredients else []
    exp_list = []
    if args.expiring:
        for name in args.expiring.split(","):
            if name.strip():
                exp_list.append({"name": name.strip(), "days_left": 1})

    print_banner()
    generator = RecipeGenerator()
    recipes = generator.generate_recipes(
        available_ingredients=avail,
        expiring_items=exp_list,
        cuisine=args.cuisine,
        count=args.count,
        use_mock_if_no_key=True
    )
    display_recipes(recipes)

    if args.save:
        os.makedirs(os.path.dirname(os.path.abspath(args.save)), exist_ok=True)
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump({"recipes": recipes}, f, ensure_ascii=False, indent=2)
        print(f"\n💾 레시피 결과가 성공적으로 저장되었습니다: {args.save}")

    if args.notify:
        notify_recipes(recipes, dry_run=args.dry_run)
        print("  ✅ 텔레그램 알림 전송 완료!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
