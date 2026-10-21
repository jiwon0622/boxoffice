import datetime
import pytz
import requests
import pandas as pd
import streamlit as st

# 1. 페이지 기본 설정 (넓은 화면 레이아웃)
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스 조회")

# 2. 한국 표준시(KST) 기준 날짜 계산
# 오늘 날짜와 가장 늦게 조회 가능한 날짜(어제)를 계산합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
today = now_kst.date()
yesterday = today - datetime.timedelta(days=1)

# 3. 사이드바 날짜 선택 기능 추가
# 선택 가능한 최대 날짜(max_value)를 어제로 제한합니다.
st.sidebar.header("🔍 날짜 선택")
selected_date = st.sidebar.date_input(
    label="조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    min_value=datetime.date(2004, 1, 1)  # KOBIS 데이터 시작 시점 근처
)

# API 요청용 날짜 문자열 (YYYYMMDD)
target_dt = selected_date.strftime("%Y%m%d")
# 화면 표시용 날짜 문자열 (YYYY년 MM월 DD일)
display_dt = selected_date.strftime("%Y년 %m월 %d일")

st.caption(f"📅 조회 기준일: **{display_dt}**")

# 4. Streamlit Secrets에서 API 인증키 불러오기
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ API 인증키(KOBIS_KEY)가 설정되지 않았습니다.")
    st.info(
        "**[확인 가이드]**\n"
        "1. 로컬 개발 시: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = '발급받은키'`를 작성해 주세요.\n"
        "2. 스트림릿 클라우드 배포 시: App Settings > Secrets 메뉴에 `KOBIS_KEY`를 추가해 주세요."
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 5. KOBIS OpenAPI 호출 함수 (캐싱 적용)
@st.cache_data(ttl=3600)
def fetch_box_office(key: str, target_date: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": key,
        "targetDt": target_date
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except Exception as e:
        return None, str(e)

data, error_msg = fetch_box_office(api_key, target_dt)

# 6. 예외 상황 및 오류 처리

# (1) 네트워크 및 서버 통신 오류
if error_msg:
    st.error("❌ KOBIS 서버와 통신 중 연결 오류가 발생했습니다.")
    st.warning(f"상세 오류: {error_msg}")
    st.info(
        "**[확인 가이드]**\n"
        "1. 인터넷 연결 상태를 확인해 주세요.\n"
        "2. KOBIS 서비스 장애 여부를 확인해 주세요."
    )
    st.stop()

# (2) API 자체 오류 메시지 (faultInfo) 처리
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("❌ KOBIS API 오류가 발생했습니다.")
    st.warning(f"코드: {fault.get('errorCode')} | 메시지: {fault.get('message')}")
    st.info(
        "**[확인 가이드]**\n"
        "1. Secrets에 등록된 `KOBIS_KEY`가 정확한지 확인해 주세요.\n"
        "2. KOBIS 개발자센터에서 일일 API 호출 한도를 초과했는지 확인해 주세요."
    )
    st.stop()

# (3) 응답 데이터에 영화 목록이 없거나 비어있는 경우
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 선택하신 날짜의 박스오피스 데이터가 존재하지 않습니다.")
    st.info("그날은 아직 집계 전입니다.")
    st.stop()

# 7. 데이터 변환 및 전처리
df = pd.DataFrame(daily_list)

# 문자열 숫자를 정수형(int)으로 변환
numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 8. 1위 영화 지표 카드 표시 (Metrics)
top_1 = df.iloc[0]

# 100만 관객 돌파 시 🏆 표시 붙이기
top_1_name = top_1['movieNm']
if top_1['audiAcc'] >= 1_000_000:
    top_1_name += " 🏆"

st.subheader(f"🥇 1위 영화: {top_1_name}")

col
