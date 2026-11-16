"""
팀원 D 텔레그램 알림 유닛 테스트 (실제 전송 없음)
"""
import json
import os
import sys
import tempfile
from unittest import mock

import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.db.inventory_manager import InventoryManager  # noqa: E402
from src.notify import messages, notify_expiry  # noqa: E402
from src.notify.telegram import (  # noqa: E402
    TelegramBot, load_env_file, split_message
)


def _item(name, expiry, qty=1.0, seasoning=False):
    return {
        "id": name, "name": name, "quantity": qty, "unit": "개",
        "category": "기타", "purchase_date": "2026-11-10",
        "expiry_date": expiry, "is_seasoning": seasoning,
    }


@pytest.fixture
def manager():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    items = [
        _item("우유", "2026-11-17"),
        _item("두부", "2026-11-19"),
        _item("김치", "2026-12-20"),
        _item("대파", "2026-11-14"),
        _item("간장", "2026-11-15", seasoning=True),
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_updated": "", "items": items}, f, ensure_ascii=False)
    yield InventoryManager(db_path=path)
    os.remove(path)


def test_expiry_alert_dry_run(manager, capsys):
    n = notify_expiry(reference_date="2026-11-16", manager=manager,
                      dry_run=True)
    out = capsys.readouterr().out
    assert n == 3  # 우유(D-1), 두부(D-3), 대파(만료) / 간장은 양념이라 제외
    assert "우유" in out and "D-1" in out
    assert "만료 2일 지남" in out
    assert "간장" not in out and "김치" not in out


def test_only_if_any_skips_send(manager):
    with mock.patch("src.notify.TelegramBot") as bot:
        n = notify_expiry(reference_date="2026-10-01", only_if_any=True,
                          manager=manager)
    assert n == 0
    bot.assert_not_called()


def test_recipes_sent_after_alert(manager):
    with mock.patch("src.notify.TelegramBot") as bot:
        notify_expiry(reference_date="2026-11-16", manager=manager,
                      recipes=[{"title": "두부조림"}])
    assert bot.return_value.send_message.call_count == 2


def test_html_is_escaped():
    text = messages.expiry_alert(
        [{"name": "<b>x&y", "days_left": 0, "expiry_date": "2026-11-16"}],
        [], "2026-11-16")
    assert "&lt;b&gt;x&amp;y" in text
    assert "D-DAY" in text


def test_recipe_card():
    card = messages.recipe_card({
        "title": "계란국", "cuisine": "한식",
        "ingredients": [{"name": "계란", "amount": 2}],
        "steps": "끓인다\n넣는다",
    })
    assert "<b>계란국</b>" in card
    assert "• 계란 2" in card
    assert "2. 넣는다" in card


def test_cooked_summary_uses_deduct_result():
    text = messages.cooked_summary({
        "dish_name": "김치찌개",
        "deducted_items": [{"name": "두부", "deducted_quantity": 1.0}],
        "skipped_seasonings": [{"name": "간장", "reason": ""}],
        "insufficient_items": [{"name": "삼겹살", "shortage": 1.0}],
    })
    assert "➖ 두부 1" in text
    assert "간장 (기본 양념" in text
    assert "삼겹살 재고 부족" in text


def test_split_message():
    text = "a" * 5000 + "\n" + "b" * 10
    parts = split_message(text)
    assert all(len(p) <= 4096 for p in parts)
    assert "".join(parts) == text


def test_send_message_calls_api():
    bot = TelegramBot(token="T", chat_id="42")
    with mock.patch.object(bot, "_call", return_value={}) as call:
        bot.send_message("hi")
    method, params = call.call_args.args
    assert method == "sendMessage"
    assert params["chat_id"] == "42"
    assert params["parse_mode"] == "HTML"


def test_load_env_file_keeps_existing(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text('TG_A="from_file"\nTG_B=file\n# comment\n',
                   encoding="utf-8")
    monkeypatch.setenv("TG_B", "already")
    monkeypatch.delenv("TG_A", raising=False)
    load_env_file(str(env))
    assert os.environ["TG_A"] == "from_file"
    assert os.environ["TG_B"] == "already"
    monkeypatch.delenv("TG_A")
