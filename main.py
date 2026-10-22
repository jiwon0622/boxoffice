import datetime
import pytz
import requests
import pandas as pd
import streamlit as st
import urllib.parse
import plotly.express as px  # 검정 배경 & 빨간색 막대 그래프용

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

# --- [UI 커스텀 디자인: 조명 이펙트 + 검정 배경 + 예쁜 폰트] ---
st.markdown("""
    <style>
    /* 1. 웹폰트 적용 (Pretendard) */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, [class*="css"], .stMarkdown, button, input {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif !important;
    }

    /* 2. 메인 페이지 검정 배경 및 상단 노란색 조명 그라데이션 이펙트 */
    .stApp {
        background: radial-gradient(circle at 50% -20%, rgba(255, 215, 0, 0.35) 0%, rgba(0, 0, 0, 0.95) 55%, #000000 100%) !important;
        background-attachment: fixed !important;
        color: #FFFFFF !important;
    }

    /* 3. 사이드바 어두운 디자인 */
    [data-testid="stSidebar"] {
        background-color: #111111 !important;
        border-right: 1px solid #222222 !important;
    }

    /* 4. 지표 카드 (Metric) 스팟라이트 스타일 */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.04) !important;
        padding: 18px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 215, 0, 0.2) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
        backdrop-filter: blur(10px) !important;
    }

    /* 5. 텍스트 색상 및 강조 효과 */
    h1, h2, h3, h4, h5, h6, p, label {
        color: #FFFFFF !important;
    }

    stCaption {
        color: #CCCCCC !important;
    }

    /* 구분선 색상 */
    hr {
        border-color: rgba(255, 215, 0, 0.3) !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 일별 박스오피스 조회")

# 2. 한국 표준시(KST) 기준 날짜 계산 및 선택
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
today = now_kst.date()
yesterday = today - datetime.timedelta(days=1)

st.sidebar.header("🔍 날짜 선택")
selected_date = st.sidebar.date_input(
    label="조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday,
    min_value=datetime.date(2004, 1, 1)
)

target_dt = selected_date.strftime("%Y%m%d")
display_dt = selected_date.strftime("%Y년 %m월 %d일")

st.caption(f"📅 조회 기준일: **{display_dt}**")

# 3. Streamlit Secrets 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ API 인증키(KOBIS_KEY)가 설정되지 않았습니다.")
    st.info("Streamlit Cloud의 Secrets 설정에서 KOBIS_KEY를 추가해 주세요.")
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 4. API 데이터 호출 (캐싱 적용)
@st.cache_data(ttl=3600)
def fetch_box_office(key: str, target_date: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {"key": key, "targetDt": target_date}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json(), None
    except Exception as e:
        return None, str(e)

data, error_msg = fetch_box_office(api_key, target_dt)

# 5. 예외 및 오류 처리
if error_msg:
    st.error("❌ KOBIS 서버와 통신 중 연결 오류가 발생했습니다.")
    st.warning(f"상세 오류: {error_msg}")
    st.stop()

if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("❌ KOBIS API 오류가 발생했습니다.")
    st.warning(f"메시지: {fault.get('message')}")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 선택하신 날짜의 박스오피스 데이터가 존재하지 않습니다.")
    st.info("그날은 아직 집계 전입니다.")
    st.stop()

# 6. 데이터 전처리 (숫자 컬럼 변환)
df = pd.DataFrame(daily_list)

numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
