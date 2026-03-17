import os
import uuid
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
from html import escape
import streamlit.components.v1 as components  # 수제 간트차트 렌더링용 추가

st.set_page_config(page_title="Hallaon Workspace", layout="wide")

# =========================
# 🛠️ 구글 스프레드시트 DB 연동 로직
# =========================

def get_gsheets_client():
    try:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"구글 인증 실패. Secrets 세팅을 확인해주세요.\n오류: {e}")
        st.stop()

# 워크시트 이름 정의
WORKSHEET_TASKS = "Tasks"
WORKSHEET_AGENDA = "Agenda"
WORKSHEET_MEETINGS = "Meetings"

def get_sheet():
    client = get_gsheets_client()
    sheet_url = st.secrets.get("GSHEET_URL", "")
    if sheet_url:
        return client.open_by_url(sheet_url)
    else:
        st.error("Secrets에 GSHEET_URL이 설정되지 않았습니다.")
        st.stop()

def load_gsheet_to_df(worksheet_name):
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_values()
        if len(data) <= 1: return pd.DataFrame(columns=data[0] if data else [])
        return pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        st.error(f"'{worksheet_name}' 시트를 불러오지 못했습니다. URL과 시트 탭 이름을 확인하세요.\n오류: {e}")
        return pd.DataFrame()

def save_df_to_gsheet(df, worksheet_name):
    try:
        sheet = get_sheet()
        worksheet = sheet.worksheet(worksheet_name)
        worksheet.clear() 
        safe_df = df.fillna("")
        final_data = [safe_df.columns.values.tolist()] + safe_df.values.tolist()
        worksheet.update(final_data)
    except Exception as e:
        st.error(f"'{worksheet_name}' 시트에 저장하지 못했습니다.\n오류: {e}")

# =========================
# Config & Data Constants
# =========================
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")
EDIT_PASSWORD = st.secrets.get("EDIT_PASSWORD", "")
VIEW_PASSWORD = st.secrets.get("VIEW_PASSWORD", "")

TEAM_OPTIONS = ["PM", "CD", "FS", "DM", "OPS"]
TASK_STATUS_OPTIONS = ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"]
AGENDA_STATUS_OPTIONS = ["시작 전", "진행 중", "완료", "보류"]

TEAM_COLORS = {"PM": "#4f8cff", "CD": "#ff5c7c", "FS": "#14c9a2", "DM": "#8b6cff", "OPS": "#f5b031"}
STATUS_COLORS = {
    "완료": "#10c27c", "막힘": "#ef4e4e", "진행 중": "#f5b031", "작업 중": "#f5b031",
    "대기": "#8b6cff", "시작 전": "#8893a8", "보류": "#7f8aa3"
}

# =========================
# 🎨 UI Style 
# =========================
st.markdown("""
<style>
/* Streamlit 기본 UI 숨기기 (앱처럼 보이게) */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* 글로벌 변수 및 배경 */
:root { 
    --bg: #0a1222; --panel: #121d34; --line: #2f4775; 
    --txt: #f4f8ff; --muted: #b5c4e3; --main: #5b97ff; 
}
.stApp { 
    background: radial-gradient(circle at 50% 0%, #1c2f56 0%, #0a1222 60%, #091020 100%);
    color: var(--txt); 
}

/* 텍스트 색상 강제 지정 */
h1, h2, h3, h4, h5, h6, p, div.stMarkdown, div.stText { color: var(--txt) !important; }
small, [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

/* 사이드바 디자인 (모서리 둥글게, 그림자 추가) */
section[data-testid="stSidebar"] { 
    background: linear-gradient(180deg, #15213d 0%, #0a1222 100%); 
    border-right: 1px solid var(--line); 
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label { 
    background: #1a2a4b; border: 1px solid #35558e; 
    border-radius: 12px; /* 더 둥글게 */
    padding: 10px 14px; margin-bottom: 8px; 
    transition: all 0.2s ease-in-out; /* 호버 애니메이션 */
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
    background: #213a69; transform: translateY(-1px);
}

/* 버튼 디자인 (쫀득한 누름 효과) */
button[kind="primary"] { 
    background: linear-gradient(180deg, #5b97ff 0%, #4b87f3 100%) !important; 
    color: #fff !important; border: none !important; 
    border-radius: 10px !important; font-weight: bold !important;
    box-shadow: 0 4px 10px rgba(91, 151, 255, 0.3) !important;
    transition: all 0.2s;
}
button[kind="primary"]:active { transform: scale(0.97); } /* 클릭 시 살짝 작아짐 */

/* 입력창 및 Expander (카드 느낌) */
input, textarea, div[data-baseweb="select"] > div { 
    background: #121d34 !important; color: #f4f8ff !important;
    border: 1px solid #35558e !important; border-radius: 8px !important;
}
div[data-testid="stExpander"] details { 
    background: rgba(18, 29, 52, 0.6) !important; 
    border: 1px solid #2f4775 !important;
    border-radius: 12px !important; backdrop-filter: blur(10px);
}
</style>
""", unsafe_allow_html=True)

# =========================
# Utils & UI 렌더링 함수
# =========================
def safe_date_str(v):
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return date.today().strftime("%Y-%m-%d")

def team_badge(team):
    t = str(team).split(",")[0].strip() if str(team).strip() else "미지정"
    c = TEAM_COLORS.get(t, "#7b8599")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8893a8")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(s)}</span>"

def render_gantt(df):
    if df.empty:
        return "<div style='padding:12px;color:#b5c4e3;'>표시할 업무가 없습니다.</div>"
    g = df.copy()
    g["시작일_dt"] = pd.to_datetime(g["시작일"], errors="coerce")
    g["종료일_dt"] = pd.to_datetime(g["종료일"], errors="coerce")
    g = g.dropna(subset=["시작일_dt","종료일_dt"])
    if g.empty:
        return "<div style='padding:12px;color:#b5c4e3;'>날짜 데이터가 유효하지 않습니다.</div>"

    min_d = g["시작일_dt"].min().date()
    max_d = g["종료일_dt"].max().date()
    tl_start = min_d - timedelta(days=min_d.weekday())
    days_total = max((max_d - tl_start).days + 14, 35)
    days_total = ((days_total // 7) + 1) * 7
    weeks = days_total // 7
    tl_end = tl_start + timedelta(days=days_total)
    step = 1 if weeks <= 12 else 2 if weeks <= 24 else 4

    h = ""
    h += "<style>"
    h += ".gw{background:#101a2f;border:1px solid #2f4775;border-radius:12px;overflow:auto;box-shadow:0 10px 26px rgba(0,0,0,.25);}"
    h += ".gh{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:#13213b;border-bottom:1px solid #2f4775;}"
    h += ".chip{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:7px;background:#1a2c50;border:1px solid #365a95;color:#f4f8ff;font-size:11px;font-weight:700;margin-right:8px;}"
    h += ".dot{width:8px;height:8px;border-radius:50%;display:inline-block;}"
    h += ".gt{width:100%;min-width:1280px;border-collapse:collapse;table-layout:fixed;}"
    h += ".gt th,.gt td{border-right:1px solid #243a64;border-bottom:1px solid #243a64;color:#f4f8ff;padding:9px 8px;white-space:nowrap;}"
    h += ".gt th{background:#162746;font-size:12px;font-weight:700;}"
    h += ".wkh{min-width:92px;text-align:center;font-size:11px;color:#c9d8f4;}"
    h += ".tl{padding:0 !important;position:relative;background:#101a2f;}"
    h += ".bg{position:absolute;inset:0;display:flex;pointer-events:none;}"
    h += ".bgc{flex:1;border-right:1px solid #243a64;background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.00));}"
    h += ".bgc:nth-child(even){background:linear-gradient(180deg, rgba(79,140,255,.06), rgba(79,140,255,.02));}"
    h += ".barw{position:relative;height:44px;display:flex;align-items:center;}"
    h += ".bar{position:absolute;height:24px;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:700;color:#fff;overflow:hidden;text-overflow:ellipsis;box-shadow:0 3px 8px rgba(0,0,0,.28);}"
    h += ".owner{display:inline-flex;align-items:center;gap:7px;}"
    h += ".av{width:21px;height:21px;border-radius:50%;background:#30466d;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;}"
    h += "</style>"

    h += "<div class='gw'><div class='gh'><div>"
    for t, c in TEAM_COLORS.items():
        h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += "</div><div style='color:#b5c4e3;font-size:12px;font-weight:700;'>간트 차트 (Agile Tools)</div></div>"
    h += "<table class='gt'><thead><tr>"
    h += "<th style='width:72px;text-align:center;'>TEAM</th><th style='width:230px;'>업무명</th><th style='width:130px;'>담당자</th><th style='width:110px;'>상태</th>"
    for i in range(weeks):
        ws = tl_start + timedelta(days=i*7)
        full = f"Week {i+1} ({ws.month}/{ws.day}~)"
        txt = full if i % step == 0 else "·"
        h += f"<th class='wkh' title='{full}'>{txt}</th>"
    h += "</tr></thead><tbody>"

    for _, r in g.iterrows():
        team = str(r["팀"]).split(",")[0].strip() if str(r["팀"]).strip() else "미지정"
        owner = str(r["담당자"]).strip() if str(r["담당자"]).strip() else "담당자 미정"
        status = str(r["상태"]).strip()
        task = str(r["업무명"]).strip()
        c = TEAM_COLORS.get(team, "#7b8599")

        s = r["시작일_dt"].date()
        e = r["종료일_dt"].date()
        cs = max(s, tl_start)
        ce = min(e + timedelta(days=1), tl_end)
        off = (cs - tl_start).days
        dur = max((ce - cs).days, 1)
        left = (off / days_total) * 100
        width = (dur / days_total) * 100
        label = "✓ Done" if "완료" in status else "Blocked" if "막힘" in status else "In Progress" if ("진행" in status or "작업" in status) else "Scheduled"
        av = owner[0] if owner else "?"
        bg = "".join(["<div class='bgc'></div>" for _ in range(weeks)])

        h += "<tr>"
        h += f"<td style='text-align:center;'>{team_badge(team)}</td>"
        h += f"<td style='font-weight:700;'>{escape(task)}</td>"
        h += f"<td><span class='owner'><span class='av'>{escape(av)}</span>{escape(owner)}</span></td>"
        h += f"<td>{status_badge(status)}</td>"
        h += f"<td colspan='{weeks}' class='tl'><div class='bg'>{bg}</div><div class='barw'><div class='bar' style='left:{left}%;width:{width}%;background:{c};'>{escape(label)}</div></div></td>"
        h += "</tr>"

    h += "</tbody></table></div>"
    return h

def normalize_tasks_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","업무명","담당자","팀","상태","시작일","종료일","sent"])
    req = ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    d["시작일"] = d["시작일"].apply(safe_date_str)
    d["종료일"] = d["종료일"].apply(safe_date_str)
    return d[req].fillna("")

def normalize_agenda_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","안건명","입안자","팀","상태","입안일","sent"])
    req = ["id","안건명","입안자","팀","상태","입안일","sent"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    d["입안일"] = d["입안일"].apply(safe_date_str)
    return d[req].fillna("")

def normalize_meetings_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","분류","회의일자","제목","작성자","내용"])
    req = ["id","분류","회의일자","제목","작성자","내용"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    d["회의일자"] = d["회의일자"].apply(safe_date_str)
    return d[req].fillna("")

def init_data():
    t = normalize_tasks_df(load_gsheet_to_df(WORKSHEET_TASKS))
    a = normalize_agenda_df(load_gsheet_to_df(WORKSHEET_AGENDA))
    m = normalize_meetings_df(load_gsheet_to_df(WORKSHEET_MEETINGS))
    st.session_state.tasks_df = t
    st.session_state.agenda_df = a
    st.session_state.meetings_df = m

def auth_gate():
    if EDIT_PASSWORD == "" and VIEW_PASSWORD == "":
        st.session_state.role = "edit"
        return
    if st.session_state.get("role") is not None: return
    st.title("🔐 로그인")
    role_choice = st.radio("권한", ["조회", "편집"], horizontal=True)
    pw = st.text_input("비밀번호", type="password")
    if st.button("로그인", type="primary"):
        if role_choice == "편집" and pw == EDIT_PASSWORD: st.session_state.role = "edit"; st.rerun()
        elif role_choice == "조회" and pw == VIEW_PASSWORD: st.session_state.role = "view"; st.rerun()
        else: st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

def can_edit(): return st.session_state.get("role") == "edit"

def send_discord(fields, title, username, color=3447003):
    if not DISCORD_WEBHOOK_URL: return False, "DISCORD_WEBHOOK_URL이 설정되지 않았습니다."
    try:
        sent = 0
        for i in range(0, len(fields), 25):
            batch = fields[i:i+25]
            payload = {
                "username": username,
                "embeds": [{"title": title, "color": color, "fields": batch, "footer": {"text": f"Hallaon Agile • {len(batch)}개"}}]
            }
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if r.status_code not in (200, 204): return False, f"HTTP {r.status_code}: {r.text[:120]}"
            sent += len(batch)
        return True, f"{sent}개 전송 완료"
    except Exception as e: return False, str(e)

# =========================
# Init
# =========================
if "tasks_df" not in st.session_state: init_data()
auth_gate()

tasks_df = st.session_state.tasks_df.copy()
agenda_df = st.session_state.agenda_df.copy()
meetings_df = st.session_state.meetings_df.copy()

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.title("🏛️ Hallaon")
    st.markdown(f"<span class='role-badge'>권한: {'편집' if can_edit() else '조회'}</span>", unsafe_allow_html=True)
    if st.button("새로고침/권한전환"):
        init_data()
        st.session_state.role = None
        st.rerun()
    st.markdown("---")
    menu = st.radio(
        "워크스페이스 메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🗂️ 안건", "📝 회의록", "🤖 최근 등록된 작업 전송"]
    )

# =========================
# Tab 1 업무 
# =========================
if menu == "📋 2026 한라온":
    st.header("📋 2026 한라온")
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    with st.form("add_task_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            업무명 = st.text_input("업무명")
            담당자 = st.text_input("담당자")
        with c2:
            팀 = st.multiselect("팀", TEAM_OPTIONS, default=[])
            상태 = st.selectbox("상태", TASK_STATUS_OPTIONS, index=0)
        with c3:
            시작일 = st.date_input("시작일", value=date.today())
            종료일 = st.date_input("종료일", value=date.today())
        add_btn = st.form_submit_button("업무 추가", type="primary", disabled=not can_edit())

    if add_btn and 업무명.strip():
        new_row = {
            "id": str(uuid.uuid4()), "업무명": 업무명.strip(), "담당자": 담당자.strip() or "담당자 미정",
            "팀": ", ".join(팀) or "미지정", "상태": 상태, "시작일": safe_date_str(시작일), "종료일": safe_date_str(종료일), "sent": "False"
        }
        tasks_df = pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.tasks_df = tasks_df
        save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
        st.success("업무가 추가되었습니다.")
        st.rerun()

    todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)].copy()
    done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)].copy()

    with st.expander(f"할 일 ({len(todo_df)}개)", expanded=True):
        st.dataframe(todo_df[["업무명","담당자","팀","상태","시작일","종료일"]], use_container_width=True, hide_index=True)

    with st.expander(f"완료됨 ({len(done_df)}개)", expanded=False):
        st.dataframe(done_df[["업무명","담당자","팀","상태","시작일","종료일"]], use_container_width=True, hide_index=True)

    st.markdown("### 업무 수정/삭제")
    e = tasks_df.copy()
    e.insert(0, "선택", False)
    
    e["시작일"] = pd.to_datetime(e["시작일"]).dt.date
    e["종료일"] = pd.to_datetime(e["종료일"]).dt.date
    
    edited = st.data_editor(
        e[["선택","업무명","담당자","팀","상태","시작일","종료일"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택"), "상태": st.column_config.SelectboxColumn("상태", options=TASK_STATUS_OPTIONS)}
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("업무 수정사항 저장", type="primary", disabled=not can_edit()):
            base = tasks_df.copy().reset_index(drop=True)
            edited["시작일"] = edited["시작일"].apply(safe_date_str)
            edited["종료일"] = edited["종료일"].apply(safe_date_str)
            base[["업무명","담당자","팀","상태","시작일","종료일"]] = edited[["업무명","담당자","팀","상태","시작일","종료일"]]
            st.session_state.tasks_df = base
            save_df_to_gsheet(base, WORKSHEET_TASKS)
            st.success("수정사항이 저장되었습니다.")
            st.rerun()
    with c2:
        if st.button("선택 업무 삭제", disabled=not can_edit()):
            idx = edited.index[edited["선택"] == True].tolist()
            if not idx: st.warning("삭제할 업무를 선택하세요.")
            else:
                keep = tasks_df.drop(index=idx).reset_index(drop=True)
                st.session_state.tasks_df = keep
                save_df_to_gsheet(keep, WORKSHEET_TASKS)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()

# =========================
# Tab 2 간트 (수제 간트차트 렌더링!)
# =========================
elif menu == "📊 간트 차트":
    st.header("📊 간트 차트 (Agile Tools)")
    hide_done = st.toggle("완료 업무 숨기기", value=True)
    gdf = tasks_df.copy()
    if hide_done: 
        gdf = gdf[~gdf["상태"].str.contains("완료", na=False)].copy()
    
    # HTML 수제 간트 차트 렌더링
    components.html(render_gantt(gdf), height=max(700, len(gdf)*56 + 230), scrolling=True)

# =========================
# Tab 3 대시보드
# =========================
elif menu == "📈 대시보드":
    st.header("📈 2026 한라온 종합 대시보드")
    if tasks_df.empty: st.info("업무 데이터가 없습니다.")
    else:
        unique_df = tasks_df.drop_duplicates(subset=['업무명'])
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 전체 태스크", len(unique_df))
        m2.metric("⏳ 진행 중", len(unique_df[unique_df['상태'].str.contains('진행|작업', na=False)]))
        m3.metric("🛑 막힘", len(unique_df[unique_df['상태'].str.contains('막힘', na=False)]))
        m4.metric("✅ 완료", len(unique_df[unique_df['상태'].str.contains('완료', na=False)]))

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("##### 📊 상태별 태스크")
            s = unique_df["상태"].value_counts().reset_index()
            s.columns = ["상태","개수"]
            fig1 = px.pie(s, names="상태", values="개수", hole=0.5, color="상태", color_discrete_map=STATUS_COLORS)
            fig1.update_layout(template="plotly_dark", height=380, showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig1, use_container_width=True)
        with chart_col2:
            st.markdown("##### 👤 소유자별 태스크")
            a = unique_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#5b97ff"])
            fig2.update_layout(template="plotly_dark", height=380, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# Tab 4 안건
# =========================
elif menu == "🗂️ 안건":
    st.header("🗂️ 안건")
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    with st.form("add_agenda_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: 안건명 = st.text_input("안건명")
        with c2: 팀 = st.multiselect("팀", TEAM_OPTIONS, default=[])
        with c3: 입안자 = st.text_input("입안자")
        with c4: 입안일 = st.date_input("입안일", value=date.today())
        상태 = st.selectbox("상태", AGENDA_STATUS_OPTIONS, index=0)
        add_btn = st.form_submit_button("안건 추가", type="primary", disabled=not can_edit())

    if add_btn and 안건명.strip():
        new_row = {
            "id": str(uuid.uuid4()), "안건명": 안건명.strip(), "입안자": 입안자.strip() or "담당자 미정",
            "팀": ", ".join(팀) or "미지정", "상태": 상태, "입안일": safe_date_str(입안일), "sent": "False"
        }
        agenda_df = pd.concat([agenda_df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.agenda_df = agenda_df
        save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
        st.success("안건이 추가되었습니다.")
        st.rerun()

    st.markdown("---")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: search_q = st.text_input("🔍 안건명 검색", placeholder="안건명을 입력하세요...")
    with c2: team_f = st.selectbox("👥 팀 필터", ["전체"] + TEAM_OPTIONS)
    with c3: status_f = st.selectbox("🏷️ 상태 필터", ["전체"] + AGENDA_STATUS_OPTIONS)

    f = agenda_df.copy()
    if search_q: f = f[f["안건명"].str.contains(search_q, case=False, na=False)]
    if team_f != "전체": f = f[f["팀"].str.contains(team_f, na=False)]
    if status_f != "전체": f = f[f["상태"] == status_f]
    f = f.sort_values("입안일", ascending=False)
    st.dataframe(f[["안건명","입안자","팀","상태","입안일"]], use_container_width=True, hide_index=True)

    st.markdown("### 안건 수정/삭제")
    e_a = agenda_df.copy()
    e_a.insert(0, "선택", False)
    
    e_a["입안일"] = pd.to_datetime(e_a["입안일"]).dt.date
    
    edited_a = st.data_editor(
        e_a[["선택","안건명","입안자","팀","상태","입안일"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택"), "상태": st.column_config.SelectboxColumn("상태", options=AGENDA_STATUS_OPTIONS)}
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("안건 수정사항 저장", type="primary", disabled=not can_edit()):
            base = agenda_df.copy().reset_index(drop=True)
            edited_a["입안일"] = edited_a["입안일"].apply(safe_date_str)
            base[["안건명","입안자","팀","상태","입안일"]] = edited_a[["안건명","입안자","팀","상태","입안일"]]
            st.session_state.agenda_df = base
            save_df_to_gsheet(base, WORKSHEET_AGENDA)
            st.success("안건 수정사항이 저장되었습니다.")
            st.rerun()
    with c2:
        if st.button("선택 안건 삭제", disabled=not can_edit()):
            idx = edited_a.index[edited_a["선택"] == True].tolist()
            if not idx: st.warning("삭제할 안건을 선택하세요.")
            else:
                keep = agenda_df.drop(index=idx).reset_index(drop=True)
                st.session_state.agenda_df = keep
                save_df_to_gsheet(keep, WORKSHEET_AGENDA)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()

# =========================
# Tab 5 회의록
# =========================
elif menu == "📝 회의록":
    st.header("📝 한라온 회의록")
    
    if "sel_mtg_id" not in st.session_state: st.session_state.sel_mtg_id = None
    if "is_edit_mtg" not in st.session_state: st.session_state.is_edit_mtg = False

    col_nav, col_viewer = st.columns([2.5, 7.5])
    
    with col_nav:
        st.markdown("#### 📂 분류")
        if st.button("➕ 새 회의록 작성", use_container_width=True, disabled=not can_edit()):
            st.session_state.sel_mtg_id = "NEW"; st.session_state.is_edit_mtg = True; st.rerun()
            
        st.markdown("<br>", unsafe_allow_html=True)
        folders = ["전체 회의"] + TEAM_OPTIONS
        for folder in folders:
            f_df = meetings_df[meetings_df["분류"] == folder].sort_values("회의일자", ascending=False)
            with st.expander(f"📁 {folder} ({len(f_df)})", expanded=True):
                if f_df.empty: st.caption("회의록 없음")
                else:
                    for _, r in f_df.iterrows():
                        st.markdown('<div class="folder-btn">', unsafe_allow_html=True)
                        if st.button(f"📄 {r['회의일자'][2:]} {r['제목']}", key=f"mtg_{r['id']}", use_container_width=True):
                            st.session_state.sel_mtg_id = r["id"]; st.session_state.is_edit_mtg = False; st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

    with col_viewer:
        st.markdown("<div style='border-left: 1px solid #2f4775; padding-left: 30px; min-height: 600px;'>", unsafe_allow_html=True)
        
        if st.session_state.sel_mtg_id is None:
            st.info("👈 왼쪽 폴더에서 회의록을 선택하거나, '새 회의록 작성'을 눌러주세요.")
            
        elif st.session_state.sel_mtg_id == "NEW":
            st.subheader("✨ 새 회의록 작성")
            with st.form("new_mtg_form"):
                f_title = st.text_input("회의 제목")
                c1, c2, c3 = st.columns(3)
                with c1: f_folder = st.selectbox("분류(폴더)", ["전체 회의"] + TEAM_OPTIONS)
                with c2: f_date = st.date_input("회의 일자", value=date.today())
                with c3: f_author = st.text_input("작성자")
                f_content = st.text_area("회의 내용 (Markdown 지원)", height=450)
                if st.form_submit_button("저장하기", type="primary"):
                    if not f_title: st.warning("제목을 입력하세요.")
                    else:
                        new_row = {
                            "id": str(uuid.uuid4()), "분류": f_folder, "회의일자": safe_date_str(f_date),
                            "제목": f_title, "작성자": f_author, "내용": f_content
                        }
                        meetings_df = pd.concat([meetings_df, pd.DataFrame([new_row])], ignore_index=True)
                        st.session_state.meetings_df = meetings_df
                        save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                        st.session_state.sel_mtg_id = new_row["id"]; st.session_state.is_edit_mtg = False; st.rerun()
                            
        else:
            m_data = meetings_df[meetings_df["id"] == st.session_state.sel_mtg_id]
            if m_data.empty: st.error("회의록을 찾을 수 없습니다.")
            else:
                mtg = m_data.iloc[0]
                if not st.session_state.is_edit_mtg:
                    c_h, c_b = st.columns([8, 2])
                    with c_h: st.markdown(f"## {mtg['제목']}")
                    with c_b:
                        if can_edit() and st.button("✏️ 수정", use_container_width=True):
                            st.session_state.is_edit_mtg = True; st.rerun()
                    
                    st.caption(f"📁 {mtg['분류']} &nbsp;|&nbsp; 📅 {mtg['회의일자']} &nbsp;|&nbsp; 👤 {mtg['작성자']}")
                    st.markdown("---")
                    st.markdown(mtg['내용'].replace('\n', '  \n')) 
                    
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if can_edit() and st.button("🛑 이 회의록 삭제", type="secondary"):
                        keep_m = meetings_df[meetings_df["id"] != mtg['id']].reset_index(drop=True)
                        st.session_state.meetings_df = keep_m
                        save_df_to_gsheet(keep_m, WORKSHEET_MEETINGS)
                        st.session_state.sel_mtg_id = None; st.rerun()

                else: 
                    st.subheader("✏️ 회의록 수정")
                    with st.form("edit_mtg_form"):
                        f_title = st.text_input("회의 제목", value=mtg['제목'])
                        c1, c2, c3 = st.columns(3)
                        with c1: f_folder = st.selectbox("분류(폴더)", ["전체 회의"] + TEAM_OPTIONS, index=(["전체 회의"]+TEAM_OPTIONS).index(mtg['분류']))
                        with c2: f_date = st.date_input("회의 일자", value=pd.to_datetime(mtg['회의일자']).date())
                        with c3: f_author = st.text_input("작성자", value=mtg['작성자'])
                        f_content = st.text_area("회의 내용", value=mtg['내용'], height=450)
                        
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            if st.form_submit_button("저장하기", type="primary"):
                                idx = meetings_df.index[meetings_df["id"] == mtg['id']].tolist()[0]
                                meetings_df.at[idx, '제목'] = f_title
                                meetings_df.at[idx, '분류'] = f_folder
                                meetings_df.at[idx, '회의일자'] = safe_date_str(f_date)
                                meetings_df.at[idx, '작성자'] = f_author
                                meetings_df.at[idx, '내용'] = f_content
                                st.session_state.meetings_df = meetings_df
                                save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                                st.session_state.is_edit_mtg = False; st.rerun()
                        with btn_c2:
                            if st.form_submit_button("취소"): st.session_state.is_edit_mtg = False; st.rerun()
                                    
        st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Tab 6 전송
# =========================
elif menu == "🤖 최근 등록된 작업 전송":
    st.header("🤖 최근 등록된 작업 전송")
    if not can_edit(): st.info("조회 권한에서는 전송이 불가합니다. '권한 전환'으로 로그인하세요.")

    t_task, t_agenda = st.tabs(["업무 전송", "안건 전송"])

    with t_task:
        u_tasks = tasks_df[tasks_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u_tasks.empty: st.info("미전송 업무가 없습니다.")
        else:
            v_t = u_tasks.copy()
            v_t.insert(0, "전송", False)
            pick_t = st.data_editor(
                v_t[["전송","업무명","담당자","팀","상태","시작일","종료일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            selected_task_indices = pick_t.index[pick_t["전송"] == True].tolist()
            if st.button("🚀 선택 업무 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_task_indices)):
                sel_tasks = u_tasks.iloc[selected_task_indices].copy()
                fields = [{
                    "name": f"🔹 {r['업무명']} ({r['팀']})",
                    "value": f"👤 담당: {r['담당자']}\n🏷️ 상태: {r['상태']}\n📅 일정: {r['시작일']} → {r['종료일']}",
                    "inline": False
                } for _, r in sel_tasks.iterrows()]
                
                ok, msg = send_discord(fields, "🔔 신규 업무 알림", "Hallaon Roadmap Bot", color=3447003)
                if ok:
                    sent_ids = set(sel_tasks["id"].tolist())
                    tasks_df["sent"] = tasks_df["id"].apply(lambda x: "True" if x in sent_ids or str(tasks_df.loc[tasks_df["id"]==x, "sent"].iloc[0]) == "True" else "False")
                    st.session_state.tasks_df = tasks_df
                    save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
                    st.success(msg)
                    st.rerun()
                else: st.error(msg)

    with t_agenda:
        u_agendas = agenda_df[agenda_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u_agendas.empty: st.info("미전송 안건가 없습니다.")
        else:
            v_a = u_agendas.copy()
            v_a.insert(0, "전송", False)
            pick_a = st.data_editor(
                v_a[["전송","안건명","입안자","팀","상태","입안일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            selected_agenda_indices = pick_a.index[pick_a["전송"] == True].tolist()
            if st.button("📨 선택 안건 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_agenda_indices)):
                sel_agendas = u_agendas.iloc[selected_agenda_indices].copy()
                fields = [{
                    "name": f"🗂️ {r['안건명']} ({r['팀']})",
                    "value": f"👤 입안: {r['입안자']}\n🏷️ 상태: {r['상태']}\n📅 입안일: {r['입안일']}",
                    "inline": False
                } for _, r in sel_agendas.iterrows()]
                
                ok, msg = send_discord(fields, "📌 신규 안건 알림", "Hallaon Agenda Bot", color=5793266)
                if ok:
                    sent_ids = set(sel_agendas["id"].tolist())
                    agenda_df["sent"] = agenda_df["id"].apply(lambda x: "True" if x in sent_ids or str(agenda_df.loc[agenda_df["id"]==x, "sent"].iloc[0]) == "True" else "False")
                    st.session_state.agenda_df = agenda_df
                    save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
                    st.success(msg)
                    st.rerun()
                else: st.error(msg)
