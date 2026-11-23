import os
import tempfile
import traceback
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(
    page_title="K-Refriger<Action> 스마트 냉장고",
    page_icon="🧊",
    layout="wide",
)

load_dotenv()

IMPORT_ERROR_MSG = None
try:
    from src.ocr.parser import ReceiptParser
    from src.db.inventory_manager import InventoryManager
    from src.recipe.generator import RecipeGenerator
    from src.recipe.prompts import SUPPORTED_CUISINES
    from src.notify.telegram import TelegramBot, TelegramError
except Exception:
    IMPORT_ERROR_MSG = traceback.format_exc()

if IMPORT_ERROR_MSG:
    st.error("🚨 프로젝트 모듈을 불러오는 중 오류가 발생했습니다.")
    st.code(IMPORT_ERROR_MSG, language="python")
    st.info("터미널이 프로젝트 루트 위치에서 실행되었는지 확인해 주세요.")
    st.stop()

if "parsed_receipt" not in st.session_state:
    st.session_state.parsed_receipt = None
if "recommended_recipes" not in st.session_state:
    st.session_state.recommended_recipes = []


def get_status_badge(days_left: int) -> str:
    if days_left < 0:
        return f"🚨 만료 ({abs(days_left)}일 지남)"
    if days_left == 0:
        return "🔥 오늘 만료 (D-DAY)"
    if days_left <= 3:
        return f"⚠️ 임박 (D-{days_left})"
    return f"✅ 여유 (D-{days_left})"


def send_telegram_message(text: str, dry_run: bool = False) -> tuple[bool, str]:
    try:
        bot = TelegramBot(dry_run=dry_run)
        chunks = bot.send_message(text)
        if dry_run:
            return True, f"Dry-Run 테스트 완료 (터미널 콘솔 출력 {chunks}건)"
        return True, f"텔레그램 메시지 전송 성공! ({chunks}건)"
    except TelegramError as e:
        return False, f"텔레그램 오류: {e}"
    except Exception as e:
        return False, f"전송 중 예외 발생: {e}"


with st.sidebar:
    st.title("🧊 K-Refriger<Action>")
    st.caption("영수증 OCR · 재고 관리 · AI 레시피 · 텔레그램")
    st.divider()

    st.subheader("📲 텔레그램 연결 상태")
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    has_bot = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    has_chat = bool(os.environ.get("TELEGRAM_CHAT_ID"))

    st.write("• Gemini AI API:", "✅ 연결됨" if has_gemini else "❌ 미설정")
    st.write("• 텔레그램 봇 토큰:", "✅ 연결됨" if has_bot else "❌ 미설정")
    st.write("• 텔레그램 채팅 ID:", "✅ 연결됨" if has_chat else "❌ 미설정")

    dry_run_mode = st.toggle(
        "텔레그램 Dry-Run 모드 (콘솔만 출력)",
        value=False,
        help="켜두면 실제 텔레그램 발송 없이 터미널 출력만 확인합니다.",
    )

    if st.button("🔔 텔레그램 연결 테스트 메시지 발송", use_container_width=True):
        ok, msg = send_telegram_message(
            "🧊 <b>[K-Refriger&lt;Action&gt;]</b> 대시보드와 텔레그램 봇이 정상 연결되었습니다!",
            dry_run=dry_run_mode,
        )
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.divider()
    hide_seasonings = st.checkbox("재고 목록에서 기본 양념 숨기기", value=False)
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.rerun()


st.title("🧊 K-Refriger<Action> 스마트 냉장고 대시보드")

try:
    manager = InventoryManager()
    all_items = manager.load_inventory()
    cooking_ingredients = manager.get_cooking_ingredients()
    snack_items = manager.get_snack_items()
    expiring_items = manager.get_expiring_items(days=3)
    expired_items = [it for it in all_items if int(it.get("days_left", 0)) < 0]
    available_ingredients = manager.get_available_ingredients()
except Exception:
    st.error("🚨 재고 데이터를 불러오는 중 오류가 발생했습니다.")
    st.code(traceback.format_exc(), language="python")
    st.stop()

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("📦 전체 보유 품목", f"{len(all_items)}종")
kpi2.metric("🥦 요리용 식재료", f"{len(cooking_ingredients)}종")
kpi3.metric("🍪 간식·음료", f"{len(snack_items)}종")
kpi4.metric("⚠️ D-3 유통기한 임박", f"{len(expiring_items)}종")
kpi5.metric("🚨 유통기한 만료", f"{len(expired_items)}종")

st.divider()

tab_inventory, tab_upload, tab_recipe = st.tabs([
    "📦 보유 식재료 & 간식 현황",
    "📸 영수증 사진 업로드 (자동 입고)",
    "🍳 AI 레시피 추천 & 텔레그램 공유",
])


with tab_inventory:
    col_title, col_btn = st.columns([2, 1])
    with col_title:
        st.subheader("냉장고 속 식재료 및 간식 관리")
    with col_btn:
        if st.button("📲 현재 재고/임박 알림 텔레그램 보내기", type="primary", use_container_width=True):
            lines = ["🧊 <b>[K-Refriger 냉장고 재고 & 유통기한 리포트]</b>", ""]
            if expiring_items:
                lines.append("⚠️ <b>D-3 이내 임박 품목</b>")
                for it in expiring_items:
                    lines.append(
                        f"• {it.get('name')} : <b>{it.get('quantity')}{it.get('unit', '')}</b> (D-{it.get('days_left')})"
                    )
                lines.append("")
            if cooking_ingredients:
                lines.append("🥦 <b>요리용 식재료 현황</b>")
                for it in cooking_ingredients:
                    lines.append(
                        f"• {it.get('name')} : {it.get('quantity')}{it.get('unit', '')} (~{it.get('expiry_date', '')})"
                    )
                lines.append("")
            if snack_items:
                lines.append("🍪 <b>간식·음료 현황</b>")
                for it in snack_items:
                    lines.append(
                        f"• {it.get('name')} : {it.get('quantity')}{it.get('unit', '')} (~{it.get('expiry_date', '')})"
                    )
                lines.append("")
            if not all_items:
                lines.append("현재 등록된 식재료가 없습니다.")

            ok, msg = send_telegram_message("\n".join(lines), dry_run=dry_run_mode)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    view_mode = st.radio(
        "파트 구분 선택",
        ["전체 보기", "🥦 요리용 식재료 파트만", "🍪 간식 파트만 (스낵·음료)", "🧂 기본 양념 파트만"],
        horizontal=True,
    )

    if view_mode == "🥦 요리용 식재료 파트만":
        display_target = cooking_ingredients
    elif view_mode == "🍪 간식 파트만 (스낵·음료)":
        display_target = snack_items
    elif view_mode == "🧂 기본 양념 파트만":
        display_target = manager.get_seasoning_items()
    else:
        display_target = [
            it for it in all_items
            if not (hide_seasonings and it.get("is_seasoning"))
        ]

    if not display_target:
        st.info("해당 구분에 등록된 품목이 없습니다.")
    else:
        rows = []
        for it in display_target:
            days = int(it.get("days_left", 0))
            qty_str = f"{it.get('quantity', 0)} {it.get('unit', '')}".strip()
            if it.get("is_seasoning"):
                role_label = "🧂 기본 양념"
            elif it.get("category") == "간식":
                role_label = "🍪 간식·음료"
            else:
                role_label = "🥦 요리 식재료"

            rows.append({
                "품목명": it.get("name", ""),
                "보유 수량(양)": qty_str,
                "카테고리": it.get("category", ""),
                "구매일": it.get("purchase_date", ""),
                "유통기한": it.get("expiry_date", ""),
                "상태": get_status_badge(days),
                "구분": role_label,
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)


with tab_upload:
    st.subheader("영수증 사진 업로드 및 AI 자동 인식")
    st.caption("마트·편의점 영수증 사진을 올리면 식재료와 간식을 자동 분류하고, 비식품 잡화는 자동으로 쳐내어 냉장고에 등록합니다.")

    uploaded_file = st.file_uploader(
        "영수증 이미지 선택 (JPG, JPEG, PNG)",
        type=["jpg", "jpeg", "png"],
    )

    left_col, right_col = st.columns([1, 1.3])

    with left_col:
        if uploaded_file is not None:
            st.image(uploaded_file, caption="업로드된 영수증 사진", use_container_width=True)
            if st.button("🔍 사진에서 식재료/간식 추출하기", type="primary", use_container_width=True):
                suffix = os.path.splitext(uploaded_file.name)[1] or ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded_file.getbuffer())
                    tmp_path = tmp.name

                try:
                    with st.spinner("Gemini Vision AI가 식재료와 간식을 분류하고 비식품을 쳐내는 중입니다..."):
                        parser = ReceiptParser()
                        parsed = parser.parse_receipt_image(tmp_path, use_mock_if_no_key=True)
                        st.session_state.parsed_receipt = parsed
                    st.success("추출 완료! 오른쪽 표를 확인하고 냉장고에 입고하세요.")
                except Exception as e:
                    st.error(f"영수증 분석 실패: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
        else:
            st.info("위 버튼을 눌러 영수증 사진을 업로드해 주세요.")

    with right_col:
        parsed = st.session_state.parsed_receipt
        if parsed is not None:
            st.markdown("#### 인식된 품목 확인 (비식품은 자동 쳐내기 완료)")
            st.write(
                f"**매장명:** {parsed.store_name or '미상'} | "
                f"**구매일:** {parsed.purchase_date} | "
                f"**결제금액:** {f'{parsed.total_amount:,}원' if parsed.total_amount else '미상'}"
            )

            preview_data = []
            for item in parsed.items:
                if item.is_seasoning:
                    role_tag = "🧂 기본 양념"
                elif item.category == "간식":
                    role_tag = "🍪 간식·음료"
                else:
                    role_tag = "🥦 요리 식재료"

                preview_data.append({
                    "품목명": item.name,
                    "수량(양)": f"{item.quantity} {item.unit}".strip(),
                    "카테고리": item.category,
                    "구분": role_tag,
                })

            st.dataframe(preview_data, use_container_width=True, hide_index=True)

            if st.button("📥 냉장고에 입고하고 텔레그램 알림 보내기", type="primary", use_container_width=True):
                try:
                    added = manager.add_items_from_receipt(parsed)
                    msg_lines = [
                        "🧾 <b>[영수증 자동 입고 완료]</b>",
                        f"매장: {parsed.store_name or '알 수 없음'} ({parsed.purchase_date})",
                        "",
                    ]
                    for it in added:
                        cat_tag = "🍪간식" if it.get("category") == "간식" else "🥦식재료"
                        msg_lines.append(
                            f"• [{cat_tag}] {it.get('name')} : {it.get('quantity')}{it.get('unit', '')} (~{it.get('expiry_date', '')})"
                        )
                    ok, tg_msg = send_telegram_message("\n".join(msg_lines), dry_run=dry_run_mode)
                    st.session_state.parsed_receipt = None
                    st.success(f"{len(added)}개 품목 입고 완료! ({tg_msg})")
                    st.rerun()
                except Exception as e:
                    st.error(f"입고 처리 중 오류 발생: {e}")


with tab_recipe:
    st.subheader("보유 식재료 기반 AI 맞춤 레시피 추천")
    st.caption("간식(과자, 음료, 주류)과 양념은 제외하고, 순수 요리용 식재료만 기반으로 레시피를 구성합니다.")

    if available_ingredients:
        st.write("**현재 냉장고 요리용 식재료:**", ", ".join(available_ingredients))
    else:
        st.warning("현재 냉장고에 요리용 식재료가 없습니다. 먼저 영수증 사진을 업로드해 식재료를 추가해 주세요.")

    c1, c2, c3 = st.columns([1.2, 1, 1.5])
    with c1:
        cuisine_choice = st.selectbox("원하는 요리 스타일", options=list(SUPPORTED_CUISINES), index=0)
    with c2:
        recipe_num = st.number_input("추천 개수", min_value=1, max_value=5, value=2, step=1)
    with c3:
        st.write("")
        st.write("")
        gen_btn = st.button("👨‍🍳 AI 레시피 추천받기", type="primary", use_container_width=True)

    if gen_btn:
        if not available_ingredients:
            st.error("추천할 식재료가 부족합니다.")
        else:
            try:
                with st.spinner(f"보유 식재료로 만들 수 있는 [{cuisine_choice}] 레시피를 생성 중입니다..."):
                    generator = RecipeGenerator()
                    recipes = generator.generate_recipes(
                        available_ingredients=available_ingredients,
                        expiring_items=expiring_items,
                        cuisine=cuisine_choice,
                        count=int(recipe_num),
                        use_mock_if_no_key=True,
                    )
                    st.session_state.recommended_recipes = recipes
            except Exception as e:
                st.error(f"레시피 생성 오류: {e}")

    for idx, recipe in enumerate(st.session_state.recommended_recipes):
        with st.container(border=True):
            r_col1, r_col2 = st.columns([3, 1])
            title = recipe.get("title", f"추천 레시피 {idx + 1}")
            with r_col1:
                st.markdown(f"### 🍽️ {title}")
            with r_col2:
                if st.button("📲 이 레시피 텔레그램으로 전송", key=f"tg_recipe_{idx}", use_container_width=True):
                    r_lines = [
                        f"🍳 <b>[AI 추천 레시피] {title}</b>",
                        f"• 스타일: {recipe.get('cuisine', cuisine_choice)} | 조리시간: {recipe.get('time', '-')}",
                        "",
                        "<b>[필요 재료]</b>",
                    ]
                    for ing in recipe.get("ingredients", []):
                        r_lines.append(f"- {ing}")
                    r_lines.append("")
                    r_lines.append("<b>[조리 순서]</b>")
                    for step in recipe.get("steps", []):
                        r_lines.append(f"{step}")

                    ok, tg_msg = send_telegram_message("\n".join(r_lines), dry_run=dry_run_mode)
                    if ok:
                        st.success(tg_msg)
                    else:
                        st.error(tg_msg)

            meta = []
            if recipe.get("cuisine"):
                meta.append(f"**스타일:** {recipe['cuisine']}")
            if recipe.get("time"):
                meta.append(f"**조리시간:** {recipe['time']}")
            if recipe.get("difficulty"):
                meta.append(f"**난이도:** {recipe['difficulty']}")
            if meta:
                st.caption(" | ".join(meta))

            if recipe.get("description"):
                st.write(recipe["description"])
            if recipe.get("uses_expiring"):
                st.info(f"♻️ 유통기한 임박 재료 활용: {', '.join(recipe['uses_expiring'])}")

            col_ing, col_step = st.columns(2)
            with col_ing:
                st.markdown("**필요 식재료 및 양념**")
                for ing in recipe.get("ingredients", []):
                    st.write(f"- {ing}")
            with col_step:
                st.markdown("**만드는 법**")
                for step in recipe.get("steps", []):
                    st.write(f"{step}")

    st.divider()
    st.subheader("요리 완료 후 사용한 식재료 차감")
    with st.form("deduct_form"):
        dish_name = st.text_input("완성한 요리명", placeholder="예: 양파 계란볶음")
        used_items = st.text_input(
            "사용한 식재료와 양 (쉼표로 구분)",
            placeholder="예: 양파:1, 계란:2",
        )
        deduct_submit = st.form_submit_button("✅ 요리 완료 및 보유 수량 차감", type="primary")

        if deduct_submit:
            if not dish_name.strip() or not used_items.strip():
                st.warning("요리명과 사용한 식재료를 입력해 주세요.")
            else:
                ing_map = {}
                for part in used_items.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    if ":" in part:
                        k, v = part.split(":", 1)
                        try:
                            ing_map[k.strip()] = float(v.strip())
                        except ValueError:
                            ing_map[k.strip()] = 1.0
                    else:
                        ing_map[part] = 1.0

                try:
                    res = manager.deduct_for_dish(dish_name.strip(), ing_map)
                    msg_lines = [f"🍽️ <b>[{res.get('dish_name')}] 요리 완료 및 재고 차감</b>", ""]
                    for d in res.get("deducted_items", []):
                        msg_lines.append(f"➖ {d['name']} : {d['deducted_quantity']} 사용됨")
                    ok, tg_msg = send_telegram_message("\n".join(msg_lines), dry_run=dry_run_mode)
                    st.success(f"보유 식재료 수량이 차감되었습니다! ({tg_msg})")
                    st.rerun()
                except Exception as e:
                    st.error(f"차감 오류: {e}")
