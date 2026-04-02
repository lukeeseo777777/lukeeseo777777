import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components
import json

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="인천대 자취방 최적화", page_icon="🏠", layout="wide")

# --- KAKAO MAP API KEY 설정 ---
KAKAO_API_KEY = st.secrets["kakao_api_key"]

# --- 2. 데이터 로드 및 전처리 ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('부동산 매물 정리.csv', encoding='utf-8')
        df = df.dropna(subset=['주소', '보증금'])
        
        # 실질월세 계산
        df['실질월세'] = df['월세'] + df.get('관리비', 0) + (df['보증금'] * 0.04 / 12)

        # 시설점수 계산
        option_cols = ['에어컨', '냉장고', '세탁기', '인덕션', '엘리베이터', '신발장', '옷장', '베란다', '싱크대']
        df['시설점수'] = df.apply(lambda row: (sum(1 for col in option_cols if row.get(col) == 'O') / len(option_cols)) * 10, axis=1)

        # 가격 및 크기 점수 정규화
        min_p, max_p = df['실질월세'].min(), df['실질월세'].max()
        if max_p == min_p:
            df['가격점수'] = 10
        else:
            df['가격점수'] = 10 - ((df['실질월세'] - min_p) / (max_p - min_p) * 10)
        
        target_max_size = 25.0
        min_s = df['평수'].min()
        if target_max_size == min_s:
            df['크기점수'] = 10
        else:
            df['크기점수'] = ((df['평수'] - min_s) / (target_max_size - min_s) * 10)

        return df
    except Exception as e:
        st.error(f"데이터 로드 에러: {e}")
        return pd.DataFrame()

df = load_data()
if df.empty:
    st.stop()

# --- 3. 사이드바 ---
st.sidebar.header("🔍 검색 필터")
selected_types = st.sidebar.multiselect("매물 종류", df['종류'].unique(), default=df['종류'].unique())
max_budget = st.sidebar.slider("💰 최대 예산 (월세+관리비, 만원)", 
                               int(df['실질월세'].min()/10000), 
                               int(df['실질월세'].max()/10000), 70)

st.sidebar.divider()
st.sidebar.header("⚖️ 항목별 중요도 (1~10)")
w_price = st.sidebar.slider("가격 중요도", 1, 10, 5)
w_option = st.sidebar.slider("시설 중요도", 1, 10, 5)
w_size = st.sidebar.slider("크기 중요도", 1, 10, 5)

# --- 4. 필터링 및 계산 ---
filtered_df = df[(df['종류'].isin(selected_types)) & (df['실질월세'] <= max_budget * 10000)].copy()
total_w = w_price + w_option + w_size
filtered_df['최종점수'] = ((filtered_df['가격점수'] * (w_price / total_w)) +
                           (filtered_df['시설점수'] * (w_option / total_w)) +
                           (filtered_df['크기점수'] * (w_size / total_w))).round(1)

result_df = filtered_df.sort_values('최종점수', ascending=False).reset_index(drop=True)

# --- 5. 카카오맵 렌더링 함수 ---
def render_kakao_map(data):
    marker_list = []
    for _, row in data.iterrows():
        marker_list.append({
            "title": str(row['주소']),
            "address": str(row['주소']), # 주소 변환용
            "content": f'<div style="padding:5px;font-size:12px;width:150px;color:black;">{row["최종점수"]}점 | {row["종류"]}</div>'
        })
    markers_json = json.dumps(marker_list, ensure_ascii=False)

    map_html = f"""
    <head>
        <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
    </head>
    <div id="map" style="width:100%;height:400px;border-radius:10px;background-color:#eee;"></div>
    <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_API_KEY}&libraries=services&autoload=false"></script>
    <script>
        (function() {{
            var checkInterval = setInterval(function() {{
                if (window.kakao && window.kakao.maps && window.kakao.maps.load) {{
                    clearInterval(checkInterval);
                    
                    window.kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{
                            center: new kakao.maps.LatLng(37.375, 126.632),
                            level: 5
                        }};
                        var map = new kakao.maps.Map(container, options);
                        
                        var geocoder = new kakao.maps.services.Geocoder();
                        var positions = {markers_json};
                        
                        var bounds = new kakao.maps.LatLngBounds();
                        var markerCount = 0;

                        positions.forEach(function(pos) {{
                            geocoder.addressSearch(pos.address, function(result, status) {{
                                if (status === kakao.maps.services.Status.OK) {{
                                    var coords = new kakao.maps.LatLng(result[0].y, result[0].x);
                                    var marker = new kakao.maps.Marker({{ map: map, position: coords, title: pos.title }});
                                    var infowindow = new kakao.maps.InfoWindow({{ content: pos.content }});
                                    
                                    kakao.maps.event.addListener(marker, 'mouseover', function() {{ infowindow.open(map, marker); }});
                                    kakao.maps.event.addListener(marker, 'mouseout', function() {{ infowindow.close(); }});

                                    bounds.extend(coords);
                                    markerCount++;

                                    if (markerCount === positions.length) {{
                                        map.setBounds(bounds);
                                    }}
                                }}
                            }});
                        }});
                    }});
                }}
            }}, 100);
        }})();
    </script>
    """
    return components.html(map_html, height=420)

# --- 6. 결과 화면 출력 ---
st.title("인천대 송도 자취방 추천 🏠")

if not result_df.empty:
    st.subheader("📍 매물 위치 확인")
    render_kakao_map(result_df)

    st.divider()
    st.subheader("🏆 맞춤형 추천 매물 TOP 3")
    top_cols = st.columns(3)
    
    # 여기서 에러가 났던 key를 고유하게 부여합니다!
    for i in range(min(3, len(result_df))):
        row = result_df.iloc[i]
        with top_cols[i]:
            st.metric(label=f"{i + 1}위 추천", value=f"{row['최종점수']} / 10")
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=[row['가격점수'], row['시설점수'], row['크기점수']], 
                                          theta=['가격지수', '시설지수', '크기지수'],
                                          fill='toself', line_color='#00CC96'))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])), 
                              showlegend=False, height=250, margin=dict(l=40, r=40, t=20, b=20))
            
            st.plotly_chart(fig, use_container_width=True, key=f"radar_{i}") # 고유 key 적용 완료
            
            st.info(f"📍 {row['주소']}")
            st.write(f"📏 {row['평수']}평 | 💸 {int(row['보증금']/10000)}/{int(row['월세']/10000)}")
            
            # url 주소가 있는 경우에만 버튼 생성 (에러 방지)
            if 'url 주소' in row and pd.notna(row['url 주소']):
                st.link_button("상세보기", str(row['url 주소']))

    st.divider()
    st.subheader("📋 전체 매물 분석 리스트")
    
    display_cols = ['최종점수', '주소', '종류', '평수', '가격점수', '시설점수', '크기점수']
    if 'url 주소' in result_df.columns:
        display_cols.append('url 주소')
        
    st.dataframe(result_df[display_cols],
                 column_config={"url 주소": st.column_config.LinkColumn("링크")} if 'url 주소' in result_df.columns else None,
                 hide_index=True, use_container_width=True)
else:
    st.warning("조건에 맞는 매물이 없습니다. 좌측 검색 필터의 예산을 올려보세요.")
