"""
팀원 D: 텔레그램 알림 시스템

다른 팀원 코드에서 사용 예:
    from src.notify import (
        notify_expiry, notify_recipes, notify_receipt, notify_cooked
    )
    notify_expiry()                          # D-3 임박 알림 (매일 Cron)
    notify_receipt(added)                    # 팀원 B: add_items_from_receipt 결과
    notify_cooked(result)                    # 팀원 B: deduct_for_dish 결과
    notify_recipes(recipes)                  # 팀원 C: 생성된 레시피 목록
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import messages
from .telegram import TelegramBot, TelegramError

KST = timezone(timedelta(hours=9))

__all__ = [
    "notify_expiry", "notify_recipes", "notify_receipt", "notify_cooked",
    "today_kst", "TelegramBot", "TelegramError",
]


def today_kst() -> str:
    """GitHub Actions 러너는 UTC이므로 한국 날짜를 명시적으로 계산"""
    return datetime.now(KST).strftime("%Y-%m-%d")


def notify_expiry(
    days: int = 3,
    recipes: Optional[List[Dict[str, Any]]] = None,
    reference_date: Optional[str] = None,
    only_if_any: bool = False,
    manager: Any = None,
    dry_run: bool = False,
) -> int:
    """팀원 B의 InventoryManager로 임박/만료 품목을 조회해 알림 전송.
    반환값: 임박 + 만료 품목 수
    """
    if manager is None:
        from ..db.inventory_manager import InventoryManager
        manager = InventoryManager()
    ref = reference_date or today_kst()
    expiring = manager.get_expiring_items(days=days, reference_date=ref)
    expired = [
        it for it in manager.get_expired_items(reference_date=ref)
        if not it.get("is_seasoning", False)
    ]
    total = len(expiring) + len(expired)
    if only_if_any and total == 0:
        print("임박/만료 품목이 없어 알림을 보내지 않습니다.")
        return 0

    bot = TelegramBot(dry_run=dry_run)
    bot.send_message(messages.expiry_alert(expiring, expired, ref, days))
    if total and recipes:
        bot.send_message(messages.recipes_message(recipes))
    return total


def notify_recipes(
    recipes: List[Dict[str, Any]], dry_run: bool = False
) -> None:
    TelegramBot(dry_run=dry_run).send_message(
        messages.recipes_message(recipes)
    )


def notify_receipt(
    added_items: List[Dict[str, Any]], dry_run: bool = False
) -> None:
    TelegramBot(dry_run=dry_run).send_message(
        messages.receipt_summary(added_items)
    )


def notify_cooked(result: Dict[str, Any], dry_run: bool = False) -> None:
    TelegramBot(dry_run=dry_run).send_message(messages.cooked_summary(result))
