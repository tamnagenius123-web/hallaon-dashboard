import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import altair as alt
import plotly.express as px

# --- 설정 정보 ---
NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID = st.secrets["DATABASE_ID"]
DISCORD_WEBHOOK_URL = st.secrets["DISCORD_WEBHOOK_URL"]

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- 데이터 로직 ---
@st.cache_data(ttl=60)
def fetch_and_process_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    response = requests.post(url, headers=headers)
    
    if response.status_code != 200:
        st.error(f"Notion API 연결 실패: {response.json().get('message')}")
        return pd.DataFrame()

    data = response.json()
    results = []
    
    for row in data['results']:
        props = row['properties']
        
        name_list = props.get('작업 이름', {}).get('title', [])
        name = name_list[0]['plain_text'] if name_list else "이름 없음"
        
        status = props.get('상태', {}).get('status', {}).get('name', '시작 전')
        
        teams_list = props.get('팀', {}).get('multi_select', [])
        teams = [t['name'] for t in teams_list] if teams_list else ["미지정"]
        
        people_list = props.get('담당자', {}).get('people', [])
        assignees = ", ".join([person.get('name', '알 수 없음') for person in people_list]) if people_list else "담당자 미정"
        
        date_info = props.get('마감일', {}).get('date')
        if date_info:
            start_str = date_info['start']
            end_str = date_info['end'] if date_info.get('end') else start_str
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            display_end = end_date + timedelta(days=1)
        else:
            start_date = datetime.now().date()
            display_end = start_date + timedelta(days=1)
            end_str = start_str = start_date.strftime("%Y-%m-%d")

        for team in teams:
            results.append({
                "작업명": name,
                "담당자": assignees, # 담당자를 표기
                "팀": team,
                "상태": status,
                "시작일": start_date,
                "종료일": display_end,
                "타임라인": f"{start_str} → {end_str}",
            })
            
    return pd.DataFrame(results)

# --- 기본 UI 및 CSS 셋팅 ---
st.set_page_config(page_title="Hallaon Workspace", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #111111; color: white; }
    h1, h2, h3 { color: #f0f2f6 !important; font-family: 'Inter', sans-serif; }
    
    /* 대시보드 메트릭 카드 디자인 - 다크/라이트 완벽 대응 (화이트 텍스트) */
    div[data-testid="metric-container"] {
        background-color: transparent !important;
        border: none !important;
        padding: 5px 10px;
    }
    div[data-testid="metric-container"] * { color: #ffffff !important; }
    div[data-testid="stMetricLabel"] > div > div > div > p { color: #ffffff !important; font-weight: 500; font-size: 15px; }
    div[data-testid="stMetricValue"] > div { color: #ffffff !important; font-size: 32px; font-weight: 700; margin-top: 5px; }
    
    /* Expander 스타일 초기화 */
    .streamlit-expanderHeader {
        background-color: transparent !important;
        color: #f0f2f6 !important;
    }
    .streamlit-expanderContent {
        background-color: transparent !important;
        border: none !important;
    }
    
    /* 사이드바 메뉴 디자인 */
    section[data-testid="stSidebar"] {
        background-color: #1a1a1a;
    }
    .stRadio > div {
        gap: 15px;
    }
    </style>
""", unsafe_allow_html=True)

df = fetch_and_process_data()

# 초기화: 디스코드로 전송된 작업 이름 목록 보관 (session_state 활용)
if 'sent_to_discord' not in st.session_state:
    st.session_state.sent_to_discord = set()

# 데이터 중복 병합 (출력용)
if not df.empty:
    display_df = df.groupby(['작업명', '담당자', '상태', '타임라인', '시작일', '종료일']).agg({'팀': ', '.join}).reset_index()
    # 최신 등록순으로 정렬을 위해 인덱스 활용 (노션은 기본적으로 최근 항목이 뒤쪽에 있거나 쿼리 순서에 따름)
else:
    display_df = pd.DataFrame()

# --- 사이드바 (왼쪽 탭 메뉴) ---
with st.sidebar:
    st.title("🏛️ Hallaon")
    st.markdown("---")
    # 4개의 탭을 라디오 버튼으로 구현
    menu = st.radio(
        "워크스페이스 메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🤖 최근 등록된 작업 전송"]
    )
    st.markdown("---")
    st.caption("2026 Hallaon Agile System")

# --- 메인 화면 로직 ---
if df.empty:
    st.info("데이터를 불러오는 중이거나 노션에 데이터가 없습니다.")

else:
    # ==========================================
    # 탭 1: 2026 한라온 (메인 테이블 뷰)
    # ==========================================
    if menu == "📋 2026 한라온":
        st.header("📋 2026 한라온 (할 일 / 완료됨)")
        st.markdown("노션 형태의 데이터베이스 뷰입니다.")
        
        # 상태 기반 그룹화
        todo_df = display_df[display_df['상태'].str.contains('시작 전|대기|진행|작업|막힘', na=False) == True]
        done_df = display_df[display_df['상태'].str.contains('완료', na=False) == True]
        
        # HTML을 이용한 노션 스타일 테이블 렌더링 함수
        def render_notion_table(df_subset):
            if df_subset.empty:
                return "<div style='color: #9ca3af; padding: 10px; font-size: 14px;'>항목이 없습니다.</div>"
            
            html = f"""
            <style>
            .n-table-wrap {{
                background-color: transparent;
                margin-bottom: 5px;
            }}
            .n-table {{
                width: 100%;
                border-collapse: collapse;
                text-align: left;
                font-family: 'Inter', sans-serif;
            }}
            .n-table th {{
                background-color: #1f2329;
                color: #a3a8b4;
                font-size: 13px;
                font-weight: 500;
                padding: 12px 16px;
                border-bottom: 1px solid #2d3139;
                border-right: 1px solid #2d3139;
            }}
            .n-table th:last-child {{ border-right: none; }}
            .n-table td {{
                padding: 12px 16px;
                border-bottom: 1px solid #2d3139;
                border-right: 1px solid #2d3139;
                font-size: 14px;
                color: #e2e8f0;
                background-color: #11141a;
            }}
            .n-table td:last-child {{ border-right: none; }}
            .n-table tr:hover td {{ background-color: #1a1e26; cursor: pointer; }}
            
            .n-tag {{
                display: inline-block;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: 500;
            }}
            .n-tag-blue {{ background-color: #dbeafe; color: #1e40af; }}
            .n-tag-green {{ background-color: #dcfce3; color: #166534; }}
            .n-tag-yellow {{ background-color: #fef08a; color: #854d0e; }}
            .n-tag-red {{ background-color: #fee2e2; color: #991b1b; }}
            .n-tag-gray {{ background-color: #f3f4f6; color: #374151; }}
            .n-tag-purple {{ background-color: #f3e8ff; color: #6b21a8; }}
            
            .n-owner {{
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .n-avatar {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background-color: #e5e7eb;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                font-weight: bold;
                color: #4b5563;
            }}
            .n-date {{
                display: flex;
                align-items: center;
                gap: 4px;
                font-size: 13px;
                color: #4b5563;
            }}
            </style>
            <div class="n-table-wrap">
                <table class="n-table">
                    <thead>
                        <tr>
                            <th style="width: 40px;"></th>
                            <th style="width: 300px;">태스크</th>
                            <th style="width: 120px;">소유자</th>
                            <th style="width: 120px;">상태</th>
                            <th style="width: 100px;">팀</th>
                            <th>타임라인 ⓘ</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for _, row in df_subset.iterrows():
                task = row['작업명']
                owner = row['담당자']
                status = row['상태']
                team = str(row['팀'])
                tl = row['타임라인']
                
                # 상태 색상
                s_class = "n-tag-gray"
                if '완료' in status: s_class = "n-tag-green"
                elif '작업' in status or '진행' in status: s_class = "n-tag-yellow"
                elif '막힘' in status: s_class = "n-tag-red"
                elif '대기' in status: s_class = "n-tag-purple"
                
                # 팀 색상 (첫번째 팀 기준)
                first_t = team.split(', ')[0] if ',' in team else team
                t_class = "n-tag-blue" if first_t == 'PM' else "n-tag-red" if first_t == 'CD' else "n-tag-green" if first_t == 'FS' else "n-tag-purple" if first_t == 'DM' else "n-tag-yellow"
                
                # 아바타 이니셜
                av = owner[0] if len(owner) > 0 else "?"
                
                html += f"""
                        <tr>
                            <td style="text-align: center;"><input type="checkbox" style="cursor:pointer;"></td>
                            <td style="font-weight: 500;">{task}</td>
                            <td><div class="n-owner"><div class="n-avatar">{av}</div><span>{owner}</span></div></td>
                            <td><span class="n-tag {s_class}">{status}</span></td>
                            <td><span class="n-tag {t_class}">{first_t}</span></td>
                            <td><div class="n-date">📅 {tl}</div></td>
                        </tr>
                """
                
            html += "</tbody></table></div>"
            return html

        # 할 일 (단순 마크다운이 아닌 html 컴포넌트 렌더링으로 겹침/코드노출 방지)
        st.markdown("<h4 style='color: #4b8df8; font-size: 18px; margin-bottom: 0px;'>˅ 할 일</h4>", unsafe_allow_html=True)
        html_todo = render_notion_table(todo_df)
        st.components.v1.html(html_todo, height=max(200, len(todo_df)*55 + 50), scrolling=True)

        # 완료됨
        st.markdown("<h4 style='color: #10b981; font-size: 18px; margin-bottom: 0px; margin-top: -10px;'>˅ 완료됨</h4>", unsafe_allow_html=True)
        html_done = render_notion_table(done_df)
        st.components.v1.html(html_done, height=max(150, len(done_df)*55 + 50), scrolling=True)

    # ==========================================
    # 탭 2: 간트 차트 (타임라인 뷰)
    # ==========================================
    elif menu == "📊 간트 차트":
        st.header("📊 프로젝트 간트 차트")
        st.markdown("작업 일정과 흐름을 시각적으로 확인합니다.")
        
        if not df.empty:
            min_date = df['시작일'].min()
            max_date = df['종료일'].max()
            
            # 타임라인 기준일 설정 (min_date가 속한 주의 일요일 또는 월요일 - 여기선 월요일 기준)
            start_diff = min_date.weekday()
            timeline_start = min_date - timedelta(days=start_diff)
            
            days_total = (max_date - timeline_start).days + 14 # 우측 여백 추가
            if days_total < 35:
                days_total = 35 # 최소 5주 표기
            
            days_total = ((days_total // 7) + 1) * 7
            total_weeks = days_total // 7
            timeline_end = timeline_start + timedelta(days=days_total)

            html_content = ""
            html_content += "<style>\n"
            html_content += ".gan-wrapper { background-color: #11141a; border-radius: 8px; border: 1px solid #2d3139; overflow-x: auto; font-family: 'Inter', sans-serif; color: #e2e8f0; margin-top: 10px; padding-bottom: 20px; }\n"
            html_content += ".gan-header { display: flex; align-items: center; gap: 15px; padding: 15px 15px 0 15px; margin-bottom: -5px; }\n"
            html_content += ".leg-item { display: flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600; color: #94a3b8; }\n"
            html_content += ".leg-dot { width: 10px; height: 10px; border-radius: 50%; }\n"
            html_content += ".g-table { width: 100%; min-width: 1000px; border-collapse: collapse; table-layout: fixed; margin-top: 15px; }\n"
            html_content += ".g-table th, .g-table td { border-bottom: 1px solid #2d3139; border-right: 1px solid #2d3139; padding: 12px 14px; white-space: nowrap; font-size: 13px; vertical-align: middle; }\n"
            html_content += ".g-table th:last-child, .g-table td:last-child { border-right: none; }\n"
            html_content += ".g-table th { background-color: #1a1e26; color: #94a3b8; font-size: 11px; font-weight: 600; text-transform: uppercase; text-align: left; }\n"
            html_content += ".g-table th.week-h { text-align: center; border-right: 1px solid #2d3139; min-width: 130px; }\n"
            html_content += ".badge-team { padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; color: white; display: inline-block; }\n"
            html_content += ".owner-box { display: flex; align-items: center; gap: 8px; }\n"
            html_content += ".owner-avt { width: 24px; height: 24px; border-radius: 50%; background-color: #334155; color: white; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 600; }\n"
            html_content += ".status-box { display: flex; align-items: center; gap: 6px; }\n"
            html_content += ".dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }\n"
            html_content += ".tl-cell { padding: 0 !important; position: relative; }\n"
            html_content += ".tl-bg { position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; pointer-events: none; }\n"
            html_content += ".tl-col { flex: 1; border-right: 1px solid #2d3139; box-sizing: border-box; }\n"
            html_content += ".tl-col:last-child { border-right: none; }\n"
            html_content += ".bar-wrap { position: relative; height: 50px; display: flex; align-items: center; width: 100%; }\n"
            html_content += ".g-bar { position: absolute; height: 26px; border-radius: 4px; display: flex; align-items: center; padding: 0 10px; font-size: 12px; font-weight: 600; color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.3); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }\n"
            html_content += "</style>\n"
            html_content += "<div class='gan-wrapper'>\n"
            
            # Team Legend
            html_content += "<div class='gan-header'>\n"
            html_content += "<div class='leg-item'><div class='leg-dot' style='background-color: #3b82f6;'></div>PM</div>\n"
            html_content += "<div class='leg-item'><div class='leg-dot' style='background-color: #10b981;'></div>FS</div>\n"
            html_content += "<div class='leg-item'><div class='leg-dot' style='background-color: #ef4444;'></div>CD</div>\n"
            html_content += "<div class='leg-item'><div class='leg-dot' style='background-color: #8b5cf6;'></div>DM</div>\n"
            html_content += "<div class='leg-item'><div class='leg-dot' style='background-color: #eab308;'></div>OPS</div>\n"
            html_content += "</div>\n"
            
            html_content += "<table class='g-table'>\n"
            html_content += "<thead><tr>\n"
            html_content += "<th style='width: 70px; text-align: center;'>TEAM</th>\n"
            html_content += "<th style='width: 220px;'>TASK NAME</th>\n"
            html_content += "<th style='width: 130px;'>OWNER</th>\n"
            html_content += "<th style='width: 110px;'>STATUS</th>\n"
            
            for i in range(total_weeks):
                ws = timeline_start + timedelta(days=i*7)
                html_content += f'<th class="week-h">Week {i+1} ({ws.month}/{ws.day}~)</th>'
                
            html_content += "</tr></thead><tbody>"
            
            for idx, row in display_df.iterrows():
                team_str = row['팀']
                task_name = row['작업명']
                owner = row['담당자']
                status = row['상태']
                start_d = row['시작일']
                end_d = row['종료일']
                
                first_team = team_str.split(', ')[0] if isinstance(team_str, str) else str(team_str)
                # 간트 차트 팀별 커스텀 배지 색상 (이미지 기준: PM=파랑, CD=빨강/분홍, FS=초록, DM=보라, OPS=노랑/주황)
                t_color = {"PM": "#3b82f6", "CD": "#ef4444", "FS": "#10b981", "DM": "#8b5cf6", "OPS": "#eab308"}.get(first_team, "#6b7280")
                
                av_char = owner[0] if len(owner) > 0 else "?"
                
                if '완료' in status:
                    dot_c = '#10b981'
                    bar_txt = '✓ Done'
                elif '대기' in status or '시작 전' in status:
                    dot_c = '#6b7280'
                    bar_txt = 'Scheduled'
                else:
                    dot_c = '#eab308'
                    bar_txt = '진행중'
                    
                cs = max(start_d, timeline_start)
                ce = min(end_d, timeline_end)
                
                off = (cs - timeline_start).days
                dur = (ce - cs).days
                if dur < 1: dur = 1
                
                left_p = (off / days_total) * 100
                wid_p = (dur / days_total) * 100
                
                bg_grids = "".join(["<div class='tl-col'></div>" for _ in range(total_weeks)])
                
                html_content += "<tr>\n"
                html_content += f"<td style='text-align: center;'><span class='badge-team' style='background-color: {t_color}; opacity: 0.9;'>{first_team}</span></td>\n"
                html_content += f"<td style='font-weight: 500;'>{task_name}</td>\n"
                html_content += f"<td><div class='owner-box'><div class='owner-avt'>{av_char}</div><span>{owner}</span></div></td>\n"
                html_content += f"<td><div class='status-box'><span class='dot' style='background-color: {dot_c};'></span><span>{status}</span></div></td>\n"
                html_content += f"<td colspan='{total_weeks}' class='tl-cell'>\n"
                html_content += f"<div class='tl-bg'>{bg_grids}</div>\n"
                html_content += "<div class='bar-wrap'>\n"
                html_content += f"<div class='g-bar' style='left: {left_p}%; width: {wid_p}%; background-color: {t_color}; opacity: 0.85;'>{bar_txt}</div>\n"
                html_content += "</div>\n"
                html_content += "</td>\n"
                html_content += "</tr>\n"
                
            html_content += "</tbody></table></div>"
            st.components.v1.html(html_content, height=max(400, len(display_df)*55 + 100), scrolling=True)

    # ==========================================
    # 탭 3: 대시보드 (통계 뷰)
    # ==========================================
    elif menu == "📈 대시보드":
        st.header("📈 2026 한라온 종합 대시보드")
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_tasks = len(display_df)
        in_progress = len(display_df[display_df['상태'].str.contains('진행|작업', na=False)])
        stuck = len(display_df[display_df['상태'].str.contains('막힘', na=False)])
        done = len(display_df[display_df['상태'].str.contains('완료', na=False)])

        col1.metric("📦 모든 태스크", total_tasks)
        col2.metric("⏳ 진행 중", in_progress)
        col3.metric("🛑 막힘", stuck)
        col4.metric("✅ 완료", done)
        
        st.markdown("<br>", unsafe_allow_html=True)

        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.markdown("##### 📊 상태별 태스크")
            status_counts = display_df['상태'].value_counts().reset_index()
            status_counts.columns = ['상태', '개수']
            
            color_map = {'완료': '#00C853', '작업 중': '#FFA500', '막힘': '#D50000', '시작 전': '#9E9E9E'}
            fig_pie = px.pie(status_counts, names='상태', values='개수', color='상태', color_discrete_map=color_map, hole=0.4)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(template="plotly_dark", height=350, margin=dict(t=20, b=20, l=0, r=0), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

        with chart_col2:
            st.markdown("##### 👤 담당자별 태스크")
            assignee_counts = display_df['담당자'].value_counts().reset_index()
            assignee_counts.columns = ['담당자', '개수']
            
            fig_bar = px.bar(assignee_counts, x='담당자', y='개수', text_auto=True, color_discrete_sequence=['#3366CC'])
            fig_bar.update_layout(template="plotly_dark", height=350, margin=dict(t=20, b=20, l=0, r=0))
            st.plotly_chart(fig_bar, use_container_width=True)

    # ==========================================
    # 탭 4: 디스코드 웹후크 전송
    # ==========================================
    elif menu == "🤖 최근 등록된 작업 전송":
        st.header("🤖 디스코드 알림 전송")
        st.markdown("아직 디스코드로 전송되지 않은 새 작업들을 일괄 전송합니다.")
        
        # 전송되지 않은 작업 필터링 (작업명 기준)
        unsent_tasks = display_df[~display_df['작업명'].isin(st.session_state.sent_to_discord)]
        
        if unsent_tasks.empty:
            st.info("현재 새롭게 추가되거나 업데이트되어 전송할 작업이 없습니다.")
        else:
            st.success(f"전송 대기 중인 새 작업: {len(unsent_tasks)}개")
            
            # 미리보기 표출
            st.dataframe(
                unsent_tasks[["작업명", "담당자", "상태", "팀", "타임라인"]],
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("🚀 미전송 작업 모두 디스코드로 쏘기", type="primary"):
                embeds = []
                
                # 디스코드 embed 최대 개수는 10개이므로 10개씩 끊어서 전송 혹은 1개의 embed 내 fields로 처리
                # 여기서는 1개의 embed 안에 여러 개의 field(작업)으로 묶어서 전송 (embed description이 꽉 찰 수 있으니 유의)
                
                fields = []
                for _, task in unsent_tasks.iterrows():
                    field_value = f"👤 **담당:** {task['담당자']}\n📅 **기간:** {task['타임라인']} | 🏷️ **상태:** {task['상태']}"
                    fields.append({
                        "name": f"🔹 {task['작업명']} ({task['팀']})",
                        "value": field_value,
                        "inline": False
                    })
                
                # field가 25개 이상 넘어갈 경우를 대비해 슬라이싱 (디스코드 한도)
                for i in range(0, len(fields), 25):
                    batch_fields = fields[i:i+25]
                    payload = {
                        "username": "Hallaon Roadmap Bot",
                        "embeds": [{
                            "title": "🔔 전송 대기 중이던 새로운 작업들이 등록되었습니다!",
                            "color": 3447003,
                            "fields": batch_fields,
                            "footer": {"text": f"Hallaon Agile Dashboard • {len(batch_fields)}개 항목"}
                        }]
                    }
                    
                    res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
                    
                    if res.status_code == 204:
                        # 성공적으로 보낸 작업명들을 session_state에 저장
                        sent_names = [f["name"].split(" (")[0].replace("🔹 ", "") for f in batch_fields]
                        st.session_state.sent_to_discord.update(sent_names)
                    else:
                        st.error(f"전송 중 오류가 발생했습니다. (코드: {res.status_code})")
                        break
                else:
                    st.success(f"총 {len(unsent_tasks)}개의 작업을 성공적으로 디스코드에 전송했습니다!")
                    st.rerun()
