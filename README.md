# 🥬 K-Refriger: 스마트 냉장고 재고 관리 및 AI 레시피 추천 시스템
> **GitHub Actions + Vision AI 기반 일상 자동화**  
> *"영수증 사진 한 장으로 시작하는 스마트 냉장고 재고 관리 및 맞춤형 AI 레시피 추천"*

---

## 📌 1. 프로젝트 개요
- **배경 & 목적**: 
  - 냉장고 속 방치되어 버려지는 식재료 낭비 및 음식물 쓰레기 방지
  - 불규칙한 잔여 재고를 파악하여 유통기한 임박(D-3) 알림 및 알뜰한 맞춤 식단 제공
- **서버리스 아키텍처**: 별도의 상시 웹 서버 없이 GitHub Actions Runner와 Git Repository(`inventory.json`)를 영구 DB로 활용

---

## 👥 2. 팀원 R&R (역할 분담)

| 역할 | 담당 영역 | 주요 구현 및 책임 |
| :--- | :--- | :--- |
| **김민유 (팀장)** | CI/CD 파이프라인 | GitHub Actions 구축, Cron 스케줄러, `workflow_dispatch`, Auto Git Commit & Push 관리 |
| **전민성** | **OCR & 스마트 재고 DB** | **Gemini Vision 영수증 인식, `inventory.json` 관리, 유통기한 산출, 요리 실행 시 차감(기본 양념 제외)** |
| **김민재** | AI 식단 엔진 | 프롬프트 설계, 남은 재고 기반 맞춤형 레시피 동적 생성, `cuisine` 옵션 확장 |
| **마흐디에** | 알림 & PM | Discord Webhook / Telegram Bot 연동, D-3 유통기한 임박 알림 전송, 일정 관리 |

---

## 🛠️ 3. 팀원 B 상세 구현 내역

### 1) Gemini Vision 기반 영수증 OCR (`src/ocr/`)
- 마트/편의점마다 제각각인 비정형 영수증 사진을 분석하여 구조화된 데이터로 추출
- 품목명, 수량, 단위, 카테고리, 구매일자 정제 (Pydantic 스키마 기반 정형화)
- 비식품(종량제 봉투, 세제 등) 자동 필터링 및 대표 식재료명으로 정제

### 2) 스마트 재고 DB & 유통기한 자동 산출 (`src/db/`)
- **`inventory.json` 영구 보존 구조**: GitHub Actions 종료 시 사라지지 않도록 JSON 기반 파일 DB로 구성
- **유통기한 산출 엔진 (`expiry_calculator.py`)**:
  - 구매일자 + 식재료별 기본 보관기간(`default_expiry.json`)을 계산하여 `expiry_date` 자동 산출
  - 현재 날짜 기준 D-day(`days_left`) 실시간 계산
- **요리 시 재고 자동 차감 로직 (`inventory_manager.py`)**:
  - **★ 핵심 요구사항 반영**: 요리 실행 시 **기본 양념(간장, 소금, 설탕, 고춧가루, 식용유 등)은 차감 대상에서 자동 제외**
  - 유통기한이 가장 임박한 품목부터 우선 차감 (FEFO: First Expiring First Out)
- **팀원 간 인터페이스 연동 지원**:
  - **팀원 D 연동**: `get_expiring_items(days=3)` -> D-3 임박 품목 실시간 조회
  - **팀원 C 연동**: `get_available_ingredients()` -> 추천 가능한 잔여 식재료 목록 제공
  - **팀원 A 연동**: CLI 명령어로 `workflow_dispatch` 및 Cron 작업에서 즉시 호출 가능

---

## 🔔 3-2. 팀원 D 상세 구현 내역 (텔레그램 알림)

### 1) 텔레그램 봇 연동 (`src/notify/`)
- `telegram.py`: Telegram Bot API 클라이언트 (표준 라이브러리만 사용, 4096자 초과 시 자동 분할)
- `messages.py`: D-3 임박 알림, 레시피 카드, 영수증 입고/요리 차감 결과 메시지 포맷 (HTML)
- `__init__.py`: 팀원용 함수 `notify_expiry`, `notify_recipes`, `notify_receipt`, `notify_cooked`

### 2) D-3 유통기한 임박 알림
- 팀원 B의 `get_expiring_items(days=3)`, `get_expired_items()`로 조회 (기본 양념 제외)
- GitHub Actions 러너는 UTC이므로 **한국 날짜(KST) 기준**으로 D-day 계산
- `.github/workflows/d3-alert.yml`: 매일 **08:00 KST** 자동 전송 (+ `workflow_dispatch` 수동 실행)
- `data/recipes.json`이 있으면 레시피 카드도 함께 전송 (팀원 C 연계)

### 3) 설정
1. 텔레그램 **@BotFather** → `/newbot` → 토큰 발급
2. `.env`에 `TELEGRAM_BOT_TOKEN` 입력 후 봇에게 아무 메시지 전송 → `python src/main_d.py --chat-id`로 채팅 ID 확인
3. `.env`에 `TELEGRAM_CHAT_ID` 입력
4. GitHub → Settings → Secrets and variables → Actions 에 같은 이름으로 두 값 등록

### 4) 실행
```bash
python src/main_d.py --test                 # 연결 테스트
python src/main_d.py --expiry               # D-3 임박 알림
python src/main_d.py --expiry --dry-run     # 전송 없이 화면 출력
python src/main_d.py --recipes recipes.json # 레시피 카드
```

### 5) 다른 팀원 코드에서 호출
```python
from src.notify import notify_receipt, notify_cooked, notify_recipes
notify_receipt(manager.add_items_from_receipt(receipt))   # 팀원 B: 입고 후
notify_cooked(manager.deduct_for_dish(dish, ingredients)) # 팀원 B: 요리 차감 후
notify_recipes(recipes)  # 팀원 C: [{title, cuisine, time, uses_expiring, ingredients, steps}]
```

---

## 🍳 3-3. 팀원 C 상세 구현 내역 (AI 식단 엔진)

### 1) Gemini 기반 맞춤형 레시피 생성 및 Pydantic 스키마 (`src/recipe/`)
- **잔여 식재료 기반 프롬프트 엔지니어링 (`prompts.py`)**:
  - 팀원 B의 재고 DB에서 가용 식재료(`get_available_ingredients()`)와 유통기한 임박 식재료(`get_expiring_items(days=3)`)를 주입
  - 임박 식재료를 최우선으로 소비하도록 유도하며, 실제로 활용된 재료를 `uses_expiring`에 명시
  - 집집마다 구비된 기본 양념(간장, 소금, 설탕, 고춧가루, 식용유, 마늘 등)을 자유롭게 조합하여 현실적인 레시피 도출
- **정형화 스키마 (`schema.py`)**:
  - `Recipe` (Pydantic v2): `title`, `cuisine`, `time`, `difficulty`, `description`, `uses_expiring`, `ingredients`, `steps`, `tips`
  - 팀원 D의 텔레그램 카드 포맷(`messages.recipe_card`)과 100% 호환
- **지능형 Mock 엔진 내장 (`generator.py`)**:
  - `GEMINI_API_KEY`가 없거나 API 호출 실패 시에도, 입력된 식재료와 임박 재료, 선택한 cuisine 스타일을 조합하여 완성도 높은 Mock 레시피를 실시간 생성 (테스트 및 오프라인 데모 완벽 지원)

### 2) `cuisine` 옵션 확장
- 한식뿐만 아니라 **양식, 중식, 일식, 분식, 퓨전, 다이어트/건강식** 등 다양한 요리 카테고리 지원
- CLI 인자(`--cuisine`)로 사용자가 원하는 스타일을 지정하여 레시피 생성 가능

### 3) 팀원 간 인터페이스 연동
- **팀원 B 연계**: `InventoryManager`로부터 가용 재료와 D-3 임박 재료를 자동 수신
- **팀원 D 연계**: 생성된 레시피를 `notify_recipes(recipes)`를 통해 텔레그램 카드 메시지로 즉시 전송
- **팀원 A 연계**: 일일 파이프라인에서 호출 가능한 `generate_recipes()` 함수 제공

### 4) 실행 방법 (`src/main_c.py`)
```bash
python src/main_c.py --demo                      # 재고 DB 연동 전체 추천 데모
python src/main_c.py --cuisine 양식               # 양식 스타일 레시피 추천
python src/main_c.py --cuisine 일식 --count 3     # 일식 3가지 메뉴 추천
python src/main_c.py --ingredients "두부,대파" --expiring "두부" # 수동 식재료 지정
python src/main_c.py --demo --save data/recipes.json          # 결과를 recipes.json으로 저장
python src/main_c.py --demo --notify --dry-run   # 생성 후 텔레그램 알림 시뮬레이션
```

---

## 📁 4. 디렉토리 구조

```text
K-Refriger/
├── data/
│   ├── default_expiry.json     # 카테고리/품목별 기본 보관일수 및 기본 양념 정의
│   ├── inventory.json          # 냉장고 재고 DB (Git Commit으로 보존)
│   └── receipts/               # 영수증 이미지 보관 폴더
├── src/
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── parser.py           # Gemini Vision API 영수증 파서
│   │   └── schema.py           # Pydantic v2 데이터 스키마
│   ├── db/
│   │   ├── __init__.py
│   │   ├── expiry_calculator.py# 유통기한 및 D-day, 기본양념 판별
│   │   └── inventory_manager.py# 재고 입고/차감/조회 핵심 매니저
│   ├── recipe/
│   │   ├── __init__.py         # AI 식단 모듈 인터페이스
│   │   ├── schema.py           # 레시피 데이터 스키마 (Pydantic v2)
│   │   ├── prompts.py          # 맞춤형 레시피 프롬프트 엔지니어링
│   │   └── generator.py        # Gemini API 및 지능형 Mock 레시피 생성기
│   ├── notify/
│   │   ├── __init__.py         # 알림 함수 (notify_expiry 등)
│   │   ├── telegram.py         # Telegram Bot API 클라이언트
│   │   └── messages.py         # 알림/레시피 카드 메시지 포맷
│   ├── __init__.py
│   ├── main_b.py               # 팀원 B 통합 실행 CLI
│   ├── main_c.py               # 팀원 C AI 식단 엔진 실행 CLI
│   └── main_d.py               # 팀원 D 텔레그램 알림 CLI
├── tests/
│   ├── test_inventory.py       # 재고 관리 및 차감 로직 단위 테스트
│   ├── test_ocr.py             # OCR 파서 단위 테스트
│   ├── test_notify.py          # 텔레그램 알림 단위 테스트
│   └── test_recipe.py          # AI 식단 엔진 단위 테스트
├── requirements.txt            # 필요 패키지 (google-genai, pydantic 등)
├── .env.example                # 환경 변수 설정 템플릿
└── README.md
```

---

## 🚀 5. 설치 및 실행 가이드

### 1) 환경 준비
```bash
# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정 (.env 파일 생성 후 GEMINI_API_KEY 입력)
# (API 키가 없어도 내장된 Mock 엔진으로 전체 시뮬레이션 및 테스트가 가능합니다)
cp .env.example .env
```

### 2) 팀원 B 전체 파이프라인 데모 실행
영수증 입고 ➡️ 유통기한 자동 산출 ➡️ D-3 임박 품목 감지 ➡️ 요리 실행 및 양념 제외 차감의 전 과정을 한 번에 확인할 수 있습니다.
```bash
python src/main_b.py --demo
```

### 3) 개별 CLI 명령어 사용법 (GitHub Actions 연계용)

- **현재 냉장고 재고 및 D-day 상태 확인**:
  ```bash
  python src/main_b.py --list
  ```

- **영수증 스캔 및 자동 입고**:
  ```bash
  python src/main_b.py --scan data/receipts/sample_receipt.jpg
  ```

- **요리 실행 및 재고 차감 (기본 양념은 자동 제외됨)**:
  ```bash
  python src/main_b.py --cook "돼지고기 김치찌개" --ingredients "삼겹살:1,두부:1,진간장:1,고춧가루:1"
  ```

- **D-3 임박 식재료 확인 (팀원 D 봇 알림용)**:
  ```bash
  python src/main_b.py --check-d3
  ```

- **추천용 가용 식재료 목록 확인 (팀원 C AI 식단용)**:
  ```bash
  python src/main_b.py --available
  ```

### 4) 팀원 C AI 식단 추천 데모 및 개별 실행

- **냉장고 잔여 재고 기반 AI 레시피 추천 전체 데모**:
  ```bash
  python src/main_c.py --demo
  ```

- **cuisine(요리 스타일) 옵션 확장 추천 (양식, 중식, 일식 등)**:
  ```bash
  python src/main_c.py --demo --cuisine 양식
  python src/main_c.py --demo --cuisine 일식 --count 3
  ```

- **원하는 식재료 및 임박 재료 직접 입력하여 레시피 생성**:
  ```bash
  python src/main_c.py --ingredients "삼겹살,양파,두부" --expiring "두부" --cuisine 한식
  ```

- **레시피 생성 후 JSON 저장 및 텔레그램 알림 연동**:
  ```bash
  python src/main_c.py --demo --save data/recipes.json --notify --dry-run
  ```

### 5) 단위 테스트 실행
```bash
pytest tests/
```

