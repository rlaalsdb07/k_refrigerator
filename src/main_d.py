"""
팀원 D (알림 & PM) 텔레그램 알림 실행 CLI
K-Refriger: D-3 유통기한 임박 알림, 레시피 카드, 입고/차감 결과 전송

사용 예:
  python src/main_d.py --test                       # 연결 테스트
  python src/main_d.py --chat-id                    # 내 채팅 ID 확인
  python src/main_d.py --expiry                     # D-3 임박 알림
  python src/main_d.py --expiry --recipes recipes.json
  python src/main_d.py --recipes recipes.json       # 레시피 카드만
  python src/main_d.py --expiry --dry-run           # 전송 없이 화면 출력
"""
import argparse
import json
import os
import sys

# 프로젝트 루트를 sys.path에 추가
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)

from src.notify import notify_expiry, notify_recipes  # noqa: E402
from src.notify.telegram import TelegramBot, TelegramError  # noqa: E402


def load_recipes(path):
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("recipes") or [data]
    return data


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # 윈도우 콘솔 한글/이모지 출력
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="K-Refriger 텔레그램 알림 시스템 (팀원 D)"
    )
    parser.add_argument("--test", action="store_true", help="연결 테스트 메시지")
    parser.add_argument(
        "--chat-id", action="store_true", help="봇에게 메시지 보낸 채팅 ID 조회"
    )
    parser.add_argument("--expiry", action="store_true", help="D-N 임박 알림")
    parser.add_argument("--days", type=int, default=3, help="임박 기준 일수")
    parser.add_argument("--recipes", type=str, help="레시피 JSON 경로 (팀원 C)")
    parser.add_argument(
        "--only-if-any", action="store_true", help="임박 품목 없으면 전송 안 함"
    )
    parser.add_argument("--date", type=str, help="기준 날짜 YYYY-MM-DD (테스트용)")
    parser.add_argument(
        "--dry-run", action="store_true", help="전송하지 않고 화면에 출력"
    )
    args = parser.parse_args(argv)

    try:
        if args.chat_id:
            ids = TelegramBot().find_chat_ids()
            if not ids:
                print("채팅이 없습니다. 텔레그램에서 봇에게 아무 메시지나 보낸 뒤 다시 실행하세요.")
            for cid, name in ids:
                print(f"{cid}\t{name}")
        elif args.test:
            TelegramBot(dry_run=args.dry_run).send_message(
                "✅ K-Refriger 텔레그램 봇 연결 성공!"
            )
            print("테스트 메시지 전송 완료")
        elif args.expiry:
            n = notify_expiry(
                days=args.days,
                recipes=load_recipes(args.recipes),
                reference_date=args.date,
                only_if_any=args.only_if_any,
                dry_run=args.dry_run,
            )
            print(f"임박/만료 품목: {n}개")
        elif args.recipes:
            notify_recipes(load_recipes(args.recipes), dry_run=args.dry_run)
            print("레시피 카드 전송 완료")
        else:
            parser.print_help()
    except (TelegramError, FileNotFoundError, json.JSONDecodeError) as err:
        print(f"❌ 오류: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
