import calendar
import datetime
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 알레르기 정보 정의
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="학교 급식 달력",
    page_icon="🍱",
    layout="wide",
)

# NEIS API 기준 알레르기 번호 매핑 (1~19번)
ALLERGY_MAP = {
    "1": "난류",
    "2": "우유",
    "3": "메밀",
    "4": "땅콩",
    "5": "대두",
    "6": "밀",
    "7": "고등어",
    "8": "게",
    "9": "새우",
    "10": "돼지고기",
    "11": "복숭아",
    "12": "토마토",
    "13": "아황산류",
    "14": "호두",
    "15": "닭고기",
    "16": "쇠고기",
    "17": "오징어",
    "18": "조개류",
    "19": "잣",
}


# -----------------------------------------------------------------------------
# 2. 헬퍼 함수 정의
# -----------------------------------------------------------------------------
def convert_allergy_numbers(menu_str, convert_flag):
    """메뉴 문자열에서 알레르기 번호(예: 1.2.5.)를 실제 식재료 이름으로 변환하거나 정리하는 함수"""
    if not menu_str:
        return ""

    # 문자열에 포함된 HTML 줄바꿈 태그(<br/>)를 일반 줄바꿈으로 변경
    clean_menu = menu_str.replace("<br/>", "\n")

    if not convert_flag:
        return clean_menu

    # 알레르기 번호(1~19)를 이름으로 변환
    import re

    def replace_match(match):
        numbers = match.group(0).strip("()").split(".")
        converted = []
        for num in numbers:
            if num in ALLERGY_MAP:
                converted.append(ALLERGY_MAP[num])
            elif num:
                converted.append(num)
        return f"({','.join(converted)})" if converted else ""

    # 괄호 안의 숫자.숫자 패턴 찾아서 변환 (예: (1.2.5) -> (난류,우유,대두))
    pattern = r"\([\d\.]+\)"
    return re.sub(pattern, replace_match, clean_menu)


@st.cache_data(ttl=3600)
def fetch_meal_data(office_code, school_code, from_ymd, to_ymd, api_key):
    """NEIS API를 호출하여 해당 기간의 급식 데이터를 가져오는 함수"""
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # HTTP 에러 발생 시 예외 호출
        data = response.json()

        # API 응답 결과 확인
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"], None
        elif "RESULT" in data:
            # 데이터가 없는 경우 (예: 방학, 휴교 등)
            code = data["RESULT"].get("CODE")
            if code == "INFO-200":  # 해당 조건의 데이터가 없는 경우
                return [], None
            return None, f"API 안내 메시지: {data['RESULT'].get('MESSAGE')}"
        else:
            return None, "알 수 없는 API 응답 구조입니다."

    except requests.exceptions.RequestException as e:
        return None, f"API 통신 오류가 발생했습니다: {e}"
    except Exception as e:
        return None, f"데이터 처리 중 오류가 발생했습니다: {e}"


# -----------------------------------------------------------------------------
# 3. 비밀키(API KEY) 검증
# -----------------------------------------------------------------------------
if "NEIS_KEY" not in st.secrets:
    st.error("🔑 API 키가 설정되지 않았습니다.")
    st.info(
        "`.streamlit/secrets.toml` 파일에 `NEIS_KEY = '발급받은_키'` 형태로 등록해 주세요."
    )
    st.stop()

neis_key = st.secrets["NEIS_KEY"]


# -----------------------------------------------------------------------------
# 4. 사이드바 구성
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 학교 및 화면 설정")

    # 시도교육청코드 및 학교코드 입력 box (기본값: 서울특별시교육청 / 서울고등학교)
    office_code = st.text_input(
        "시도교육청코드",
        value="B10",
        help="예: 서울 B10, 경기 J10, 부산 C10 등",
    )
    school_code = st.text_input(
        "표준학교코드", value="7010536", help="7자리 학교 고유 코드"
    )

    st.divider()

    # 알레르기 변환 옵션
    convert_allergy = st.toggle("알레르기 식품명으로 변환", value=True)

    # 알레르기 대응표 (접기/편히 기능)
    with st.expander("ℹ️ 알레르기 번호 안내표"):
        st.markdown(
            """
        | 번호 | 식재료 | 번호 | 식재료 |
        |---|---|---|---|
        | 1 | 난류 | 11 | 복숭아 |
        | 2 | 우유 | 12 | 토마토 |
        | 3 | 메밀 | 13 | 아황산류 |
        | 4 | 땅콩 | 14 | 호두 |
        | 5 | 대두 | 15 | 닭고기 |
        | 6 | 밀 | 16 | 쇠고기 |
        | 7 | 고등어 | 17 | 오징어 |
        | 8 | 게 | 18 | 조개류 |
        | 9 | 새우 | 19 | 잣 |
        | 10 | 돼지고기 | | |
        """
        )


# -----------------------------------------------------------------------------
# 5. 메인 화면 - 상단 설정 (연도/월/급식종류 선택)
# -----------------------------------------------------------------------------
st.title("🍱 우리 학교 한 달 급식 달력")

today = datetime.date.today()

col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    selected_year = st.selectbox(
        "연도 선택", range(today.year - 1, today.year + 2), index=1
    )

with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=today.month - 1)

with col3:
    meal_type_filter = st.radio(
        "급식 종류",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True,
    )

# -----------------------------------------------------------------------------
# 6. API 데이터 조회
# -----------------------------------------------------------------------------
# 조회할 달의 시작일과 마지막일 계산
_, last_day = calendar.monthrange(selected_year, selected_month)
from_ymd = f"{selected_year}{selected_month:02d}01"
to_ymd = f"{selected_year}{selected_month:02d}{last_day:02d}"

# 급식 데이터 조회
meal_rows, error_msg = fetch_meal_data(
    office_code, school_code, from_ymd, to_ymd, neis_key
)

if error_msg:
    st.error(f"🚨 {error_msg}")
    st.stop()

# 날짜별 / 급식종류별 데이터 정리 (예: {'20260901': {'중식': '메뉴내용...'}})
meal_dict = {}
if meal_rows:
    for row in meal_rows:
        ymd = row["MLSV_YMD"]
        meal_name = row["MMEAL_SC_NM"]  # 조식, 중식, 석식
        dish_name = row["DDISH_NM"]

        if ymd not in meal_dict:
            meal_dict[ymd] = {}
        meal_dict[ymd][meal_name] = dish_name


# -----------------------------------------------------------------------------
# 7. 달력 화면 구성 (월~금 주간 달력)
# -----------------------------------------------------------------------------
st.subheader(f"📅 {selected_year}년 {selected_month}월 급식 식단표")

# calendar.monthcalendar는 해당 월의 주차별 날짜(월~일) 리스트를 생성합니다.
# [0, 0, 1, 2, 3, 4, 5] -> 0은 이전/다음 달 날짜
month_cal = calendar.monthcalendar(selected_year, selected_month)

try:
    for week in month_cal:
        # 월요일(0)부터 금요일(4)까지만 슬라이싱 (주말 제외)
        workdays = week[:5]

        # 평일 중에 하루라도 이번 달 날짜가 포함되어 있으면 행을 출력
        if any(day != 0 for day in workdays):
            cols = st.columns(5)

            for idx, day in enumerate(workdays):
                with cols[idx]:
                    if day == 0:
                        # 이번 달 날짜가 아닌 경우 빈 카드
                        st.empty()
                    else:
                        current_date = datetime.date(
                            selected_year, selected_month, day
                        )
                        date_str = current_date.strftime("%Y%m%d")

                        # 오늘 날짜 여부 체크
                        is_today = current_date == today
                        today_badge = (
                            " <span style='color:red; font-weight:bold;'>[TODAY]</span>"
                            if is_today
                            else ""
                        )

                        # 요일 이름
                        weekdays_ko = ["월", "화", "수", "목", "금"]
                        weekday_name = weekdays_ko[idx]

                        # 날짜 헤더 영역
                        header_html = f"<b>{selected_month}/{day} ({weekday_name})</b>{today_badge}"

                        # 카드 형태 구현을 위한 컨테이너 생성
                        with st.container(border=True):
                            st.markdown(header_html, unsafe_allow_html=True)
                            st.markdown("---")

                            # 해당 날짜의 급식 데이터 유무 검사
                            if date_str not in meal_dict or not meal_dict[
                                date_str
                            ]:
                                st.caption("급식 없음")
                            else:
                                day_meals = meal_dict[date_str]
                                displayed_count = 0

                                # 급식 종류별 표시
                                for meal_type, menu_raw in day_meals.items():
                                    # 사용자 필터 적용
                                    if (
                                        meal_type_filter == "중식만 보기"
                                        and meal_type != "중식"
                                    ):
                                        continue
                                    if (
                                        meal_type_filter == "석식만 보기"
                                        and meal_type != "석식"
                                    ):
                                        continue

                                    displayed_count += 1

                                    # 알레르기 번호 변환 적용
                                    formatted_menu = convert_allergy_numbers(
                                        menu_raw, convert_allergy
                                    )

                                    # 급식 종류별 색상 배지 설정
                                    if meal_type == "중식":
                                        badge = "🔵 **[중식]**"
                                    elif meal_type == "석식":
                                        badge = "🔴 **[석식]**"
                                    else:
                                        badge = "🟢 **[조식/기타]**"

                                    st.markdown(badge)
                                    st.text(formatted_menu)

                                # 필터링 조건에 부합하는 급식이 없을 경우
                                if displayed_count == 0:
                                    st.caption("해당 식단 없음")

except Exception as e:
    st.error(f"🖼️ 화면을 그리는 도중 오류가 발생했습니다: {e}")
