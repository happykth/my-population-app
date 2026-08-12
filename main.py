import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# -----------------------------------------------------------
# 페이지 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="우리 동네 인구 피라미드", page_icon="🏘️")

st.title("🏘️ 우리 동네 인구 피라미드")
st.write(
    "시도 → 시군구 → 동을 골라보세요. 선택한 동네의 나이별·성별 인구 구조를 "
    "인구 피라미드로 보여드릴게요 😊"
)

# -----------------------------------------------------------
# 1) 데이터 불러오기 (gz로 압축된 csv지만 pandas가 알아서 풀어줘요)
# -----------------------------------------------------------
DATA_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_URL, compression="gzip")
    return df


with st.spinner("데이터를 불러오는 중이에요... 잠시만 기다려주세요!"):
    df = load_data()

# -----------------------------------------------------------
# 2) 가장 최신 연도만 남기기
# -----------------------------------------------------------
latest_year = df["연도"].max()
df_latest = df[df["연도"] == latest_year].copy()

st.info(f"가장 최신 연도인 **{latest_year}년** 데이터를 사용할게요.")

# -----------------------------------------------------------
# 3) 나이 목록 만들기 (0세 ~ 100세 이상, 순서 고정!)
#    이 순서가 그래프의 세로축 순서와 그대로 이어져요.
# -----------------------------------------------------------
age_labels = [f"{i}세" for i in range(100)] + ["100세 이상"]

# 남_0세, 여_0세 ... 남_100세 이상, 여_100세 이상 형태의 열 이름을
# 위 age_labels 순서에 맞춰 미리 만들어둡니다.
male_cols = [f"남_{age}" for age in age_labels]
female_cols = [f"여_{age}" for age in age_labels]

# -----------------------------------------------------------
# 4) 시도 → 시군구 → 동 드롭다운 (선택할수록 목록이 좁혀져요)
# -----------------------------------------------------------
st.subheader("🔍 동네 선택하기")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df_latest["시도"].unique())
    selected_sido = st.selectbox("시도", sido_list)

# 선택한 시도에 속한 시군구만 추려서 보여줘요
df_sido = df_latest[df_latest["시도"] == selected_sido]

with col2:
    sigungu_list = sorted(df_sido["시군구"].unique())
    selected_sigungu = st.selectbox("시군구", sigungu_list)

# 선택한 시군구에 속한 동만 추려서 보여줘요
df_sigungu = df_sido[df_sido["시군구"] == selected_sigungu]

with col3:
    dong_list = sorted(df_sigungu["동"].unique())
    selected_dong = st.selectbox("동", dong_list)

# 최종적으로 선택된 동네 한 줄(row)을 가져옵니다.
row = df_sigungu[df_sigungu["동"] == selected_dong].iloc[0]

st.divider()

# -----------------------------------------------------------
# 5) 선택한 동네의 나이별 남/여 인구 뽑아내기
# -----------------------------------------------------------
male_values = row[male_cols].astype(int).to_numpy()
female_values = row[female_cols].astype(int).to_numpy()

# 남자는 피라미드 왼쪽에 두기 위해 값을 음수로 바꿔줍니다.
male_values_neg = -male_values

total_pop = male_values.sum() + female_values.sum()

st.subheader(f"📍 {selected_sido} {selected_sigungu} {selected_dong}")
st.write(f"총인구: **{total_pop:,}명** (남 {male_values.sum():,}명 · 여 {female_values.sum():,}명)")

# -----------------------------------------------------------
# 6) 인구 피라미드 그리기 (plotly 가로 막대그래프)
# -----------------------------------------------------------
fig = go.Figure()

# 남자 막대 (왼쪽, 음수 값)
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=male_values_neg,
        name="남자",
        orientation="h",
        marker_color="#4C9AFF",
        # 마우스를 올렸을 때는 원래(양수) 인구 수가 보이도록 설정
        customdata=male_values,
        hovertemplate="나이: %{y}<br>남자 인구: %{customdata:,}명<extra></extra>",
    )
)

# 여자 막대 (오른쪽, 양수 값)
fig.add_trace(
    go.Bar(
        y=age_labels,
        x=female_values,
        name="여자",
        orientation="h",
        marker_color="#FF7F91",
        hovertemplate="나이: %{y}<br>여자 인구: %{x:,}명<extra></extra>",
    )
)

fig.update_layout(
    title=f"{selected_sido} {selected_sigungu} {selected_dong} 인구 피라미드 ({latest_year}년)",
    barmode="overlay",  # 두 막대를 같은 축 위에 겹쳐서 좌우로 표현
    bargap=0.1,
    xaxis_title="인구 수 (명)",
    yaxis_title="나이",
    legend=dict(title="성별"),
    height=900,
)

# x축: 음수/양수를 모두 절댓값으로 보이게 눈금 표시 (왼쪽도 '숫자만' 보이도록)
max_val = max(male_values.max(), female_values.max())
fig.update_xaxes(
    tickvals=[-max_val, -max_val / 2, 0, max_val / 2, max_val],
    ticktext=[
        f"{int(max_val):,}",
        f"{int(max_val / 2):,}",
        "0",
        f"{int(max_val / 2):,}",
        f"{int(max_val):,}",
    ],
)

# ⭐ 세로축(나이) 순서를 0세 → 100세 이상 순으로 "고정"합니다.
# category_order='array' + categoryarray=age_labels 는
# plotly가 값 크기나 알파벳 순으로 임의 정렬하지 못하게 막고,
# 우리가 만든 age_labels 리스트 순서를 그대로 사용하게 해줘요.
# 리스트가 [0세, 1세, ..., 100세 이상] 순서이고, plotly 세로축은
# 기본적으로 "리스트의 첫 항목이 맨 아래, 마지막 항목이 맨 위"로 그려지므로
# 별도로 뒤집지 않아도 0세가 맨 아래, 100세 이상이 맨 위에 위치합니다.
fig.update_yaxes(
    categoryorder="array",
    categoryarray=age_labels,
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "💡 막대에 마우스를 올리면 정확한 인구 수를 확인할 수 있어요. "
    "왼쪽은 남자, 오른쪽은 여자 인구이고, 맨 아래가 0세, 맨 위가 100세 이상이랍니다."
)

st.divider()
st.success("여기까지! 선택하신 동네의 나이·성별 인구 구조를 잘 살펴보셨나요? 🎉")

