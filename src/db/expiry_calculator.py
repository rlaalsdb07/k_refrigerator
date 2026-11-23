"""
식재료 유통기한(소비기한) 산출 및 기본 양념/간식/비식품 판별 계산기
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


class ExpiryCalculator:
    """식재료 카테고리 및 명칭 기반 유통기한 산출 엔진"""

    _DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    DEFAULT_CONFIG_PATH = os.path.abspath(
        os.path.join(_DATA_DIR, "default_expiry.json")
    )

    # 간식/음료/주류 키워드 (식재료와 분리하여 관리)
    SNACK_KEYWORDS = [
        "과자", "스낵", "칩", "초콜릿", "초코", "사탕", "캔디", "젤리", "카라멜",
        "쿠키", "비스킷", "웨하스", "파이", "케이크", "도넛", "빵", "호빵", "호떡",
        "팝콘", "껌", "아이스크림", "빙과", "아이스", "빙수",
        "음료", "콜라", "사이다", "주스", "쥬스", "탄산", "환타", "밀키스",
        "포카리스웨트", "게토레이", "에너지드링크", "핫식스", "몬스터",
        "커피", "라떼", "아메리카노", "에스프레소", "카페", "티", "차",
        "맥주", "소주", "와인", "막걸리", "청주", "위스키", "하이볼",
        "포키", "빼빼로", "새우깡", "감자칩", "포테토칩", "프링글스", "초코파이",
        "카스타드", "몽쉘", "빅파이", "마가렛트", "약과", "한과", "뻥튀기", "맛동산"
    ]

    # 비식품 / 생활잡화 키워드 (영수증 파싱 및 재고에서 쳐내기용)
    NON_FOOD_KEYWORDS = [
        "스푼", "국자", "포크", "나이프", "젓가락", "수저", "식기", "접시", "그릇",
        "냄비", "후라이팬", "프라이팬", "도마", "칼", "가위", "집게", "뒤집개",
        "면봉", "화장솜", "물티슈", "휴지", "화장지", "티슈", "키친타올",
        "세제", "비누", "샴푸", "린스", "바디워시", "치약", "칫솔", "가글",
        "쓰레기봉투", "종량제", "비닐봉투", "쇼핑백", "봉투",
        "불스원샷", "워셔액", "엔진오일", "차량", "방향제", "탈취제",
        "건전지", "배터리", "호일", "랩", "위생백", "지퍼백", "위생장갑",
        "수세미", "행주", "고무장갑", "락스", "표백제", "섬유유연제",
        "살충제", "모기약", "에프킬라", "테이프", "본드", "라이터", "부탄가스",
        "스타킹", "양말", "마스크", "기저귀", "생리대", "면도기", "면도날"
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """기본 보관기간 및 양념 목록 JSON 파일 로드"""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "categories": {
                "채소": 7, "육류": 5, "닭고기": 3, "수산물": 3,
                "유제품": 10, "계란": 21, "두부": 5, "과일": 7,
                "가공식품": 60, "간식": 60, "냉동식품": 90, "기타": 14
            },
            "item_specific_days": {
                "삼겹살": 5, "소고기": 5, "우유": 10, "두부": 5, "양파": 21
            },
            "seasonings": [
                "소금", "설탕", "간장", "고추장", "된장", "후추", "참기름", "식용유"
            ]
        }

    def is_seasoning(self, item_name: str) -> bool:
        """기본 양념 여부 판별 (요리 차감 제외 대상)"""
        clean_name = item_name.strip()
        seasonings = self.config.get("seasonings", [])
        for seasoning in seasonings:
            if seasoning in clean_name or clean_name in seasoning:
                return True
        return False

    def is_snack(self, item_name: str, category: str = "") -> bool:
        """간식/음료/주류 여부 판별 (요리 레시피 추천 식재료에서 제외)"""
        if category in ["간식", "음료", "주류", "간식/음료"]:
            return True
        clean_name = item_name.strip()
        for kw in self.SNACK_KEYWORDS:
            if kw in clean_name:
                return True
        return False

    def is_non_food(self, item_name: str, raw_name: str = "") -> bool:
        """이상한 것들(비식품/생활용품/잡화) 여부 판별 (영수증 파싱 시 쳐내기용)"""
        text = f"{item_name} {raw_name}".strip()
        for kw in self.NON_FOOD_KEYWORDS:
            if kw in text:
                return True
        return False

    def get_shelf_life_days(self, item_name: str, category: str = "기타") -> int:
        """품목명 및 카테고리에 따른 보관 가능 일수 조회"""
        clean_name = item_name.strip()
        item_specific = self.config.get("item_specific_days", {})

        # 1. 특정 식재료명 직접 매칭
        for key, days in item_specific.items():
            if key in clean_name:
                return days

        # 2. 카테고리 기준 매칭
        categories = self.config.get("categories", {})
        if category in categories:
            return categories[category]

        # 3. 양념인 경우 기본 180일 보관
        if self.is_seasoning(clean_name):
            return 180

        # 4. 간식인 경우 기본 60일 보관
        if self.is_snack(clean_name, category):
            return categories.get("간식", 60)

        # 기본 fallback
        return categories.get("기타", 14)

    def calculate_expiry_date(
        self,
        item_name: str,
        category: str = "기타",
        purchase_date_str: Optional[str] = None
    ) -> str:
        """구매일자와 식재료명을 기준으로 유통기한(YYYY-MM-DD) 계산"""
        if not purchase_date_str:
            purchase_date = datetime.now().date()
        else:
            try:
                date_text = purchase_date_str.strip()
                purchase_date = datetime.strptime(
                    date_text, "%Y-%m-%d"
                ).date()
            except ValueError:
                purchase_date = datetime.now().date()

        shelf_life = self.get_shelf_life_days(item_name, category)
        expiry_date = purchase_date + timedelta(days=shelf_life)
        return expiry_date.strftime("%Y-%m-%d")

    @staticmethod
    def calculate_days_left(
        expiry_date_str: str,
        reference_date_str: Optional[str] = None
    ) -> int:
        """
        유통기한까지 남은 일수(D-day) 계산
        - 양수: D-day (예: 3이면 D-3)
        - 0: 당일 만료 (D-DAY)
        - 음수: 기한 초과
        """
        try:
            expiry_date = datetime.strptime(
                expiry_date_str.strip(), "%Y-%m-%d"
            ).date()
        except ValueError:
            return 999

        if reference_date_str:
            try:
                ref_date = datetime.strptime(
                    reference_date_str.strip(), "%Y-%m-%d"
                ).date()
            except ValueError:
                ref_date = datetime.now().date()
        else:
            ref_date = datetime.now().date()

        delta = expiry_date - ref_date
        return delta.days
