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
from src.ocr.schema import ReceiptParseResult, ReceiptItem  # noqa: E402


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
        assert any(item.category == "간식" for item in result.items)
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_filter_and_clean_items():
    parser = ReceiptParser()
    raw_items = [
        ReceiptItem(name="양파", category="채소"),
        ReceiptItem(name="초코파이", category="기타"),
        ReceiptItem(name="콜라", category="가공식품"),
        ReceiptItem(name="79옻칠미니볶음스푼기", category="기타"),
        ReceiptItem(name="N코럴스텐국자(소)", category="기타"),
        ReceiptItem(name="원형면봉200개_", category="기타"),
        ReceiptItem(name="불스원샷휘발유용 500", category="기타"),
    ]

    cleaned = parser.filter_and_clean_items(raw_items)
    cleaned_names = [it.name for it in cleaned]

    # 비식품 4종은 반드시 쳐내기(제외)
    assert "79옻칠미니볶음스푼기" not in cleaned_names
    assert "N코럴스텐국자(소)" not in cleaned_names
    assert "원형면봉200개_" not in cleaned_names
    assert "불스원샷휘발유용 500" not in cleaned_names

    # 식재료는 유지
    assert "양파" in cleaned_names

    # 간식은 카테고리 '간식'으로 정상 보정
    chocopie = next(it for it in cleaned if it.name == "초코파이")
    assert chocopie.category == "간식"

    cola = next(it for it in cleaned if it.name == "콜라")
    assert cola.category == "간식"
