import datetime
import pytz
import requests
import pandas as pd
import streamlit as st

# 1. 페이지 기본 설정 (넓은 화면 레이아웃)
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 일별 박스오피스")

# 2. 한국 표준시(KST) 기준 '어제' 날짜 계산
# 스트림릿 클라우드 서버 시계(UTC)와 상관없이 항상 한국 시간 기준으로 '어제'를 계산합니다.
kst = pytz.timezone("Asia/Seoul")
now_kst = datetime.datetime.now(kst)
yesterday = now_kst - datetime.timedelta(days=1)

# API 요청용 날짜 형식 (YYYYMMDD)
target_dt = yesterday.strftime("%Y%m%d")
# 화면 표시용 날짜 형식 (YYYY년 MM월 DD일)
display_dt = yesterday.strftime("%Y년 %m월 %d일")

st.caption(f"📅 기준일: {display_dt} (한국 표준시 기준 어제)")

# 3. Streamlit Secrets에서 API 인증키 불러오기
# secrets.toml 설정에 [KOBIS_KEY]가 등록되어 있어야 합니다.
if "KOBIS_KEY" not in st.secrets:
    st.error("❌ API 인증키(KOBIS_KEY)가 설정되지 않았습니다.")
    st.info(
        "**[확인 가이드]**\n"
        "1. 로컬 개발 시: `.streamlit/secrets.toml` 파일에 `KOBIS_KEY = '발급받은키'`를 작성해 주세요.\n"
        "2. 스트림릿 클라우드 배포 시: App Settings > Secrets 메뉴에 `KOBIS_KEY`를 추가해 주세요."
    )
    st.stop()

api_key = st.secrets["KOBIS_KEY"]

# 4. KOBIS OpenAPI 호출 함수 (1시간 동안 데이터 캐싱)
@st.cache_data(ttl=3600)
def fetch_box_office(key: str, target_date: str):
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": key,
        "targetDt": target_date
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # HTTP 상태 코드가 200이 아닌 경우 예외 발생
        return response.json(), None
    except Exception as e:
        return None, str(e)

data, error_msg = fetch_box_office(api_key, target_dt)

# 5. 예외 상황 및 오류 처리

# (1) 네트워크 요청 자체 실패
if error_msg:
    st.error("❌ KOBIS 서버와 통신 중 연결 오류가 발생했습니다.")
    st.warning(f"상세 오류: {error_msg}")
    st.info(
        "**[확인 가이드]**\n"
        "1. 인터넷 연결 상태를 확인해 주세요.\n"
        "2. KOBIS 서비스 일시 장애 여부를 확인한 뒤 잠시 후 다시 시도해 주세요."
    )
    st.stop()

# (2) API에서 오류 응답(faultInfo)이 올 경우
# KOBIS API는 인증키 오류나 잘못된 변수인 경우에도 상태코드 200과 함께 faultInfo 객체를 보냅니다.
if "faultInfo" in data:
    fault = data["faultInfo"]
    st.error("❌ KOBIS API 인증 및 처리 오류가 발생했습니다.")
    st.warning(f"코드: {fault.get('errorCode')} | 메시지: {fault.get('message')}")
    st.info(
        "**[확인 가이드]**\n"
        "1. Secrets에 저장된 `KOBIS_KEY`가 정확한지 확인해 주세요.\n"
        "2. KOBIS 개발자센터에서 일일 API 호출 허용 한도를 초과하지 않았는지 확인해 주세요."
    )
    st.stop()

# (3) 응답에 영화 목록이 없거나 비어있는 경우
box_office_result = data.get("boxOfficeResult", {})
daily_list = box_office_result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning("⚠️ 어제 날짜의 박스오피스 데이터가 비어 있습니다.")
    st.info(
        "**[확인 가이드]**\n"
        "1. KOBIS의 일별 집계 반영 시점 이전일 수 있습니다.\n"
        "2. 잠시 후 다시 조회를 시도해 주세요."
    )
    st.stop()

# 6. 데이터 변환 및 전처리
# KOBIS 응답 데이터는 모든 숫자 값이 문자열(string)로 반환되므로 정수형(int)으로 변환합니다.
df = pd.DataFrame(daily_list)

numeric_columns = ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 7. 1위 영화 지표 카드 표시 (Metric 3장)
top_1 = df.iloc[0]

st.subheader(f"🏆 1위 영화: {top_1['movieNm']}")

col1, col2, col3 = st.columns(3)

# 순위 증감 레이블 설정
rank_change = top_1['rankInten']
if rank_change > 0:
    delta_str = f"▲ {rank_change}"
elif rank_change < 0:
    delta_str = f"▼ {abs(rank_change)}"
else:
    delta_str = "변동 없음"

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{top_1['audiCnt']:,} 명",
        delta=f"전일 대비 순위 {delta_str}"
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

# 8. 관객수 상위 5편 막대그래프 시각화
st.subheader("📊 관객수 TOP 5")
top_5_df = df.head(5).copy()

# 막대그래프 표시용 데이터 구성 (영화명을 인덱스로 설정)
chart_data = top_5_df.set_index("movieNm")[["audiCnt"]]
chart_data.columns = ["관객수"]

st.bar_chart(chart_data)

st.divider()

# 9. 전체 박스오피스 순위 표 출력
st.subheader("📋 박스오피스 전체 순위")

# 요청사항에 명시된 필수 컬럼 선택 및 보기 좋은 한글 이름으로 변경
display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

# 숫자에 천 단위 쉼표(,) 포맷 적용
formatted_df = display_df.style.format({
    "관객수": "{:,}",
    "누적관객": "{:,}",
    "스크린수": "{:,}"
})

st.dataframe(
    formatted_df,
    use_container_width=True,
    hide_index=True
)
