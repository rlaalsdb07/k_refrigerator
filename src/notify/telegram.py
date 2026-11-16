"""
Telegram Bot API 클라이언트 (표준 라이브러리만 사용)
- 토큰/채팅 ID: 환경 변수 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  (로컬에서는 프로젝트 루트 .env, GitHub Actions에서는 Secrets)
- 4096자 넘는 메시지는 자동 분할 전송
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

API_BASE = "https://api.telegram.org"
MAX_LEN = 4096
_ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".env")
)


class TelegramError(RuntimeError):
    """텔레그램 전송 실패"""


def load_env_file(path: str = _ENV_PATH) -> None:
    """.env 파일의 KEY=VALUE를 읽어 환경 변수에 등록 (이미 있는 값은 유지)"""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def split_message(text: str, limit: int = MAX_LEN) -> List[str]:
    """줄 단위로 나눠 각 조각이 limit 이하가 되도록 분할"""
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks


class TelegramBot:
    """sendMessage / getUpdates만 사용하는 최소 클라이언트"""

    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        dry_run: bool = False,
        timeout: float = 15.0,
    ):
        load_env_file()
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.dry_run = dry_run
        self.timeout = timeout
        if not dry_run and not self.token:
            raise TelegramError(
                "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 확인해주세요."
            )

    def _call(self, method: str, params: Dict[str, str]) -> object:
        url = f"{API_BASE}/bot{self.token}/{method}"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise TelegramError(
                f"{method} 실패: HTTP {e.code} {detail}"
            ) from None
        except urllib.error.URLError as e:
            raise TelegramError(f"{method} 실패: {e.reason}") from None
        if not body.get("ok"):
            raise TelegramError(f"{method} 실패: {body}")
        return body["result"]

    def send_message(self, text: str) -> int:
        """HTML 메시지 전송. 보낸 메시지 조각 수 반환"""
        chunks = split_message(text)
        for chunk in chunks:
            if self.dry_run:
                print(f"--- [dry-run] chat={self.chat_id or '(미설정)'} ---")
                print(chunk + "\n")
                continue
            if not self.chat_id:
                raise TelegramError("TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
            self._call("sendMessage", {
                "chat_id": self.chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            })
        return len(chunks)

    def find_chat_ids(self) -> List[Tuple[str, str]]:
        """최근 봇에게 메시지를 보낸 채팅의 (chat_id, 이름) 목록"""
        result = self._call("getUpdates", {})
        seen: Dict[str, str] = {}
        for upd in result if isinstance(result, list) else []:
            msg = upd.get("message") or upd.get("channel_post") or {}
            chat = msg.get("chat")
            if chat:
                seen[str(chat["id"])] = (
                    chat.get("title") or chat.get("username")
                    or chat.get("first_name") or ""
                )
        return list(seen.items())
