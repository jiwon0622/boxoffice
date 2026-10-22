import datetime
import pytz
import requests
import pandas as pd
import streamlit as st
import urllib.parse

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

# --- [UI 디자인: 검정 배경 + 상단 노란 조명 + 프리텐다드 폰트] ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, [class*="css"], .stMarkdown, button, input {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif !important;
    }

    .stApp {
        background: radial-gradient(circle at 50% -20%, rgba(255, 215, 0, 0.35) 0%, rgba(0, 0, 0, 0.95) 55%, #000000 100%) !important;
        background-attachment: fixed !important;
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] {
        background-color: #111111 !important;
        border-right: 1px solid #222222 !important;
    }

    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.05) !important;
        padding: 18px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 215, 0, 0.2) !important;
    }

    h1, h2, h3, h4, h5, h6, p, label {
        color: #FFFFFF !important;
    }

    hr {
        border-color: rgba(255, 215, 0, 0.3) !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 일별 박스오피스 조회")

# 2. 날짜 선택 Sidebar
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

# 3. Secrets 키 확인
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ API 인증키(KOBIS_KEY)가 Streamlit Secrets에 설정되지 않았습니다.")
    st.info("Streamlit Cloud 하단의 'Manage app' > 'Secrets' 설정에서 KOBIS_KEY를 등록해 주세요.")
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

# 5. 예외 발생 시 구체적인 메시지 출력
if error_msg:
    st.error("❌ KOBIS API 호출 실패")
    st.code(error_msg)
    st.stop()

if not data:
    st.error("❌ API 응답 데이터가 비어 있습니다.")
    st.stop()

if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error(f"❌ KOBIS API 에러: {fault.get('message', '알 수 없는 오류')}")
    st.stop()

box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 선택하신 날짜의 박스오피스 데이터가 존재하지 않거나 집계 전입니다.")
    st.stop()

# 6. 데이터 전처리
df = pd.DataFrame(daily_list)

numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 7. 1위 영화 지표 카드 (Metrics)
top_1 = df.iloc[0]

raw_top_1_name = top_1['movieNm']
top_1_name = raw_top_1_name
if top_1['audiAcc'] >= 1_000_000:
    top_1_name += " 🏆"

head_col1, head_col2 = st.columns([4, 1])

with head_col1:
    st.subheader(f"🥇 1위 영화: {top_1_name}")

with head_col2:
    encoded_movie_name = urllib.parse.quote(raw_top_1_name)
    namu_url = f"https://namu.wiki/go/{encoded_movie_name}"
    st.link_button("⭐ 나무위키 보기", namu_url)

col1, col2, col3 = st.columns(3)

rank_change = top_1['rankInten']
if rank_change > 0:
    delta_str = f"🔺 {rank_change} 상승"
elif rank_change < 0:
    delta_str = f"🔹 {abs(rank_change)} 하락"
else:
    delta_str = "변동 없음"

with col1:
    st.metric(label="당일 관객수", value=f"{top_1['audiCnt']:,} 명", delta=delta_str)

with col2:
    st.metric(label="누적 관객수", value=f"{top_1['audiAcc']:,} 명")

with col3:
    st.metric(label="스크린수", value=f"{top_1['scrnCnt']:,} 개")

st.divider()

# 8. 관객수 TOP 5 빨간색 막대그래프
st.subheader("📊 관객수 TOP 5")

top_5_df = df.head(5).copy()
chart_df = pd.DataFrame({
    "영화명": top_5_df["movieNm"],
    "관객수": top_5_df["audiCnt"]
}).set_index("영화명")

st.bar_chart(chart_df, color="#E50914")

st.divider()

# 9. 전체 박스오피스 순위 표
st.subheader("📋 전체 박스오피스 순위")

def get_display_movie_name(row):
    name = str(row['movieNm'])
    if row['audiAcc'] >= 1_000_000:
        name += " 🏆"
    return name

def get_rank_change_str(rank_inten):
    if rank_inten > 0:
        return f"🔺 {rank_inten}"
    elif rank_inten < 0:
        return f"🔹 {abs(rank_inten)}"
    return "-"

df['영화명(가공)'] = df.apply(get_display_movie_name, axis=1)
df['순위변동'] = df['rankInten'].apply(get_rank_change_str)

display_df = pd.DataFrame({
    "순위": df["rank"],
    "변동": df["순위변동"],
    "영화명": df["영화명(가공)"],
    "개봉일": df["openDt"],
    "관객수": df["audiCnt"].apply(lambda x: f"{x:,}"),
    "누적관객": df["audiAcc"].apply(lambda x: f"{x:,}"),
    "스크린수": df["scrnCnt"].apply(lambda x: f"{x:,}")
})

st.dataframe(display_df, hide_index=True)
