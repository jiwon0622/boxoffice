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
df['순위변동'] = df['rankInten'].apply(get_rank_change_str)  # 👈 이 부분이 누락되었던 곳입니다!

display_df = pd.DataFrame({
    "순위": df["rank"],
    "변동": df["순위변동"],
    "영화명": df["영화명(가공)"],
    "개봉일": df["openDt"],
    "관객수": df["audiCnt"].apply(lambda x: f"{x:,}"),
    "누적관객": df["audiAcc"].apply(lambda x: f"{x:,}"),
    "스크린수": df["scrnCnt"].apply(lambda x: f"{x:,}")
})

st.dataframe(
    display_df,
    hide_index=True
)
