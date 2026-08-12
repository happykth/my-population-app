import json

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# -----------------------------------------------------------
# 페이지 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="전국 고령화 단계구분도", page_icon="🗺️")

st.title("🗺️ 전국 고령화 단계구분도")
st.write("시군구별 65세 이상 인구 비율(고령화율)을 지도 위에 색깔로 표현했어요. 색이 진할수록 고령화율이 높은 지역이랍니다 😊")

# -----------------------------------------------------------
# 1) 인구 데이터 불러오기 (gz로 압축된 csv지만 pandas가 알아서 풀어줘요)
# -----------------------------------------------------------
DATA_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"


@st.cache_data
def load_population():
    df = pd.read_csv(DATA_URL, compression="gzip")
    return df


@st.cache_data
def load_geojson():
    # requests로 GeoJSON 파일을 내려받아 파이썬 딕셔너리(JSON)로 읽어옵니다.
    response = requests.get(GEOJSON_URL)
    response.raise_for_status()
    return response.json()


with st.spinner("인구 데이터와 지도 경계 데이터를 불러오는 중이에요... 잠시만 기다려주세요!"):
    df = load_population()
    geojson_data = load_geojson()

# -----------------------------------------------------------
# 2) 2026년 데이터만 남기기
# -----------------------------------------------------------
TARGET_YEAR = 2026
df_year = df[df["연도"] == TARGET_YEAR].copy()

st.info(f"**{TARGET_YEAR}년** 데이터를 기준으로 그렸어요.")

# -----------------------------------------------------------
# 3) '코드'의 앞 5자리로 시군구 코드 만들기
#    (동 단위 코드는 10자리인데, 앞 5자리가 시군구를 나타내요)
# -----------------------------------------------------------
df_year["코드"] = df_year["코드"].astype(str)
df_year["시군구코드"] = df_year["코드"].str[:5]

# -----------------------------------------------------------
# 4) 65세 이상 인구 비율(고령화율) 계산하기
# -----------------------------------------------------------
# '계_'로 시작하는 모든 열 = 전체 인구 (남_·여_ 열은 제외!)
total_cols = [col for col in df_year.columns if col.startswith("계_")]

# 65세부터 100세 이상까지의 '계_' 열 = 65세 이상 인구
elderly_cols = [f"계_{i}세" for i in range(65, 100)] + ["계_100세 이상"]

# 시군구코드별로 동 단위 인구를 모두 더해줍니다.
grouped = df_year.groupby("시군구코드")[total_cols].sum()

grouped["전체인구"] = grouped[total_cols].sum(axis=1)
grouped["고령인구"] = grouped[elderly_cols].sum(axis=1)
grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"] * 100).round(2)

aging_df = grouped.reset_index()[["시군구코드", "전체인구", "고령인구", "고령화율"]]

# -----------------------------------------------------------
# 5) plotly 단계구분도(choropleth) 그리기
#    - 배경 지도(타일) 없이 경계선만 그려요 (Mapbox 등 사용 안 함)
#    - featureidkey는 GeoJSON 속성의 '코드'와 짝짓고,
#      locations는 우리 데이터의 '시군구코드'와 짝지어줍니다.
#    - 둘 다 문자열(str)로 맞춰야 정확히 매칭돼요.
# -----------------------------------------------------------
fig = go.Figure(
    go.Choropleth(
        geojson=geojson_data,
        featureidkey="properties.코드",
        locations=aging_df["시군구코드"],
        z=aging_df["고령화율"],
        colorscale="OrRd",  # 연한 색 → 진한 색 (고령화율이 높을수록 진하게)
        colorbar_title="고령화율(%)",
        marker_line_color="white",
        marker_line_width=0.5,
        # 마우스를 올리면 시군구 이름과 고령화율이 보이도록 customdata 사용
        customdata=aging_df[["시군구코드", "고령화율"]].merge(
            df_year[["시군구코드", "시군구"]].drop_duplicates(),
            on="시군구코드",
            how="left",
        )["시군구"],
        hovertemplate="<b>%{customdata}</b><br>고령화율: %{z:.2f}%<extra></extra>",
    )
)

# 배경 지도(타일) 없이 경계 도형만 표시하도록 geo 설정
fig.update_geos(
    visible=False,  # 기본 지도 배경(국경선, 바다색 등) 숨기기
    fitbounds="locations",  # 우리 데이터가 있는 영역에 딱 맞게 확대
)

fig.update_layout(
    title=f"{TARGET_YEAR}년 전국 시군구별 고령화율(65세 이상 인구 비율)",
    height=800,
    margin=dict(l=0, r=0, t=60, b=0),
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "💡 색이 진할수록 65세 이상 인구 비율이 높은 지역이에요. "
    "지역 위에 마우스를 올리면 시군구 이름과 정확한 고령화율(%)을 확인할 수 있어요. "
    "지도를 드래그하거나 스크롤하면 확대·축소도 가능합니다."
)

st.divider()
st.success("여기까지! 전국 시군구의 고령화 수준 차이를 잘 살펴보셨나요? 🎉")
