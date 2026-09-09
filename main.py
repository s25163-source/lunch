import calendar
import datetime
import re
import requests
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="월간/주간/일간 학교 급식 달력",
    page_icon="📅",
    layout="wide",
)

st.title("🍱 우리 학교 급식 알리미")
st.caption(
    "월별, 주별, 일별 급식 메뉴와 칼로리 정보를 확인하고, 선호하는 식단을 즐겨찾기하세요!"
)

# 2. 알레르기 매핑 테이블
ALLERGY_MAP = {
    1: "난류",
    2: "우유",
    3: "메밀",
    4: "땅콩",
    5: "대두",
    6: "밀",
    7: "고등어",
    8: "게",
    9: "새우",
    10: "돼지고기",
    11: "복숭아",
    12: "토마토",
    13: "아황산류",
    14: "호두",
    15: "닭고기",
    16: "쇠고기",
    17: "오징어",
    18: "조개류(굴/전복/홍합 포함)",
    19: "잣",
}


def replace_allergy_codes(dish_text, convert_to_text=True):
    """메뉴명 뒤의 알레르기 번호를 감지하여 한글 식재료명으로 치환합니다."""
    if not convert_to_text or not dish_text:
        return dish_text

    def convert_match(match):
        raw = match.group(0)
        nums = re.findall(r"\d+", raw)
        allergens = [
            ALLERGY_MAP[int(n)] for n in nums if int(n) in ALLERGY_MAP
        ]
        if allergens:
            return f" :orange[[{', '.join(allergens)}]]"
        return raw

    pattern = r"\(?(\d+\.)+\)?"
    return re.sub(pattern, convert_match, dish_text)


# 3. 사이드바 - 학교 설정 & 즐겨찾기
st.sidebar.header("⚙️ 학교 정보 설정")
office_code = st.sidebar.text_input(
    "시도교육청코드",
    value="T10",
    help="기본값: 제주특별자치도교육청(T10)",
)
school_code = st.sidebar.text_input(
    "표준학교코드", value="9290088", help="기본값: 제주중앙고등학교(9290088)"
)

st.sidebar.markdown("---")
st.sidebar.subheader("🍽️ 알레르기 표시 설정")
show_allergen_names = st.sidebar.toggle(
    "알레르기 식품명으로 변환",
    value=True,
    help="체크 시 숫자 대신 [난류, 대두] 형태로 변환하여 표시합니다.",
)

with st.sidebar.expander("📖 나이스 알레르기 번호 안내표"):
    table_md = "\n".join([f"- **{k}번**: {v}" for k, v in ALLERGY_MAP.items()])
    st.markdown(table_md)

# 즐겨찾기 세션 상태 초기화
if "favorites" not in st.session_state:
    st.session_state.favorites = {}

# 사이드바 즐겨찾기 관리
st.sidebar.markdown("---")
st.sidebar.subheader("⭐ 즐겨찾기 식단 목록")
if not st.session_state.favorites:
    st.sidebar.caption("등록된 즐겨찾기가 없습니다.")
else:
    for fav_date in sorted(st.session_state.favorites.keys()):
        fav_data = st.session_state.favorites[fav_date]
        with st.sidebar.expander(f"⭐ {fav_date}"):
            for m_type, m_info in fav_data.items():
                st.markdown(f"**[{m_type}]** ({m_info['cal']})")
                for item in m_info["dishes"]:
                    st.markdown(f"- {item}")
            if st.button(f"삭제 ({fav_date})", key=f"del_{fav_date}"):
                del st.session_state.favorites[fav_date]
                st.rerun()

# 4. 상단 날짜 및 필터 선택
today = datetime.date.today()
col_y, col_m, col_filter = st.columns([1, 1, 2])
with col_y:
    year = st.selectbox(
        "연도 선택",
        options=list(range(today.year - 1, today.year + 2)),
        index=1,
    )
with col_m:
    month = st.selectbox(
        "월 선택", options=list(range(1, 13)), index=today.month - 1
    )
with col_filter:
    meal_filter = st.radio(
        "급식 종류 선택",
        options=["전체 보기", "중식만 보기", "석식만 보기"],
        index=0,
        horizontal=True,
    )


# 5. API 데이터 호출 함수
def fetch_monthly_meals(key, ofcdc_code, schul_code, yr, mo):
    _, last_day = calendar.monthrange(yr, mo)
    from_ymd = f"{yr}{mo:02d}01"
    to_ymd = f"{yr}{mo:02d}{last_day:02d}"

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": ofcdc_code,
        "SD_SCHUL_CODE": schul_code,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd,
    }
    response = requests.get(url, params=params, timeout=7)
    return response.json()


if "NEIS_KEY" not in st.secrets:
    st.error("⚠️ Streamlit Secrets에 `NEIS_KEY`가 설정되어 있지 않습니다.")
    st.stop()

neis_key = st.secrets["NEIS_KEY"]

# 데이터 파싱 함수 및 개별 카드 렌더링 함수
def render_meal_card(ymd_str, date_label, day_meals, is_today):
    """급식 카드 한 장을 생성하는 공통 함수"""
    is_fav = ymd_str in st.session_state.favorites
    star_prefix = "⭐ " if is_fav else ""

    with st.container(border=True):
        # 상단 날짜 및 즐겨찾기 토글 버튼
        col_title, col_btn = st.columns([3, 1])
        with col_title:
            if is_today:
                st.markdown(
                    f"**{star_prefix}{date_label}** :orange-background[**TODAY**]"
                )
            else:
                st.markdown(f"**{star_prefix}{date_label}**")
        with col_btn:
            if day_meals:
                btn_label = "★ 해제" if is_fav else "☆ 추가"
                if st.button(btn_label, key=f"fav_btn_{ymd_str}"):
                    if is_fav:
                        del st.session_state.favorites[ymd_str]
                    else:
                        st.session_state.favorites[ymd_str] = day_meals
                    st.rerun()

        st.divider()

        if not day_meals:
            st.caption("급식 없음 (휴업/방학)")
            return

        displayed_count = 0

        # 중식 출력
        if (
            meal_filter in ["전체 보기", "중식만 보기"]
            and "중식" in day_meals
        ):
            displayed_count += 1
            st.markdown(":blue[**🥣 중식**]")
            for dish in day_meals["중식"]["dishes"]:
                st.markdown(
                    f"<span style='font-size:0.85rem;'>• {dish}</span>",
                    unsafe_allow_html=True,
                )
            st.caption(f"⚡ 칼로리: {day_meals['중식']['cal']}")

        # 석식 출력
        if (
            meal_filter in ["전체 보기", "석식만 보기"]
            and "석식" in day_meals
        ):
            if displayed_count > 0:
                st.write("")
            displayed_count += 1
            st.markdown(":red[**🌙 석식**]")
            for dish in day_meals["석식"]["dishes"]:
                st.markdown(
                    f"<span style='font-size:0.85rem;'>• {dish}</span>",
                    unsafe_allow_html=True,
                )
            st.caption(f"⚡ 칼로리: {day_meals['석식']['cal']}")

        # 기타 (조식 등)
        if meal_filter == "전체 보기":
            for m_type, m_data in day_meals.items():
                if m_type not in ["중식", "석식"]:
                    if displayed_count > 0:
                        st.write("")
                    displayed_count += 1
                    st.markdown(f":green[**🍴 {m_type}**]")
                    for dish in m_data["dishes"]:
                        st.markdown(
                            f"<span style='font-size:0.85rem;'>• {dish}</span>",
                            unsafe_allow_html=True,
                        )
                    st.caption(f"⚡ 칼로리: {m_data['cal']}")

        if displayed_count == 0:
            st.caption("해당 식단 없음")


# 6. 데이터 로드 및 탭 화면 구성
try:
    with st.spinner(f"{year}년 {month}월 급식 정보를 불러오는 중..."):
        res_data = fetch_monthly_meals(
            neis_key, office_code, school_code, year, month
        )

    # meal_dict 구조: {'YYYYMMDD': {'중식': {'dishes': [...], 'cal': '800.5 kcal'}, ...}}
    meal_dict = {}
    if "mealServiceDietInfo" in res_data:
        rows = res_data["mealServiceDietInfo"][1]["row"]
        for row in rows:
            ymd = row.get("MLSV_YMD")
            meal_type = row.get("MMEAL_SC_NM", "급식")
            dish = row.get("DDISH_NM", "")
            cal_info = row.get("CAL_INFO", "정보 없음")

            formatted_dish = replace_allergy_codes(
                dish, convert_to_text=show_allergen_names
            )
            dish_lines = [
                d.strip()
                for d in formatted_dish.replace("<br/>", "\n").split("\n")
                if d.strip()
            ]

            meal_dict.setdefault(ymd, {})[meal_type] = {
                "dishes": dish_lines,
                "cal": cal_info,
            }

    # 탭 구성: 월별, 주별, 일별
    tab_month, tab_week, tab_day = st.tabs(
        ["🗓️ 월별 보기", "📆 주별 보기", "📌 일별 보기"]
    )

    month_cal = calendar.monthcalendar(year, month)
    weekdays_kr = ["월", "화", "수", "목", "금"]

    # ------------------ [1] 월별 보기 ------------------
    with tab_month:
        st.markdown("---")
        for week in month_cal:
            cols = st.columns(5)
            has_school_day = False

            for i in range(5):
                day = week[i]
                with cols[i]:
                    if day == 0:
                        st.empty()
                    else:
                        has_school_day = True
                        ymd_str = f"{year}{month:02d}{day:02d}"
                        day_meals = meal_dict.get(ymd_str, {})
                        is_today = (
                            year == today.year
                            and month == today.month
                            and day == today.day
                        )
                        date_label = f"{month}월 {day}일 ({weekdays_kr[i]})"

                        render_meal_card(
                            ymd_str, date_label, day_meals, is_today
                        )

            if has_school_day:
                st.write("")

    # ------------------ [2] 주별 보기 ------------------
    with tab_week:
        st.markdown("---")
        week_options = [f"{i+1}주차" for i in range(len(month_cal))]
        selected_week_idx = st.selectbox(
            "주차 선택",
            range(len(month_cal)),
            format_func=lambda x: week_options[x],
        )

        selected_week = month_cal[selected_week_idx]
        cols = st.columns(5)

        for i in range(5):
            day = selected_week[i]
            with cols[i]:
                if day == 0:
                    st.info("해당 일은 이번 달에 포함되지 않습니다.")
                else:
                    ymd_str = f"{year}{month:02d}{day:02d}"
                    day_meals = meal_dict.get(ymd_str, {})
                    is_today = (
                        year == today.year
                        and month == today.month
                        and day == today.day
                    )
                    date_label = f"{month}월 {day}일 ({weekdays_kr[i]})"

                    render_meal_card(ymd_str, date_label, day_meals, is_today)

    # ------------------ [3] 일별 보기 ------------------
    with tab_day:
        st.markdown("---")
        _, last_day = calendar.monthrange(year, month)
        selected_day = st.slider("날짜 선택 (일)", 1, last_day, min(today.day, last_day))

        ymd_str = f"{year}{month:02d}{selected_day:02d}"
        day_meals = meal_dict.get(ymd_str, {})
        is_today = (
            year == today.year
            and month == today.month
            and selected_day == today.day
        )

        dt_obj = datetime.date(year, month, selected_day)
        w_idx = dt_obj.weekday()

        if w_idx >= 5:
            st.warning("선택하신 날짜는 주말입니다.")
        else:
            date_label = f"{year}년 {month}월 {selected_day}일 ({weekdays_kr[w_idx]})"
            # 일별 보기 화면에서는 조금 더 크게 표현
            col_center, _ = st.columns([2, 1])
            with col_center:
                render_meal_card(ymd_str, date_label, day_meals, is_today)

except requests.exceptions.RequestException as e:
    st.error(f"⚠️ 나이스 API 통신 오류: 네트워크 상태를 확인해 주세요. ({e})")
except Exception as e:
    st.error(f"⚠️ 화면 구성 중 오류가 발생했습니다: {e}")
