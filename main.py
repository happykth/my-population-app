import json
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# -----------------------------------------------------------
# 페이지 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="남양주시 고령화 단계구분도", page_icon="🗺️")

st.title("🗺️ 남양주시 행정동별 고령화 단계구분도")
st.write("남양주시 행정동별 65세 이상 인구 비율(고령화율)을 지도 위에 색깔로 표현했어요. 색이 진할수록 고령화율이 높은 지역이랍니다 😊")

# -----------------------------------------------------------
# 1) 인구 데이터 불러오기 (gz로 압축된 csv지만 pandas가 알아서 풀어줘요)
# -----------------------------------------------------------
DATA_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/gyeonggi_dong.geojson"


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
# 2) 2026년 · 남양주시 데이터만 남기기
#    ('남양주시'는 '시도'가 아니라 '시군구' 값이에요)
#    한글은 같은 글자처럼 보여도 내부 인코딩 방식(NFC/NFD)이 달라서
#    문자열 비교가 실패하는 경우가 있어요. unicodedata.normalize로
#    양쪽을 같은 방식(NFC)으로 맞춰준 뒤 비교합니다.
# -----------------------------------------------------------
TARGET_YEAR = 2026
TARGET_SIGUNGU = unicodedata.normalize("NFC", "남양주시")

df["시군구_정규화"] = df["시군구"].apply(
    lambda x: unicodedata.normalize("NFC", str(x)) if pd.notna(x) else x
)
df_year = df[(df["연도"] == TARGET_YEAR) & (df["시군구_정규화"] == TARGET_SIGUNGU)].copy()

# 혹시라도 데이터가 비어 있으면(필터 조건이 안 맞으면) 원인을 바로 알 수 있도록 안내하고 멈춥니다.
if df_year.empty:
    available = sorted(df.loc[df["연도"] == TARGET_YEAR, "시군구_정규화"].unique())
    st.error(
        f"'{TARGET_SIGUNGU}' 데이터를 찾을 수 없어요. "
        f"'시군구' 열에 있는 값 중 이렇게 시작하는 것들을 확인해보세요: "
        f"{[s for s in available if '남양' in s or '남양주' in s]}"
    )
    st.stop()

st.info(f"**{TARGET_YEAR}년 남양주시** 행정동 데이터를 기준으로 그렸어요.")

# -----------------------------------------------------------
# 3) '코드'를 문자열로 맞추기 (동 단위 코드 10자리, 그대로 사용)
# -----------------------------------------------------------
df_year["코드"] = df_year["코드"].astype(str)

# -----------------------------------------------------------
# 4) 65세 이상 인구 비율(고령화율) 계산하기
# -----------------------------------------------------------
# '계_'로 시작하는 모든 열 = 전체 인구 (남_·여_ 열은 제외!)
total_cols = [col for col in df_year.columns if col.startswith("계_")]

# 65세부터 100세 이상까지의 '계_' 열 = 65세 이상 인구
elderly_cols = [f"계_{i}세" for i in range(65, 100)] + ["계_100세 이상"]

# 동(행정동) 단위는 이미 population_yearly.csv 안에서 한 줄(행)당 하나이므로
# 별도로 groupby 하지 않고 코드별로 바로 계산합니다.
df_year["전체인구"] = df_year[total_cols].sum(axis=1)
df_year["고령인구"] = df_year[elderly_cols].sum(axis=1)
df_year["고령화율"] = (df_year["고령인구"] / df_year["전체인구"] * 100).round(2)

aging_df = df_year[["코드", "동", "시군구", "전체인구", "고령인구", "고령화율"]].copy()

# -----------------------------------------------------------
# 4-0) GeoJSON도 남양주시 16개 동만 남기기
#    (경기도 전체 602개를 통째로 넘기면 지도가 무거워져서
#     제대로 그려지지 않을 수 있어요. 꼭 필요한 것만 추려줍니다)
# -----------------------------------------------------------
nyj_codes = set(aging_df["코드"])


def clean_code(value):
    # 코드 형식이 살짝 달라도(공백, 소수점 등) 매칭되도록 숫자만 남깁니다.
    return "".join(ch for ch in str(value) if ch.isdigit())


nyj_codes_clean = {clean_code(c) for c in nyj_codes}

# 원본 GeoJSON의 코드 목록을 먼저 기록해둡니다 (매칭 실패 시 진단용).
original_geo_codes = [f["properties"]["코드"] for f in geojson_data["features"]]

matched_features = []
for f in geojson_data["features"]:
    code_clean = clean_code(f["properties"]["코드"])
    if code_clean in nyj_codes_clean:
        # 지도(geojson)와 표(aging_df) 양쪽 모두 정제된 코드로 통일해서
        # plotly가 두 쪽을 정확히 같은 문자열로 매칭하도록 맞춰줍니다.
        f["properties"]["코드"] = code_clean
        matched_features.append(f)

geojson_data = {"type": "FeatureCollection", "features": matched_features}

# 인구 데이터 쪽 '코드'도 같은 정제된 형식으로 맞춰줍니다.
aging_df["코드"] = aging_df["코드"].apply(clean_code)

# 여기서도 혹시 코드가 하나도 안 맞으면, 양쪽 코드 예시를 직접 보여줘서
# 정확히 뭐가 다른지 바로 확인할 수 있게 합니다.
if len(geojson_data["features"]) == 0:
    sample_data_codes = sorted(nyj_codes)[:5]
    sample_geo_codes = sorted(original_geo_codes)[:5]
    st.error(
        "지도 경계 데이터와 인구 데이터의 '코드'가 하나도 맞지 않아요.\n\n"
        f"- 인구 데이터 코드 예시: {sample_data_codes} "
        f"(타입: {type(sample_data_codes[0]).__name__ if sample_data_codes else '없음'})\n"
        f"- GeoJSON 코드 예시: {sample_geo_codes} "
        f"(타입: {type(sample_geo_codes[0]).__name__ if sample_geo_codes else '없음'})"
    )
    st.stop()

# -----------------------------------------------------------
# 4-0-1) 지도 확대 범위를 직접 계산하기
#    (fitbounds 자동 계산이 남양주시처럼 아주 작은 영역에서는
#     제대로 동작하지 않을 때가 있어서, 위경도 범위를 직접 구해
#     지도 확대 범위를 고정해줍니다)
# -----------------------------------------------------------
def get_lon_lat_bounds(geojson):
    lons, lats = [], []

    def collect(coords):
        # 좌표 배열을 재귀적으로 파고들어 [경도, 위도] 쌍을 모두 모읍니다.
        if isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for c in coords:
                collect(c)

    for feature in geojson["features"]:
        collect(feature["geometry"]["coordinates"])

    return min(lons), max(lons), min(lats), max(lats)


min_lon, max_lon, min_lat, max_lat = get_lon_lat_bounds(geojson_data)
# 살짝 여백을 줘서 경계선이 화면 끝에 딱 붙지 않도록 합니다.
lon_pad = (max_lon - min_lon) * 0.08
lat_pad = (max_lat - min_lat) * 0.08

# -----------------------------------------------------------
# 4-1) 기준선 슬라이더: 이 값 이상인 시군구만 진하게 칠해요
# -----------------------------------------------------------
st.subheader("🎚️ 기준선으로 나눠 보기")
threshold = st.slider(
    "고령화율 기준(%)을 정해보세요",
    min_value=0,
    max_value=50,
    value=20,
    step=1,
)
st.write(f"현재 기준: **{threshold}% 이상**인 행정동을 진하게 표시합니다.")

above_label = f"{threshold}% 이상"
below_label = f"{threshold}% 미만"
aging_df["구분"] = aging_df["고령화율"].apply(
    lambda x: above_label if x >= threshold else below_label
)

# -----------------------------------------------------------
# 5) plotly 단계구분도(choropleth) 그리기
#    - 배경 지도(타일) 없이 경계선만 그려요 (Mapbox 등 사용 안 함)
#    - featureidkey는 GeoJSON 속성의 '코드'와 짝짓고,
#      locations는 우리 데이터의 '코드'와 짝지어줍니다.
#    - 둘 다 문자열(str)로 맞춰야 정확히 매칭돼요.
# -----------------------------------------------------------
fig = go.Figure()

# 기준 미만 지역: 회색으로 (지도에서 먼저 그려서 뒤에 깔리게)
below_df = aging_df[aging_df["구분"] == below_label]
fig.add_trace(
    go.Choropleth(
        geojson=geojson_data,
        featureidkey="properties.코드",
        locations=below_df["코드"],
        z=[0] * len(below_df),
        colorscale=[[0, "#D9D9D9"], [1, "#D9D9D9"]],  # 회색 고정
        showscale=False,
        marker_line_color="white",
        marker_line_width=0.3,
        customdata=below_df[["동", "고령화율"]],
        hovertemplate="<b>%{customdata[0]}</b><br>고령화율: %{customdata[1]:.2f}%<extra></extra>",
        name=below_label,
        showlegend=True,
    )
)

# 기준 이상 지역: 진한 색으로 (뒤이어 그려서 위에 덧칠해지게)
above_df = aging_df[aging_df["구분"] == above_label]
fig.add_trace(
    go.Choropleth(
        geojson=geojson_data,
        featureidkey="properties.코드",
        locations=above_df["코드"],
        z=[1] * len(above_df),
        colorscale=[[0, "#C0392B"], [1, "#C0392B"]],  # 진한 빨강 고정
        showscale=False,
        marker_line_color="white",
        marker_line_width=0.3,
        customdata=above_df[["동", "고령화율"]],
        hovertemplate="<b>%{customdata[0]}</b><br>고령화율: %{customdata[1]:.2f}%<extra></extra>",
        name=above_label,
        showlegend=True,
    )
)

# 배경 지도(타일) 없이 경계 도형만 표시하도록 geo 설정
# fitbounds 자동 계산 대신, 위에서 구한 위경도 범위로 직접 확대 범위를 지정합니다.
fig.update_geos(
    visible=False,  # 기본 지도 배경(국경선, 바다색 등) 숨기기
    projection_type="mercator",
    lonaxis_range=[min_lon - lon_pad, max_lon + lon_pad],
    lataxis_range=[min_lat - lat_pad, max_lat + lat_pad],
)

fig.update_layout(
    title=f"{TARGET_YEAR}년 남양주시 행정동별 고령화율 ({threshold}% 기준)",
    height=800,
    margin=dict(l=0, r=0, t=60, b=0),
    legend_title_text="구분",
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.0,
        xanchor="left",
        x=0,
    ),
)

map_col, table_col = st.columns([3, 1])

with map_col:
    st.plotly_chart(fig, use_container_width=True)

with table_col:
    st.write("**🔥 고령화율 TOP 5**")
    top5_df = (
        aging_df.sort_values("고령화율", ascending=False)
        .head(5)[["동", "고령화율"]]
        .reset_index(drop=True)
    )
    top5_df.index = top5_df.index + 1  # 1등부터 5등까지 순위처럼 보이도록
    st.dataframe(
        top5_df.rename(columns={"고령화율": "고령화율(%)"}),
        use_container_width=True,
    )

st.caption(
    "💡 진한 색은 기준 이상, 회색은 기준 미만인 행정동이에요. "
    "지역 위에 마우스를 올리면 동 이름과 정확한 고령화율(%)을 확인할 수 있어요. "
    "지도를 드래그하거나 스크롤하면 확대·축소도 가능합니다."
)

st.divider()
st.success("여기까지! 남양주시 행정동별 고령화 수준 차이를 잘 살펴보셨나요? 🎉")
