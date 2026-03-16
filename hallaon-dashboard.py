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

st.set_page_config(page_title="Hallaon Workspace", layout="wide")

# =========================
# 🛠️ 구글 스프레드시트 DB 연동 로직
# =========================

def get_gsheets_client():
    # Streamlit Secrets에 저장된 JSON 인증 정보를 불러옵니다.
    try:
        # 🚨 [수정된 부분] st.secrets는 읽기 전용이므로 dict()를 씌워 일반 딕셔너리로 복사합니다.
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        
        # JSON 데이터에서 private_key의 줄바꿈 문자를 처리합니다.
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
        
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"구글 스프레드시트 인증 실패. Secrets 세팅을 확인해주세요.\n오류: {e}")
        st.stop()
        
# 워크시트 이름 정의
WORKSHEET_TASKS = "Tasks"
WORKSHEET_AGENDA = "Agenda"
WORKSHEET_MEETINGS = "Meetings"

def load_gsheet_to_df(worksheet_name):
    # 구글 시트 데이터를 팬더스 데이터프레임으로 불러옵니다.
    client = get_gsheets_client()
    try:
        # 워크스페이스용 구글 시트 제목 (secrets에 저장하는 것을 권장)
        sheet_title = st.secrets.get("GSHEET_TITLE", "Hallaon_Database")
        sheet = client.open(sheet_title)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_values()
        
        if len(data) <= 1: # 데이터가 없거나 헤더만 있는 경우
             return pd.DataFrame(columns=data[0] if data else [])
        
        return pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        st.error(f"'{worksheet_name}' 시트 데이터를 불러오지 못했습니다.\n오류: {e}")
        return pd.DataFrame()

def save_df_to_gsheet(df, worksheet_name):
    # 팬더스 데이터프레임을 구글 시트에 덮어씁니다. (가장 확실한 저장 방식)
    client = get_gsheets_client()
    try:
        sheet_title = st.secrets.get("GSHEET_TITLE", "Hallaon_Database")
        sheet = client.open(sheet_title)
        worksheet = sheet.worksheet(worksheet_name)
        
        worksheet.clear() # 기존 데이터 삭제
        
        # 날짜 데이터 등을 문자열로 변환하고 빈 값을 처리합니다.
        safe_df = df.fillna("")
        
        # 헤더와 데이터를 리스트로 변환하여 업데이트합니다.
        final_data = [safe_df.columns.values.tolist()] + safe_df.values.tolist()
        worksheet.update(final_data)
        
    except Exception as e:
        st.error(f"'{worksheet_name}' 시트에 데이터를 저장하지 못했습니다.\n오류: {e}")

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
# 🎨 UI Style (폰트 깨짐 및 가독성 픽스 완료!)
# =========================
st.markdown("""
<style>
/* 기본 테마 및 배경 */
:root { --bg:#0a1222; --panel:#121d34; --line:#2f4775; --txt:#f4f8ff; --muted:#b5c4e3; --main:#5b97ff; }
.stApp { background: radial-gradient(1200px 650px at 8% -10%, #1c2f56 0%, #0a1222 50%, #091020 100%); color: var(--txt); }

/* targeted color rules: 폰트 깨짐 방지를 위해 Aggressive Div Rule 제거 */
h1, h2, h3, h4, h5, h6, p, div.stMarkdown, div.stText { color: var(--txt) !important; }
div[data-testid="stExpander"] details summary { color: var(--txt) !important; } /* Explorer folder title */
div[data-testid="stMetricLabel"] { color: var(--txt) !important; } /* Metric Label */
div[data-testid="stFormInputLabel"] { color: var(--txt) !important; } /* Form Label */
div.stTab label p { color: var(--txt) !important; } /* Tab label */

/* Muted elements (회의록 분류/날짜 가독성 픽스 핵심!) */
small, [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

/* 기존의 잘 작동하던 디자인 유지 */
section[data-testid="stSidebar"] { background: linear-gradient(180deg,#15213d 0%, #101a30 100%); border-right:1px solid var(--line); }
section[data-testid="stSidebar"] * { color:#ecf3ff !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label { background:#1a2a4b; border:1px solid #35558e; border-radius:10px; padding:8px 10px; margin-bottom:8px; }
div[data-testid="metric-container"] { background: linear-gradient(180deg,#213a69 0%, #1a2f57 100%) !important; border:1px solid #4a6aa5 !important; border-radius:14px !important; }
div[data-testid="stDataFrame"] [role="grid"] { background:#121d34 !important; }
button[kind="primary"] { background:linear-gradient(180deg,#5b97ff 0%, #4b87f3 100%) !important; color:#fff !important; border:none !important; }
button[kind="secondary"] { background:#1a2d52 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }
input, textarea, div[data-baseweb="select"] > div { background:#121d34 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }
.role-badge { display:inline-block; padding:6px 10px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid #4166a6; background:#1a2f57; color:#eaf2ff; }

/* MultiSelect 태그 PM 잘림 방지 */
[data-testid="stMultiSelect"] [data-baseweb="tag"] { background: #ff5c7c !important; border: none !important; border-radius: 8px !important; min-height: 24px !important; padding: 0 8px !important; }
[data-testid="stMultiSelect"] [data-baseweb="tag"] span { color: #fff !important; font-weight: 700 !important; overflow: visible !important; }

/* Calendar fix */
[data-baseweb="calendar"], [data-baseweb="calendar"] * { background: #121d34 !important; color: #f4f8ff !important; border-color: #35558e !important; }
[data-baseweb="calendar"] button { background: transparent !important; }
[data-baseweb="calendar"] [aria-selected="true"] { background: #ff5c7c !important; color: #fff !important; border-radius: 999px !important; }

/* Folder Explorer specific */
.folder-btn button { background: transparent !important; border: none !important; text-align: left !important; justify-content: flex-start !important; padding: 5px 10px !important; font-size: 14px !important;}
.folder-btn button:hover { background: #1f3563 !important; }
.folder-btn button span { color: var(--txt) !important; } /* explorer file title */
.folder-btn button:hover span { color: #ffffff !important; } /* explorer file title on hover */
</style>
""", unsafe_allow_html=True)

# =========================
# Utils
# =========================
def safe_date_str(v):
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return date.today().strftime("%Y-%m-%d")

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
    # 이제 CSV 대신 구글 시트에서 데이터를 불러옵니다.
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

def team_badge(team):
    t = str(team).split(",")[0].strip() if str(team).strip() else "미지정"
    c = TEAM_COLORS.get(t, "#7b8599")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8893a8")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(s)}</span>"

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
# Tab 1 업무 (구글 시트 기반)
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
        # 구글 시트에 저장
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
    # 날짜 데이터를 날짜형으로 변환하여 에디터에 표시
    e["시작일"] = pd.to_datetime(e["시작일"]).date
    e["종료일"] = pd.to_datetime(e["종료일"]).date
    
    edited = st.data_editor(
        e[["선택","업무명","담당자","팀","상태","시작일","종료일"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택"), "상태": st.column_config.SelectboxColumn("상태", options=TASK_STATUS_OPTIONS)}
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("업무 수정사항 저장", type="primary", disabled=not can_edit()):
            base = tasks_df.copy().reset_index(drop=True)
            # 날짜를 다시 문자열로 변환하여 저장
            edited["시작일"] = edited["시작일"].apply(safe_date_str)
            edited["종료일"] = edited["종료일"].apply(safe_date_str)
            base[["업무명","담당자","팀","상태","시작일","종료일"]] = edited[["업무명","담당자","팀","상태","시작일","종료일"]]
            st.session_state.tasks_df = base
            # 구글 시트에 저장
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
                # 구글 시트에 저장
                save_df_to_gsheet(keep, WORKSHEET_TASKS)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()

# =========================
# Tab 2 간트 (구글 시트 데이터 기반)
# =========================
elif menu == "📊 간트 차트":
    st.header("📊 간트 차트 (Agile Tools)")
    hide_done = st.toggle("완료 업무 숨기기", value=True)
    gdf = tasks_df.copy()
    if hide_done: gdf = gdf[~gdf["상태"].str.contains("완료", na=False)].copy()
    
    # Plotly Timeline 차트로 간지나게 표시
    if not gdf.empty:
        gdf["시작일_dt"] = pd.to_datetime(gdf["시작일"])
        gdf["종료일_dt"] = pd.to_datetime(gdf["종료일"]) + timedelta(days=1) # 종료일 당일을 포함하기 위해 1일 추가
        
        fig = px.timeline(gdf, x_start="시작일_dt", x_end="종료일_dt", y="업무명", color="팀", hover_data=["담당자","상태"])
        fig.update_yaxes(autorange="reversed") # 최신 항목이 위로
        fig.update_layout(template="plotly_dark", height=600, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("표시할 업무가 없습니다.")

# =========================
# Tab 3 대시보드
# =========================
elif menu == "📈 대시보드":
    st.header("📈 2026 한라온 종합 대시보드")
    if tasks_df.empty: st.info("업무 데이터가 없습니다.")
    else:
        # 중복 방지를 위해 업무명 기준 유니크 데이터 사용
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
# Tab 4 안건 (구글 시트 기반)
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
        # 구글 시트에 저장
        save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
        st.success("안건이 추가되었습니다.")
        st.rerun()

    # 검색 및 필터링 UI
    st.markdown("---")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: search_q = st.text_input("🔍 안건명 검색", placeholder="안건명을 입력하세요...")
    with c2: team_f = st.selectbox("👥 팀 필터", ["전체"] + TEAM_OPTIONS)
    with c3: status_f = st.selectbox("🏷️ 상태 필터", ["전체"] + AGENDA_STATUS_OPTIONS)

    # 데이터 필터링 적용
    f = agenda_df.copy()
    if search_q: f = f[f["안건명"].str.contains(search_q, case=False, na=False)]
    if team_f != "전체": f = f[f["팀"].str.contains(team_f, na=False)]
    if status_f != "전체": f = f[f["상태"] == status_f]
    # 입안일 최신순 정렬
    f = f.sort_values("입안일", ascending=False)
    st.dataframe(f[["안건명","입안자","팀","상태","입안일"]], use_container_width=True, hide_index=True)

    st.markdown("### 안건 수정/삭제")
    e_a = agenda_df.copy()
    e_a.insert(0, "선택", False)
    # 날짜 데이터 변환
    e_a["입안일"] = pd.to_datetime(e_a["입안일"]).date
    
    edited_a = st.data_editor(
        e_a[["선택","안건명","입안자","팀","상태","입안일"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택"), "상태": st.column_config.SelectboxColumn("상태", options=AGENDA_STATUS_OPTIONS)}
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("안건 수정사항 저장", type="primary", disabled=not can_edit()):
            base = agenda_df.copy().reset_index(drop=True)
            # 날짜 다시 문자열 변환
            edited_a["입안일"] = edited_a["입안일"].apply(safe_date_str)
            base[["안건명","입안자","팀","상태","입안일"]] = edited_a[["안건명","입안자","팀","상태","입안일"]]
            st.session_state.agenda_df = base
            # 구글 시트에 저장
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
                # 구글 시트에 저장
                save_df_to_gsheet(keep, WORKSHEET_AGENDA)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()

# =========================
# Tab 5 회의록 (구글 시트 기반 + UI 폰트 픽스!)
# =========================
elif menu == "📝 회의록":
    st.header("📝 한라온 회의록")
    
    if "sel_mtg_id" not in st.session_state: st.session_state.sel_mtg_id = None
    if "is_edit_mtg" not in st.session_state: st.session_state.is_edit_mtg = False

    col_nav, col_viewer = st.columns([2.5, 7.5])
    
    # ----- 왼쪽: 폴더 탐색기 -----
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

    # ----- 오른쪽: 뷰어/에디터 (폰트 가독성 픽스 완료!) -----
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
                        # 구글 시트에 저장
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
                    
                    # 🔥 [폰트 가독성 픽스] st.caption을 사용하여 분류, 일자, 작성자를 var(--muted) 색상으로 완벽하게 표시!
                    st.caption(f"📁 {mtg['분류']} &nbsp;|&nbsp; 📅 {mtg['회의일자']} &nbsp;|&nbsp; 👤 {mtg['작성자']}")
                    st.markdown("---")
                    st.markdown(mtg['내용']) # 마크다운 형식으로 내용 출력
                    
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    if can_edit() and st.button("🛑 이 회의록 삭제", type="secondary"):
                        keep_m = meetings_df[meetings_df["id"] != mtg['id']].reset_index(drop=True)
                        st.session_state.meetings_df = keep_m
                        # 구글 시트에 저장
                        save_df_to_gsheet(keep_m, WORKSHEET_MEETINGS)
                        st.session_state.sel_mtg_id = None; st.rerun()

                else: # 수정 모드
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
                                # 구글 시트에 저장
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
                    # 워크스페이스 내 데이터 및 세션 상태 업데이트
                    tasks_df["sent"] = tasks_df["id"].apply(lambda x: "True" if x in sent_ids or str(tasks_df.loc[tasks_df["id"]==x, "sent"].iloc[0]) == "True" else "False")
                    st.session_state.tasks_df = tasks_df
                    # 구글 시트에 최종 저장
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
                    # 데이터 및 세션 상태 업데이트
                    agenda_df["sent"] = agenda_df["id"].apply(lambda x: "True" if x in sent_ids or str(agenda_df.loc[agenda_df["id"]==x, "sent"].iloc[0]) == "True" else "False")
                    st.session_state.agenda_df = agenda_df
                    # 구글 시트에 최종 저장
                    save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
                    st.success(msg)
                    st.rerun()
                else: st.error(msg)
