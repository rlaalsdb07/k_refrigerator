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
| **팀원 A (팀장)** | CI/CD 파이프라인 | GitHub Actions 구축, Cron 스케줄러, `workflow_dispatch`, Auto Git Commit & Push 관리 |
| **팀원 B (본 파트)** | **OCR & 스마트 재고 DB** | **Gemini Vision 영수증 인식, `inventory.json` 관리, 유통기한 산출, 요리 실행 시 차감(기본 양념 제외)** |
| **팀원 C** | AI 식단 엔진 | 프롬프트 설계, 남은 재고 기반 맞춤형 레시피 동적 생성, `cuisine` 옵션 확장 |
| **팀원 D** | 알림 & PM | Discord Webhook / Telegram Bot 연동, D-3 유통기한 임박 알림 전송, 일정 관리 |

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
│   ├── __init__.py
│   └── main_b.py               # 팀원 B 통합 실행 CLI
├── tests/
│   ├── test_inventory.py       # 재고 관리 및 차감 로직 단위 테스트
│   └── test_ocr.py             # OCR 파서 단위 테스트
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

### 4) 단위 테스트 실행
```bash
pytest tests/
```
