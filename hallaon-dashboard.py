import os
import uuid
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, date, timedelta
from html import escape

st.set_page_config(page_title="Hallaon Workspace", layout="wide")

# =========================
# Config & Data Constants
# =========================
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")
EDIT_PASSWORD = st.secrets.get("EDIT_PASSWORD", "")
VIEW_PASSWORD = st.secrets.get("VIEW_PASSWORD", "")

TASKS_CSV = "tasks_data.csv"
AGENDA_CSV = "agenda_data.csv"
MEETINGS_CSV = "meetings_data.csv"  # 회의록 저장용 CSV 추가

TEAM_OPTIONS = ["PM", "CD", "FS", "DM", "OPS"]
TASK_STATUS_OPTIONS = ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"]
AGENDA_STATUS_OPTIONS = ["시작 전", "진행 중", "완료", "보류"]

TEAM_COLORS = {"PM": "#4f8cff", "CD": "#ff5c7c", "FS": "#14c9a2", "DM": "#8b6cff", "OPS": "#f5b031"}
STATUS_COLORS = {
    "완료": "#10c27c", "막힘": "#ef4e4e", "진행 중": "#f5b031", "작업 중": "#f5b031",
    "대기": "#8b6cff", "시작 전": "#8893a8", "보류": "#7f8aa3"
}

# =========================
# Style
# =========================
st.markdown("""
<style>
:root { --bg:#0a1222; --panel:#121d34; --line:#2f4775; --txt:#f4f8ff; --muted:#b5c4e3; }
.stApp { background: radial-gradient(1200px 650px at 8% -10%, #1c2f56 0%, #0a1222 50%, #091020 100%); color: var(--txt); }
h1,h2,h3,h4,h5,h6,p,span,label,div { color: var(--txt) !important; }
small,[data-testid="stCaptionContainer"] * { color: var(--muted) !important; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg,#15213d 0%, #101a30 100%); border-right:1px solid var(--line); }
section[data-testid="stSidebar"] * { color:#ecf3ff !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label { background:#1a2a4b; border:1px solid #35558e; border-radius:10px; padding:8px 10px; margin-bottom:8px; }
div[data-testid="metric-container"] { background: linear-gradient(180deg,#213a69 0%, #1a2f57 100%) !important; border:1px solid #4a6aa5 !important; border-radius:14px !important; }
div[data-testid="stExpander"] details { background:#121d34 !important; border:1px solid #2f4775 !important; border-radius:10px !important; }
div[data-testid="stExpander"] summary { background:#121d34 !important; color:#f4f8ff !important; }
div[data-testid="stDataFrame"] [role="grid"] { background:#121d34 !important; }
button[kind="primary"] { background:linear-gradient(180deg,#5b97ff 0%, #4b87f3 100%) !important; color:#fff !important; border:none !important; }
button[kind="secondary"] { background:#1a2d52 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }
input, textarea { background:#121d34 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }
.role-badge { display:inline-block; padding:6px 10px; border-radius:999px; font-size:12px; font-weight:700; border:1px solid #4166a6; background:#1a2f57; color:#eaf2ff; }
/* 폴더 탐색기용 버튼 스타일 투명화 */
.folder-btn button { background: transparent !important; border: none !important; text-align: left !important; justify-content: flex-start !important; padding: 5px 10px !important; font-size: 14px !important;}
.folder-btn button:hover { background: #1f3563 !important; }
</style>
""", unsafe_allow_html=True)

# =========================
# Utils
# =========================
def safe_date_str(v):
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return date.today().strftime("%Y-%m-%d")

def load_csv(path, default_cols):
    if os.path.exists(path): df = pd.read_csv(path, dtype=str).fillna("")
    else: df = pd.DataFrame(columns=default_cols)
    for c in default_cols:
        if c not in df.columns: df[c] = ""
    return df[default_cols].copy()

def save_csv(df, path):
    df.to_csv(path, index=False)

def normalize_tasks_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","업무명","담당자","팀","상태","시작일","종료일","sent"])
    req = ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x else x)
    d["시작일"] = d["시작일"].apply(safe_date_str)
    d["종료일"] = d["종료일"].apply(safe_date_str)
    return d[req].fillna("")

def normalize_agenda_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","안건명","입안자","팀","상태","입안일","sent"])
    req = ["id","안건명","입안자","팀","상태","입안일","sent"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x else x)
    d["입안일"] = d["입안일"].apply(safe_date_str)
    return d[req].fillna("")

def normalize_meetings_df(df):
    # 회의록 정규화 함수
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","분류","회의일자","제목","작성자","내용"])
    req = ["id","분류","회의일자","제목","작성자","내용"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x else x)
    d["회의일자"] = d["회의일자"].apply(safe_date_str)
    return d[req].fillna("")

def init_data():
    t = normalize_tasks_df(load_csv(TASKS_CSV, ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]))
    a = normalize_agenda_df(load_csv(AGENDA_CSV, ["id","안건명","입안자","팀","상태","입안일","sent"]))
    m = normalize_meetings_df(load_csv(MEETINGS_CSV, ["id","분류","회의일자","제목","작성자","내용"]))
    st.session_state.tasks_df = t
    st.session_state.agenda_df = a
    st.session_state.meetings_df = m
    save_csv(t, TASKS_CSV)
    save_csv(a, AGENDA_CSV)
    save_csv(m, MEETINGS_CSV)

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

# --- (이전 탭 코드들 생략 없이 그대로 유지... 길이를 위해 본 답변에서는 생략 처리하지만, 실제로는 위에 있는 탭 1~4, 6 코드가 그대로 들어갑니다. 편의상 '회의록 탭' 부분만 상세히 보여드립니다.) ---

if menu == "📋 2026 한라온":
    st.info("기존 업무 탭 코드 유지...") # 실제 적용 시에는 기존 탭 코드를 넣으세요!
    
# =========================
# Tab 5 회의록 (새로 추가됨!)
# =========================
elif menu == "📝 회의록":
    st.header("📝 한라온 회의록")
    
    # 세션 상태 초기화 (어떤 회의록을 열어볼지, 편집 모드인지 기억)
    if "sel_meeting_id" not in st.session_state:
        st.session_state.sel_meeting_id = None
    if "is_editing_mtg" not in st.session_state:
        st.session_state.is_editing_mtg = False

    # 화면을 파일 탐색기처럼 3:7 비율로 나눔
    col_nav, col_viewer = st.columns([2.5, 7.5])
    
    # ----- 왼쪽: 파일 탐색기 영역 -----
    with col_nav:
        st.markdown("#### 📂 분류")
        if st.button("➕ 새 회의록 작성", use_container_width=True, disabled=not can_edit()):
            st.session_state.sel_meeting_id = "NEW"
            st.session_state.is_editing_mtg = True
            st.rerun()
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 폴더 리스트 생성 (전체회의 + 팀별)
        folders = ["전체 회의"] + TEAM_OPTIONS
        for folder in folders:
            folder_df = meetings_df[meetings_df["분류"] == folder].sort_values("회의일자", ascending=False)
            with st.expander(f"📁 {folder} ({len(folder_df)})", expanded=True):
                if folder_df.empty:
                    st.caption("회의록 없음")
                else:
                    for _, r in folder_df.iterrows():
                        # 스트림릿 버튼을 파일 목록처럼 보이게 만듦
                        btn_label = f"📄 {r['회의일자'][2:]} {r['제목']}"
                        st.markdown('<div class="folder-btn">', unsafe_allow_html=True)
                        if st.button(btn_label, key=f"btn_{r['id']}", use_container_width=True):
                            st.session_state.sel_meeting_id = r["id"]
                            st.session_state.is_editing_mtg = False
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

    # ----- 오른쪽: 뷰어/에디터 영역 -----
    with col_viewer:
        st.markdown("<div style='border-left: 1px solid #2f4775; padding-left: 30px; min-height: 600px;'>", unsafe_allow_html=True)
        
        if st.session_state.sel_meeting_id is None:
            st.info("👈 왼쪽 폴더에서 열람할 회의록을 선택하거나, '새 회의록 작성'을 눌러주세요.")
            
        else:
            # 1) 새 회의록 작성 모드
            if st.session_state.sel_meeting_id == "NEW":
                st.subheader("✨ 새 회의록 작성")
                with st.form("new_mtg_form"):
                    f_title = st.text_input("회의 제목")
                    c1, c2, c3 = st.columns(3)
                    with c1: f_folder = st.selectbox("분류(폴더)", ["전체 회의"] + TEAM_OPTIONS)
                    with c2: f_date = st.date_input("회의 일자")
                    with c3: f_author = st.text_input("작성자")
                    
                    f_content = st.text_area("회의 내용 (Markdown 지원: **굵게**, - 목록 등)", height=400)
                    
                    if st.form_submit_button("저장하기", type="primary"):
                        if not f_title: st.warning("제목을 입력하세요.")
                        else:
                            new_row = {
                                "id": str(uuid.uuid4()), "분류": f_folder, "회의일자": safe_date_str(f_date),
                                "제목": f_title, "작성자": f_author, "내용": f_content
                            }
                            meetings_df = pd.concat([meetings_df, pd.DataFrame([new_row])], ignore_index=True)
                            st.session_state.meetings_df = meetings_df
                            save_csv(meetings_df, MEETINGS_CSV)
                            st.session_state.sel_meeting_id = new_row["id"]
                            st.session_state.is_editing_mtg = False
                            st.rerun()
                            
            # 2) 기존 회의록 열람/수정 모드
            else:
                mtg_data = meetings_df[meetings_df["id"] == st.session_state.sel_meeting_id]
                if mtg_data.empty:
                    st.error("회의록을 찾을 수 없습니다.")
                else:
                    mtg = mtg_data.iloc[0]
                    
                    # --- 열람 모드 ---
                    if not st.session_state.is_editing_mtg:
                        c1, c2 = st.columns([8, 2])
                        with c1: st.markdown(f"## {mtg['제목']}")
                        with c2:
                            if can_edit() and st.button("✏️ 수정", use_container_width=True):
                                st.session_state.is_editing_mtg = True
                                st.rerun()
                                
                        st.caption(f"📁 {mtg['분류']} &nbsp;|&nbsp; 📅 {mtg['회의일자']} &nbsp;|&nbsp; 👤 {mtg['작성자']}")
                        st.markdown("---")
                        
                        # 내용 출력 (마크다운 렌더링)
                        st.markdown(mtg['내용'])
                        
                    # --- 수정 모드 ---
                    else:
                        st.subheader("✏️ 회의록 수정")
                        with st.form("edit_mtg_form"):
                            f_title = st.text_input("회의 제목", value=mtg['제목'])
                            c1, c2, c3 = st.columns(3)
                            with c1: f_folder = st.selectbox("분류(폴더)", ["전체 회의"] + TEAM_OPTIONS, index=(["전체 회의"]+TEAM_OPTIONS).index(mtg['분류']))
                            with c2: f_date = st.date_input("회의 일자", value=pd.to_datetime(mtg['회의일자']).date())
                            with c3: f_author = st.text_input("작성자", value=mtg['작성자'])
                            
                            f_content = st.text_area("회의 내용", value=mtg['내용'], height=400)
                            
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
                                    save_csv(meetings_df, MEETINGS_CSV)
                                    st.session_state.is_editing_mtg = False
                                    st.rerun()
                            with btn_c2:
                                if st.form_submit_button("취소"):
                                    st.session_state.is_editing_mtg = False
                                    st.rerun()
                                    
        st.markdown("</div>", unsafe_allow_html=True)
