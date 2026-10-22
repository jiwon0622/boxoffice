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

# 영화 제목 기반 포스터 이미지 검색 함수 (KMDB / TMDB / Wikipedia API 활용)
@st.cache_data(ttl=86400)
def fetch_poster_url(movie_name: str):
    """
    영화 제목으로 포스터 이미지 URL을 검색합니다.
    KMDB API 키가 secrets에 있다면 KMDB를 우선 활용하고,
    없다면 위키백과/공공 오픈 API를 검색하여 이미지 URL을 반환합니다.
    """
    clean_name = movie_name.replace(" 🏆", "").strip()

    # 1. KMDB API 키가 Secrets에 설정되어 있는 경우
    if "KMDB_KEY" in st.secrets:
        try:
            kmdb_url = "http://api.koreafilm.or.kr/openapi-data2/wisenut/search_api/search_xml.jsp"
            params = {
                "collection": "kmdb_new2",
                "detail": "Y",
                "title": clean_name,
                "ServiceKey": st.secrets["KMDB_KEY"]
            }
            res = requests.get(kmdb_url, params=params, timeout=5)
            # KMDB 포스터 파싱 (posters 컬럼)
            if res.status_code == 200 and "posters" in res.text:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(res.content)
                for item in root.iter("row"):
                    posters = item.findtext("posters")
                    if posters:
                        poster_list = posters.split("|")
                        if poster_list and poster_list[0]:
                            return poster_list[0]
        except Exception:
            pass

    # 2. Wikipedia API를 통한 포스터 검색 (API 키 없이 자동 검색 가능)
    try:
        wiki_url = f"https://ko.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(clean_name)}&prop=pageimages&format=json&pithumbsize=500"
        res = requests.get(wiki_url, timeout=5).json()
        pages = res.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if "thumbnail" in page_data:
                return page_data["thumbnail"]["source"]
    except Exception:
        pass

    return None

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

# 7. 1위 영화 지표 카드 (Metrics) 및 별모양 포스터 버튼
top_1 = df.iloc[0]

raw_top_1_name = top_1['movieNm']
top_1_name = raw_top_1_name
if top_1['audiAcc'] >= 1_000_000:
    top_1_name += " 🏆"

# 제목과 별모양 버튼을 한 줄에 배치
head_col1, head_col2 = st.columns([4, 1])

with head_col1:
    st.subheader(f"🥇 1위 영화: {top_1_name}")

with head_col2:
    # 별모양 포스터 토글 버튼
    show_poster = st.button("⭐ 포스터 보기", key="poster_btn")

# 별모양 버튼 클릭 시 포스터 표시
if show_poster:
    with st.spinner("🖼️ 포스터를 불러오는 중입니다..."):
        poster_url = fetch_poster_url(raw_top_1_name)
        if poster_url:
            st.image(poster_url, caption=f"<{raw_top_1_name}> 포스터", width=300)
        else:
            st.info(f"💡 '{raw_top_1_name}'의 포스터 이미지를 찾지 못했습니다.")

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
