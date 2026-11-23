"""
텔레그램 메시지 포맷 (HTML parse mode)
- 입력은 팀원 B의 inventory.json 품목 dict 형식을 그대로 사용
  (name, quantity, unit, expiry_date, days_left)
"""
from html import escape
from typing import Any, Dict, List


def _num(value: Any) -> str:
    """2.0 -> '2', 0.5 -> '0.5'"""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _qty(item: Dict[str, Any]) -> str:
    qty = item.get("quantity")
    if qty in (None, ""):
        return ""
    return f" ({escape(_num(qty))}{escape(str(item.get('unit', '')))})"


def dday_label(days_left: int) -> str:
    if days_left < 0:
        return f"만료 {-days_left}일 지남"
    if days_left == 0:
        return "D-DAY"
    return f"D-{days_left}"


def expiry_alert(
    expiring: List[Dict[str, Any]],
    expired: List[Dict[str, Any]],
    today: str,
    days: int = 3,
) -> str:
    """D-N 유통기한 임박 + 만료 품목 알림"""
    lines = ["🧊 <b>K-Refriger 유통기한 알림</b>", f"📅 {escape(today)}", ""]
    if not expiring and not expired:
        lines.append(f"✅ {days}일 이내에 유통기한이 끝나는 재료가 없어요.")
        return "\n".join(lines)

    if expiring:
        lines.append(f"⚠️ <b>유통기한 임박 (D-{days} 이내)</b>")
        for it in expiring:
            left = int(it.get("days_left", 0))
            icon = "🔴" if left <= 1 else "🟠"
            lines.append(
                f"{icon} <b>{escape(str(it.get('name', '?')))}</b>{_qty(it)}"
                f" — {dday_label(left)} ({escape(str(it.get('expiry_date', '')))})"
            )
        lines.append("")
    if expired:
        lines.append("🗑 <b>유통기한 지남 (폐기 확인)</b>")
        for it in expired:
            left = int(it.get("days_left", 0))
            lines.append(
                f"⚫ {escape(str(it.get('name', '?')))}{_qty(it)}"
                f" — {dday_label(left)}"
            )
        lines.append("")
    lines.append("👉 임박 재료로 만들 수 있는 레시피를 확인해 보세요!")
    return "\n".join(lines)


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [s.strip() for s in value.splitlines() if s.strip()]
    out = []
    for v in value:
        if isinstance(v, dict):
            name = v.get("name") or ""
            amt = v.get("amount") or v.get("quantity") or ""
            out.append(f"{name} {_num(amt) if amt != '' else ''}".strip())
        else:
            out.append(str(v))
    return out


def recipe_card(recipe: Dict[str, Any]) -> str:
    """팀원 C AI 식단 엔진의 레시피 1개를 카드로 변환
    키: title(name), cuisine, time, uses_expiring, ingredients, steps
    """
    title = recipe.get("title") or recipe.get("name") or "추천 레시피"
    lines = [f"🍳 <b>{escape(str(title))}</b>"]
    meta = []
    if recipe.get("cuisine"):
        meta.append(f"🌏 {escape(str(recipe['cuisine']))}")
    t = recipe.get("time") or recipe.get("cook_time")
    if t:
        meta.append(f"⏱ {escape(str(t))}")
    if meta:
        lines.append(" · ".join(meta))
    uses = _as_list(recipe.get("uses_expiring"))
    if uses:
        lines.append(f"♻️ 임박 재료 활용: {escape(', '.join(uses))}")
    ings = _as_list(recipe.get("ingredients"))
    if ings:
        lines += ["", "<b>재료</b>"] + [f"• {escape(x)}" for x in ings]
    steps = _as_list(recipe.get("steps") or recipe.get("instructions"))
    if steps:
        lines += ["", "<b>만드는 법</b>"]
        lines += [f"{n}. {escape(s)}" for n, s in enumerate(steps, 1)]
    return "\n".join(lines)


def recipes_message(recipes: List[Dict[str, Any]]) -> str:
    return "\n\n━━━━━━━━━━\n\n".join(recipe_card(r) for r in recipes)


def receipt_summary(added: List[Dict[str, Any]]) -> str:
    """영수증 입고 결과 (InventoryManager.add_items_from_receipt 반환값)"""
    if not added:
        return "🧾 영수증에서 등록된 품목이 없어요. 사진을 다시 확인해 주세요."
    lines = [f"🧾 <b>영수증 입고 완료</b> — {len(added)}개 품목", ""]
    for it in added:
        exp = it.get("expiry_date")
        tail = f" · ~{escape(str(exp))}" if exp else ""
        lines.append(f"• {escape(str(it.get('name', '?')))}{_qty(it)}{tail}")
    return "\n".join(lines)


def cooked_summary(result: Dict[str, Any]) -> str:
    """요리 차감 결과 (InventoryManager.deduct_for_dish 반환값)"""
    dish = escape(str(result.get("dish_name", "요리")))
    lines = [f"🍽 <b>{dish}</b> 요리 완료! 재고에서 차감했어요.", ""]
    for d in result.get("deducted_items", []):
        lines.append(
            f"➖ {escape(str(d['name']))} {escape(_num(d['deducted_quantity']))}"
        )
    for s in result.get("skipped_seasonings", []):
        lines.append(f"🛡 {escape(str(s['name']))} (기본 양념, 차감 제외)")
    for i in result.get("insufficient_items", []):
        lines.append(
            f"⚠️ {escape(str(i['name']))} 재고 부족 "
            f"(부족: {escape(_num(i['shortage']))})"
        )
    return "\n".join(lines)
