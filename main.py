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

# 7. 1위 영화 지표 카드 (Metrics) 및 나무위키 이동 링크 버튼
top_1 = df.iloc[0]

raw_top_1_name = top_1['movieNm']
top_1_name = raw_top_1_name
if top_1['audiAcc'] >= 1_000_000:
    top_1_name += " 🏆"

# 제목과 나무위키 이동 버튼을 한 줄에 배치
head_col1, head_col2 = st.columns([4, 1])

with head_col1:
    st.subheader(f"🥇 1위 영화: {top_1_name}")

with head_col2:
    # 나무위키 검색 URL 생성 (영화 제목에 특수문자 등이 포함될 수 있으므로 URL 인코딩 적용)
    encoded_movie_name = urllib.parse.quote(f"{raw_top_1_name} (영화)")
    namu_url = f"https://namu.wiki/w/{encoded_movie_name}"
    
    # 별모양 나무위키 링크 버튼
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
    st.metric(
        label="당일 관객수",
        value=f"{top_1['audiCnt']:,} 명",
        delta=delta_str
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{top_1['audiAcc']:,} 명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{top_1['scrnCnt']:,} 개"
    )

st.divider()

# 8. 관객수 상위 5편 막대그래프 (안정적인 데이터 가공 방식)
st.subheader("📊 관객수 TOP 5")

top_5_df = df.head(5).copy()
chart_df = pd.DataFrame({
    "영화명": top_5_df["movieNm"],
    "관객수": top_5_df["audiCnt"]
}).set_index("영화명")

st.bar_chart(chart_df)

st.divider()

# 9. 전체 박스오피스 순위 표 (안전한 컬럼 생성 및 서식 적용)
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
df['순위변동'] =
