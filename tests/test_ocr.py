"""
Gemini Vision OCR 영수증 파서 유닛 테스트
"""
import os
import sys
import tempfile

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.ocr.parser import ReceiptParser  # noqa: E402
from src.ocr.schema import ReceiptParseResult  # noqa: E402


def test_mock_parser():
    parser = ReceiptParser()

    # 임시 이미지 파일 생성
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    with open(path, "wb") as f:
        f.write(b"MOCK IMAGE")

    try:
        result = parser.parse_receipt_image(path, use_mock_if_no_key=True)
        assert isinstance(result, ReceiptParseResult)
        assert len(result.items) > 0
        assert any(item.name == "삼겹살" for item in result.items)
        assert any(item.is_seasoning is True for item in result.items)
    finally:
        if os.path.exists(path):
            os.remove(path)
