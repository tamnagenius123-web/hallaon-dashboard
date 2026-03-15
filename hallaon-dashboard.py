import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta

# 1. 설정 정보
NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID = st.secrets["DATABASE_ID"]
DISCORD_WEBHOOK_URL = st.secrets["DISCORD_WEBHOOK_URL"]
headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def fetch_notion_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    response = requests.post(url, headers=headers)
    
    if response.status_code != 200:
        st.error(f"노션 연결 실패: {response.json().get('message')}")
        return pd.DataFrame()

    data = response.json()
    results = []
    
    for row in data['results']:
        props = row['properties']
        
        # 1. 작업 이름 (Title)
        title_list = props.get('작업 이름', {}).get('title', [])
        name = title_list[0]['plain_text'] if title_list else "이름 없음"
        
        # 2. 상태 (Status)
        status = props.get('상태', {}).get('status', {}).get('name', '대기')
        
        # 3. 팀 (Multi-select) - 여러 개를 쉼표로 연결
        teams_list = props.get('팀', {}).get('multi_select', [])
        teams = ", ".join([t['name'] for t in teams_list]) if teams_list else "미지정"
        
        # 4. 마감일 (Date)
        date_info = props.get('마감일', {}).get('date')
        if date_info:
            deadline = date_info['start']
            # 간트 차트 시각화를 위해 시작일은 마감일 3일 전으로 임시 설정 (변경 가능)
            end_date = datetime.strptime(deadline, "%Y-%m-%d")
            start_date = end_date - timedelta(days=3) 
        else:
            deadline = datetime.now().strftime("%Y-%m-%d")
            start_date = datetime.now()
            end_date = datetime.now()

        results.append({
            "작업명": name,
            "팀": teams,
            "상태": status,
            "시작일": start_date,
            "마감일": end_date,
            "표시날짜": deadline
        })
    return pd.DataFrame(results)

# --- Streamlit UI ---
st.set_page_config(page_title="Hallaon 작업 트래커", layout="wide")
st.title("🏛️ 한라온(Hallaon) 실시간 작업 트래커")

df = fetch_notion_data()

if not df.empty:
    # 간트 차트 (Plotly)
    # 팀(다중선택) 중 첫 번째 팀을 기준으로 색상 지정
    df['대표팀'] = df['팀'].apply(lambda x: x.split(',')[0])
    
    fig = px.timeline(
        df, 
        x_start="시작일", 
        x_end="마감일", 
        y="작업명", 
        color="대표팀",
        hover_data=["상태", "표시날짜", "팀"],
        title="📅 프로젝트 타임라인 (마감일 기준)"
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(template="plotly_dark", height=600)
    
    st.plotly_chart(fig, use_container_width=True)

    # 데이터 표
    st.subheader("📋 전체 작업 리스트")
    st.dataframe(df[["작업명", "팀", "상태", "표시날짜"]], use_container_width=True)
else:
    st.info("데이터를 불러오는 중이거나 데이터베이스가 비어있습니다.")
    

def send_discord_notification(task_name, team_name, status, deadline):
    # 디스코드에 보낼 임베드 데이터 구성
    payload = {
        "username": "HALLAON_BOT", # 봇 이름 설정
        "embeds": [
            {
                "title": f"📋 새로운 작업이 등록되었습니다!",
                "description": f"**{task_name}**",
                "color": 5814783, # 파란색 계열
                "fields": [
                    {"name": "담당 팀", "value": team_name, "inline": True},
                    {"name": "현재 상태", "value": status, "inline": True},
                    {"name": "마감 기한", "value": deadline, "inline": False}
                ],
                "footer": {"text": "Hallaon Agile Dashboard"},
                "timestamp": datetime.now().isoformat()
            }
        ]
    }
    
    # 웹후크 전송
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

# 대시보드 화면에 전송 버튼 만들기
if st.sidebar.button("디스코드에 최근 작업 현황 전송"):
    # 현재 가장 최근 작업 하나를 예시로 전송
    if not df.empty:
        latest = df.iloc[-1]
        send_discord_notification(latest['작업명'], latest['팀'], latest['상태'], latest['표시날짜'])
        st.sidebar.success("디스코드로 알림을 보냈습니다!")    
