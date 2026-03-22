import os
import uuid
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import gspread
import base64
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
from html import escape
import streamlit.components.v1 as components
from streamlit_calendar import calendar

st.set_page_config(page_title="Hallaon Workspace", layout="wide", initial_sidebar_state="expanded")

# 로고 파일 경로 상수
LOGO_IMAGE_PATH = "image_02c15f0a-577a-462d-8cd3-1ca275ece279.png"

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

WORKSHEET_TASKS = "Tasks"
WORKSHEET_AGENDA = "Agenda"
WORKSHEET_MEETINGS = "Meetings"
WORKSHEET_DECISIONS = "DECISIONS"
WORKSHEET_USERS = "Users"  # ★ 신규 추가된 유저 관리 시트

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

TEAM_OPTIONS = ["PM", "CD", "FS", "DM", "OPS"]
TASK_STATUS_OPTIONS = ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"]
AGENDA_STATUS_OPTIONS = ["시작 전", "진행 중", "완료", "보류"]

TEAM_COLORS = {
    "PM":  "#6C9CFF",   "CD":  "#FF7EB3",   "FS":  "#5EEAA0",
    "DM":  "#B18CFF",   "OPS": "#FFCB57",
}
STATUS_COLORS = {
    "완료":   "#5EEAA0",  "막힘":   "#FF6B6B",  "진행 중": "#FFCB57",
    "작업 중": "#FFB070", "대기":   "#B18CFF",  "시작 전": "#8899AA", "보류":   "#6B7B8D",
}

# =========================
# 🎨 MASTER CSS
# =========================
st.markdown("""
<style>
#MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --sf-ground: #0B0F14; --sf-base: #101621; --sf-raised: #151C2A; --sf-overlay: #1A2335; --sf-top: #1F2A40;
    --bd-subtle: rgba(140, 170, 220, 0.07); --bd-default: rgba(140, 170, 220, 0.12); --bd-strong: rgba(140, 170, 220, 0.20);
    --tx-primary: #E8EDF5; --tx-secondary: #9BAABB; --tx-tertiary: #6B7B8D; --tx-inverse: #0B0F14;
    --accent: #6C9CFF; --accent-soft: rgba(108, 156, 255, 0.12);
    --sh-sm: 0 2px 6px rgba(0,0,0,0.24); --sh-md: 0 4px 12px rgba(0,0,0,0.28); --sh-lg: 0 8px 28px rgba(0,0,0,0.36);
    --r-sm: 8px; --r-md: 12px; --r-lg: 16px; --r-xl: 20px; --r-full: 999px;
    --sp-3: 12px; --sp-4: 16px; --sp-5: 20px; --sp-6: 24px; --sp-8: 32px;
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --dur-fast: 120ms; --dur-normal: 200ms;
}

html, body, .stApp { font-family: 'Inter', sans-serif !important; background: var(--sf-ground) !important; color: var(--tx-primary) !important; font-weight: 450; line-height: 1.65; }
h1, h2, h3 { color: var(--tx-primary) !important; font-weight: 800 !important; letter-spacing: -0.025em; }
p, div.stMarkdown, label, span { color: var(--tx-primary) !important; }
small, [data-testid="stCaptionContainer"] * { color: var(--tx-secondary) !important; font-size: 12px !important; font-weight: 600; text-transform: uppercase; }

.login-logo-container { display: flex; justify-content: center; margin-bottom: var(--sp-6); }
.login-logo-img { width: 100px; height: 100px; border-radius: var(--r-xl); object-fit: cover; box-shadow: var(--sh-lg); border: 2px solid var(--bd-strong); }

section[data-testid="stSidebar"] { background: var(--sf-base) !important; border-right: 1px solid var(--bd-subtle) !important; padding: var(--sp-5) var(--sp-4) !important; }
section[data-testid="stSidebar"] * { color: var(--tx-primary) !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label { border-radius: var(--r-md) !important; padding: var(--sp-3) var(--sp-4) !important; transition: all var(--dur-fast) var(--ease-out); }
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover { background: var(--accent-soft) !important; color: var(--accent) !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label[data-selected="true"], section[data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div + label { background: var(--accent-soft) !important; box-shadow: inset 3px 0 0 var(--accent); color: var(--accent) !important; font-weight: 700; }

button[data-testid="stSidebarCollapsedControl"] { visibility: visible !important; background: var(--accent) !important; border-radius: 0 var(--r-lg) var(--r-lg) 0 !important; box-shadow: var(--sh-md), 0 0 16px rgba(108,156,255,0.3) !important; position: fixed !important; top: 12px !important; left: 0 !important; z-index:9999;}
button[data-testid="stSidebarCollapsedControl"] svg { visibility: visible !important; color: var(--tx-inverse) !important; fill: var(--tx-inverse) !important; }

div[data-testid="metric-container"] { background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important; border-radius: var(--r-xl) !important; padding: var(--sp-6) !important; transition: all var(--dur-normal) var(--ease-out); }
div[data-testid="metric-container"]:hover { box-shadow: var(--sh-md) !important; transform: translateY(-2px); }
div[data-testid="stMetricLabel"] { color: var(--tx-secondary) !important; font-size: 12px !important; font-weight: 700 !important; text-transform: uppercase; }
div[data-testid="stMetricValue"] { color: var(--tx-primary) !important; font-size: 32px !important; font-weight: 900 !important; }

div[data-testid="stDataFrame"] { background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important; border-radius: var(--r-lg) !important; overflow: hidden; }
div[data-testid="stDataFrame"] [role="columnheader"] { background: var(--sf-overlay) !important; color: var(--tx-secondary) !important; font-size: 11px !important; text-transform: uppercase; }
div[data-testid="stDataFrame"] canvas + div input { color: #FFFFFF !important; background: var(--sf-top) !important; border: 2px solid var(--accent) !important; border-radius: var(--r-xs) !important; }

div[data-testid="stExpander"] details { background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important; border-radius: var(--r-lg) !important; margin-bottom: 8px;}
div[data-testid="stExpander"] summary { background: var(--sf-overlay) !important; font-size: 14px !important; padding: var(--sp-4) var(--sp-5) !important; }

button[kind="primary"], button[data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, #6C9CFF 0%, #5580E0 100%) !important; color: var(--tx-inverse) !important; border-radius: var(--r-md) !important; box-shadow: var(--sh-sm), 0 0 12px rgba(108,156,255,0.15) !important; transition: all var(--dur-fast) var(--ease-out); font-weight:700 !important;}
button[kind="primary"]:hover { box-shadow: var(--sh-md), 0 0 20px rgba(108,156,255,0.3) !important; transform: translateY(-1px); }
button[kind="secondary"] { background: var(--sf-overlay) !important; border: 1px solid var(--bd-default) !important; border-radius: var(--r-md) !important; }

div[data-baseweb="input"] input,
div[data-baseweb="input"] textarea,
div[data-baseweb="base-input"] input,
input, textarea {
    background: var(--sf-base) !important;
    color: var(--tx-primary) !important;
    -webkit-text-fill-color: var(--tx-primary) !important; 
    border: 1.5px solid var(--bd-default) !important;
    border-radius: var(--r-sm) !important;
    padding: var(--sp-3) var(--sp-4) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    transition: all var(--dur-fast) var(--ease-out);
    caret-color: var(--accent) !important;
    min-height: 44px;
}
div[data-baseweb="input"] input:focus,
div[data-baseweb="input"] textarea:focus,
input:focus, textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
    outline: none !important;
    background: var(--sf-raised) !important;
}
input::placeholder, textarea::placeholder {
    color: var(--tx-tertiary) !important;
    -webkit-text-fill-color: var(--tx-tertiary) !important;
    font-weight: 400;
}
[data-testid="stForm"] { background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important; border-radius: var(--r-xl) !important; padding: var(--sp-6) !important; }
.role-badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 16px; border-radius: var(--r-full); font-size: 12px; font-weight: 700; border: 1px solid var(--bd-default); background: var(--sf-overlay); color: var(--accent) !important; }
</style>
""", unsafe_allow_html=True)

# =========================
# Utils
# =========================
def safe_date_str(v):
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return date.today().strftime("%Y-%m-%d")

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8899AA")
    return f"<span style='display:inline-flex;align-items:center;padding:4px 12px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.12);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.25);'>{escape(s)}</span>"

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# =========================
# CPM 및 간트 차트 
# =========================
def calculate_cpm(df):
    df = df.copy()
    df["is_critical"] = False
    if "WBS_코드" not in df.columns or "선행_업무" not in df.columns or df.empty: return df

    df["_start"] = pd.to_datetime(df["시작일"], errors="coerce")
    df["_end"] = pd.to_datetime(df["종료일"], errors="coerce")
    df = df.dropna(subset=["_start", "_end"])
    if df.empty: return df
    
    wbs_map = {str(row["WBS_코드"]).strip(): idx for idx, row in df.iterrows() if str(row["WBS_코드"]).strip()}
    df["ES"] = df["_start"]
    df["EF"] = df["_end"]
    
    for idx, row in df.iterrows():
        preds = str(row.get("선행_업무", "")).strip()
        if preds:
            pred_list = [p.strip() for p in preds.split(",") if p.strip()]
            max_ef = None
            for p in pred_list:
                if p in wbs_map:
                    pred_ef = df.at[wbs_map[p], "EF"]
                    if max_ef is None or pred_ef > max_ef: max_ef = pred_ef
            if max_ef is not None:
                df.at[idx, "ES"] = max(df.at[idx, "ES"], max_ef + timedelta(days=1))
    
    project_end = df["EF"].max()
    df["LF"] = project_end
    df["LS"] = project_end
    
    for idx in reversed(df.index.tolist()):
        wbs = str(df.at[idx, "WBS_코드"]).strip()
        for idx2, row2 in df.iterrows():
            preds = str(row2.get("선행_업무", "")).strip()
            if preds and wbs in [p.strip() for p in preds.split(",") if p.strip()]:
                succ_ls = df.at[idx2, "LS"] if "LS" in df.columns else project_end
                df.at[idx, "LF"] = min(df.at[idx, "LF"], succ_ls - timedelta(days=1))
        
        duration = (df.at[idx, "EF"] - df.at[idx, "ES"]).days
        df.at[idx, "LS"] = df.at[idx, "LF"] - timedelta(days=duration)
    
    df["_float"] = (df["LS"] - df["ES"]).dt.days
    df["is_critical"] = df["_float"] <= 0
    df.drop(columns=["_start", "_end", "ES", "EF", "LS", "LF", "_float"], inplace=True, errors='ignore')
    return df

def render_gantt(df):
    if df.empty: return "<div style='padding:32px;color:#9BAABB;font-size:14px;text-align:center;'>표시할 업무가 없습니다.</div>"
    
    g = calculate_cpm(df.copy())
    g["시작일_dt"] = pd.to_datetime(g["시작일"], errors="coerce")
    g["종료일_dt"] = pd.to_datetime(g["종료일"], errors="coerce")
    g = g.dropna(subset=["시작일_dt","종료일_dt"])
    if g.empty: return "<div style='padding:32px;color:#9BAABB;font-size:14px;text-align:center;'>날짜 데이터가 유효하지 않습니다.</div>"

    min_d = g["시작일_dt"].min().date()
    max_d = g["종료일_dt"].max().date()
    tl_start = min_d - timedelta(days=min_d.weekday())
    days_total = max((max_d - tl_start).days + 14, 35)
    days_total = ((days_total // 7) + 1) * 7
    weeks = days_total // 7
    tl_end = tl_start + timedelta(days=days_total)
    step = 1 if weeks <= 12 else 2 if weeks <= 24 else 4
    today = date.today()
    today_off = (today - tl_start).days
    today_pct = (today_off / days_total) * 100 if 0 <= today_off <= days_total else -100

    h = "<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');.gw{font-family:'Inter',sans-serif;background:#0B0F14;border:1px solid rgba(140,170,220,0.12);border-radius:20px;overflow:auto;}.gh{display:flex;justify-content:space-between;align-items:center;padding:16px 24px;background:#101621;border-bottom:1px solid rgba(140,170,220,0.07);gap:8px;}.chip-row{display:flex;flex-wrap:wrap;gap:6px;}.chip{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:8px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:10px;font-weight:700;}.dot{width:7px;height:7px;border-radius:50%;}.gt{width:100%;min-width:1200px;border-collapse:collapse;}.gt th,.gt td{border-right:1px solid rgba(140,170,220,0.05);border-bottom:1px solid rgba(140,170,220,0.05);color:#E8EDF5;padding:10px;}.gt th{background:#151C2A;font-size:10px;text-transform:uppercase;color:#6B7B8D;position:sticky;top:0;z-index:2;}.gt tr:hover{background:rgba(108,156,255,0.04);}.today-line{position:absolute;top:0;bottom:0;width:2px;background:rgba(108,156,255,0.5);z-index:1;}.today-line::before{content:'Today';position:absolute;top:-18px;left:-14px;font-size:8px;color:#6C9CFF;font-weight:700;}.barw{position:relative;height:44px;display:flex;align-items:center;}.bar{position:absolute;height:26px;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:10px;color:#0B0F14;text-overflow:ellipsis;transition:all 200ms;}.bar:hover{transform:scaleY(1.15);box-shadow:0 4px 12px rgba(0,0,0,0.35);}.bar.critical{background:linear-gradient(135deg,#FF6B6B 0%,#E04545 100%) !important;color:#fff;box-shadow:0 0 10px rgba(255,107,107,0.5);border:1px solid #FF9B9B;}</style>"
    h += "<div class='gw'><div class='gh'><div class='chip-row'>"
    for t, c in TEAM_COLORS.items(): h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += f"<span class='chip' style='border-color:rgba(255,107,107,0.3);color:#FF9B9B;'><span class='dot' style='background:#FF6B6B'></span>Critical</span></div><div style='color:#6B7B8D;font-size:11px;font-weight:800;text-transform:uppercase;'>PERT · CPM Gantt</div></div>"
    h += "<table class='gt'><thead><tr><th style='width:55px;'>WBS</th><th style='width:180px;'>업무</th><th style='width:70px;'>선행</th><th style='width:55px;'>TE</th><th style='width:90px;'>상태</th>"
    for i in range(weeks):
        ws = tl_start + timedelta(days=i*7)
        h += f"<th class='wkh'>{f'W{i+1} ({ws.month}/{ws.day})' if i % step == 0 else ''}</th>"
    h += "</tr></thead><tbody>"

    for _, r in g.iterrows():
        is_crit = r.get("is_critical", False)
        c = TEAM_COLORS.get(str(r["팀"]).split(",")[0].strip(), "#8899AA")
        s = r["시작일_dt"].date(); e = r["종료일_dt"].date()
        off = max((s - tl_start).days, 0)
        dur = max(((min(e, tl_end) - max(s, tl_start)).days + 1), 1)
        left = (off / days_total) * 100; width = (dur / days_total) * 100
        today_html = f"<div class='today-line' style='left:{today_pct}%'></div>" if 0 <= today_pct <= 100 else ""
        crit_class = " critical" if is_crit else ""

        h += "<tr>"
        h += f"<td style='color:#6C9CFF;font-weight:800;'>{escape(str(r.get('WBS_코드','')))}</td>"
        h += f"<td style='font-weight:600;'>{escape(str(r['업무명']))}</td>"
        h += f"<td style='color:#9BAABB;'>{escape(str(r.get('선행_업무','')))}</td>"
        h += f"<td>{escape(str(r.get('기대_시간(TE)','')))}</td>"
        h += f"<td>{status_badge(r['상태'])}</td>"
        h += f"<td colspan='{weeks}' class='tl'>{today_html}<div class='barw'><div class='bar{crit_class}' style='left:{left}%;width:{width}%;background:linear-gradient(135deg,{c} 0%,{c}cc 100%);'>{escape(str(r['업무명']))}</div></div></td></tr>"
    h += "</tbody></table></div>"
    return h

# =========================
# DB 정규화 
# =========================
def normalize_users_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["이름", "비밀번호", "권한"])
    req = ["이름", "비밀번호", "권한"]
    for c in req:
        if c not in d.columns: d[c] = ""
    return d

def normalize_tasks_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame()
    req = ["id", "업무명", "담당자", "팀", "상태", "시작일", "종료일", "sent", "WBS_코드", "선행_업무", "낙관적_시간(O)", "가능성_높은_시간(M)", "비관적_시간(P)", "기대_시간(TE)"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    d["시작일"] = d["시작일"].apply(safe_date_str); d["종료일"] = d["종료일"].apply(safe_date_str)
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

def normalize_decisions_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id", "안건명", "평가기준", "대안", "최종점수", "작성일"])
    req = ["id", "안건명", "평가기준", "대안", "최종점수", "작성일"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    return d[req].fillna("")

def init_data():
    st.session_state.tasks_df = normalize_tasks_df(load_gsheet_to_df(WORKSHEET_TASKS))
    st.session_state.agenda_df = normalize_agenda_df(load_gsheet_to_df(WORKSHEET_AGENDA))
    st.session_state.meetings_df = normalize_meetings_df(load_gsheet_to_df(WORKSHEET_MEETINGS))
    st.session_state.decisions_df = normalize_decisions_df(load_gsheet_to_df(WORKSHEET_DECISIONS))

# =========================
# 🔐 AUTH GATE (이름/PW 기반 로그인)
# =========================
def auth_gate():
    if st.session_state.get("role") is not None:
        return

    # 🚨 로고 절대 경로 추적 강화
    logo_b64 = ""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, LOGO_IMAGE_PATH)
        
        if os.path.exists(logo_path):
            logo_b64 = get_base64_of_bin_file(logo_path)
        else:
            print(f"로고 파일을 찾을 수 없습니다: {logo_path}")
    except Exception as e:
        print(f"로고 인코딩 에러: {e}")

    logo_html = f'<div class="login-logo-container"><img src="data:image/jpeg;base64,{logo_b64}" class="login-logo-img" alt="Logo"/></div>' if logo_b64 else '<div style="font-size:48px; text-align:center; margin-bottom:12px;">🏛️</div>'

    # 🚨 완벽한 강제 중앙 정렬 레이아웃 적용
    st.markdown(f"""
    <div style="display:flex; flex-direction:column; justify-content:center; align-items:center; min-height:70vh; text-align:center;">
        <div style="display:flex; flex-direction:column; align-items:center; max-width:360px; width:100%;">
            {logo_html}
            <h1 style="font-size:28px; font-weight:900; margin:0 0 4px 0; letter-spacing:-0.03em; padding:0; text-align:center;">Hallaon</h1>
            <p style="color:#6B7B8D; font-size:13px; margin:0 0 36px 0; font-weight:600; letter-spacing:0.04em; text-transform:uppercase; text-align:center;">WORKSPACE</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<div style='font-size:13px; font-weight:700; color:#9BAABB; margin-bottom:12px; text-align:center;'>팀 계정으로 로그인하세요</div>", unsafe_allow_html=True)
            user_id = st.text_input("이름 (ID)", placeholder="자신의 이름을 입력하세요")
            user_pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
            submit = st.form_submit_button("로그인", type="primary", use_container_width=True)
            
            if submit:
                if not user_id or not user_pw:
                    st.warning("이름과 비밀번호를 모두 입력해주세요.")
                else:
                    with st.spinner("정보를 확인하는 중..."):
                        users_df = st.session_state.users_df
                        user_row = users_df[users_df["이름"] == user_id]
                        
                        if user_row.empty:
                            st.error("등록되지 않은 이름입니다. (Users 시트를 확인하세요)")
                        else:
                            real_pw = str(user_row.iloc[0]["비밀번호"])
                            real_role = str(user_row.iloc[0]["권한"])
                            
                            if user_pw == real_pw:
                                st.session_state.role = real_role
                                st.session_state.username = user_id
                                st.toast(f"환영합니다, {user_id}님!", icon="👋")
                                st.rerun()
                            else:
                                st.error("비밀번호가 일치하지 않습니다.")
    st.stop()

def can_edit():
    return st.session_state.get("role") == "edit"

# =========================
# MAIN APP 실행 구조 (최적화)
# =========================

# 1. 로그인 폼을 띄우기 위해 가벼운 Users 시트만 먼저 로드!
if "users_df" not in st.session_state:
    st.session_state.users_df = normalize_users_df(load_gsheet_to_df(WORKSHEET_USERS))

# 2. 로그인 게이트 실행 (여기서 통과하지 못하면 밑으로 안 넘어감)
auth_gate()

# 3. 로그인 성공 시 무거운 업무/회의록 데이터 로드 (최초 1회만 스피너)
if "tasks_df" not in st.session_state:
    with st.spinner("🏛️ 한라온 데이터를 불러오고 있습니다..."):
        init_data()

tasks_df = st.session_state.tasks_df.copy()
agenda_df = st.session_state.agenda_df.copy()
meetings_df = st.session_state.meetings_df.copy()
decisions_df = st.session_state.decisions_df.copy()

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
        <span style="font-size:28px;">🏛️</span>
        <div>
            <div style="font-size:18px;font-weight:900;letter-spacing:-0.03em;">Hallaon</div>
            <div style="font-size:10px;color:#6B7B8D;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Workspace</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"<span class='role-badge'>👤 {st.session_state.username} ({'편집' if can_edit() else '조회'})</span>", unsafe_allow_html=True)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    
    if st.button("🔄 새로고침 / 로그아웃", use_container_width=True):
        with st.spinner("로그아웃 처리 중..."):
            init_data()
            st.session_state.role = None
            st.session_state.username = None
        st.rerun()
    
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.caption("WORKSPACE")
    
    menu = st.radio(
        "메뉴",
        ["🏠 홈", "📋 업무 및 WBS", "📊 간트 차트", "📅 캘린더", "📈 대시보드", "🗂️ 안건", "⚖️ 의사결정", "📄 문서", "🤖 작업 전송"],
        label_visibility="collapsed"
    )
    
    # === 🔐 비밀번호 변경 기능 추가 ===
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.caption("ACCOUNT SETTINGS")
    with st.expander("🔑 비밀번호 변경", expanded=False):
        with st.form("pw_change_form"):
            new_pw = st.text_input("새 비밀번호", type="password")
            new_pw_conf = st.text_input("비밀번호 확인", type="password")
            if st.form_submit_button("변경하기", type="primary", use_container_width=True):
                if not new_pw or not new_pw_conf:
                    st.warning("비밀번호를 입력해주세요.")
                elif new_pw != new_pw_conf:
                    st.error("두 비밀번호가 다릅니다.")
                else:
                    users_df = st.session_state.users_df
                    idx = users_df.index[users_df["이름"] == st.session_state.username].tolist()[0]
                    users_df.at[idx, "비밀번호"] = new_pw
                    st.session_state.users_df = users_df
                    save_df_to_gsheet(users_df, WORKSHEET_USERS)
                    st.success("✅ 비밀번호가 변경되었습니다.")

# =========================
# Tab: 홈
# =========================
if menu == "🏠 홈":
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(108,156,255,0.08) 0%, rgba(94,234,160,0.04) 50%, transparent 100%); 
                padding: 40px 32px; border-radius: 24px; border: 1px solid rgba(140,170,220,0.07); margin-bottom: 32px;">
        <h1 style="font-size:32px;font-weight:900;margin:0 0 10px 0;letter-spacing:-0.03em;">
            <span style="color:#6C9CFF;">Hallaon</span> Workspace
        </h1>
        <p style="color:#9BAABB;font-size:15px;line-height:1.7;margin:0;max-width:720px;">
            탐라영재관 자율회 한라온의 프로젝트 완수를 위한 <b style="color:#E8EDF5;">데이터 기반 의사결정 및 일정 관리 플랫폼</b>입니다.<br>
            체계적인 알고리즘과 시각화된 데이터로 팀의 목표를 달성하세요.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📖 필수 가이드")
    
    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown("""
        <div style="background:#151C2A;padding:24px;border-radius:16px;border:1px solid rgba(140,170,220,0.1);height:100%;">
            <div style="font-size:28px;margin-bottom:12px;">📋</div>
            <h4 style="color:#FF7EB3;margin:0 0 10px 0;font-size:15px;">WBS와 고유 코드</h4>
            <p style="color:#9BAABB;font-size:13px;line-height:1.7;margin:0;">
                <b style="color:#E8EDF5;">WBS(Work Breakdown Structure)</b>는 프로젝트를 하위 단위로 쪼개는 구조입니다. WBS 코드는 절대 중복 불가하며 예: <b style="color:#E8EDF5;">2.2.1</b>처럼 부여하세요.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div style="background:#151C2A;padding:24px;border-radius:16px;border:1px solid rgba(140,170,220,0.1);height:100%;">
            <div style="font-size:28px;margin-bottom:12px;">📊</div>
            <h4 style="color:#FFCB57;margin:0 0 10px 0;font-size:15px;">핵심 경로(CPM)와 PERT</h4>
            <p style="color:#9BAABB;font-size:13px;line-height:1.7;margin:0;">
                알고리즘이 <b style="color:#E8EDF5;">핵심 경로(Critical Path)</b>를 자동 계산합니다. 간트 차트의 <b style="color:#FF6B6B;">붉은 막대</b>가 지연되면 전체 일정이 밀립니다.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div style="background:#151C2A;padding:24px;border-radius:16px;border:1px solid rgba(140,170,220,0.1);height:100%;">
            <div style="font-size:28px;margin-bottom:12px;">⚖️</div>
            <h4 style="color:#5EEAA0;margin:0 0 10px 0;font-size:15px;">의사결정 알고리즘</h4>
            <p style="color:#9BAABB;font-size:13px;line-height:1.7;margin:0;">
                가중치 평가 모델로 직감을 배제합니다. 기준과 가중치를 설정하고 점수를 입력하면 <b style="color:#5EEAA0;">최적 1순위 대안</b>을 과학적으로 추천합니다.
            </p>
        </div>
        """, unsafe_allow_html=True)

# =========================
# Tab: 업무 및 WBS
# =========================
elif menu == "📋 업무 및 WBS":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">📋 업무 및 WBS</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">작업 분할 구조도(WBS)와 PERT 기반 일정 관리</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not can_edit(): st.info("조회 권한입니다.")

    with st.expander("➕ 새 업무 추가", expanded=False):
        with st.form("add_wbs_task_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1: 
                WBS_코드 = st.text_input("WBS 코드", placeholder="예: 1.1, 2.3.1")
                업무명 = st.text_input("업무명", placeholder="업무명을 입력하세요")
                담당자 = st.text_input("담당자", placeholder="담당자 이름")
                팀 = st.multiselect("팀", TEAM_OPTIONS)
            with c2:
                선행_업무 = st.text_input("선행 업무 WBS 코드", placeholder="없으면 비워두세요")
                상태 = st.selectbox("상태", TASK_STATUS_OPTIONS)
                st.markdown("**PERT 예상 소요 시간(일)**")
                p1, p2, p3 = st.columns(3)
                with p1: O_time = st.number_input("낙관적(O)", min_value=0, step=1)
                with p2: M_time = st.number_input("보통(M)", min_value=0, step=1)
                with p3: P_time = st.number_input("비관적(P)", min_value=0, step=1)
                
            add_btn = st.form_submit_button("➕ 업무 추가", type="primary", disabled=not can_edit())

        if add_btn and 업무명:
            existing_wbs = tasks_df["WBS_코드"].astype(str).str.strip().tolist()
            if WBS_코드.strip() and WBS_코드.strip() in existing_wbs:
                st.error(f"WBS 코드 '{WBS_코드}'가 이미 존재합니다. 고유한 코드를 입력하세요.")
            else:
                with st.spinner('WBS 데이터를 기록하고 있습니다...'):
                    TE = round((O_time + 4 * M_time + P_time) / 6, 1) if (O_time or M_time or P_time) else 0
                    start_d = date.today()
                    
                    if 선행_업무.strip():
                        pred_rows = tasks_df[tasks_df["WBS_코드"].astype(str).str.strip() == 선행_업무.strip()]
                        if not pred_rows.empty:
                            pred_end = pd.to_datetime(pred_rows.iloc[0]["종료일"], errors="coerce")
                            if pd.notna(pred_end):
                                start_d = max(start_d, pred_end.date() + timedelta(days=1))
                    
                    end_d = start_d + timedelta(days=max(int(TE), 1))
                    
                    new_row = {
                        "id": str(uuid.uuid4()), "업무명": 업무명, "담당자": 담당자 or "미정",
                        "팀": ", ".join(팀) or "미지정", "상태": 상태, 
                        "시작일": safe_date_str(start_d), "종료일": safe_date_str(end_d), 
                        "sent": "False", "WBS_코드": WBS_코드, "선행_업무": 선행_업무,
                        "낙관적_시간(O)": O_time, "가능성_높은_시간(M)": M_time, "비관적_시간(P)": P_time, "기대_시간(TE)": TE
                    }
                    tasks_df = pd.concat([st.session_state.tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state.tasks_df = tasks_df
                    save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
                
                st.toast(f"'{업무명}' 업무가 추가되었습니다!", icon="✅")
                st.rerun()

    todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)].copy()
    done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)].copy()
    blocked_df = tasks_df[tasks_df["상태"].str.contains("막힘", na=False)].copy()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("전체", len(tasks_df))
    m2.metric("진행 중", len(todo_df) - len(blocked_df))
    m3.metric("막힘", len(blocked_df))
    m4.metric("완료", len(done_df))

    disp_cols = ["WBS_코드", "선행_업무", "업무명", "담당자", "팀", "상태", "기대_시간(TE)", "시작일", "종료일"]

    with st.expander(f"⏳ 진행 중 ({len(todo_df)})", expanded=True):
        if todo_df.empty: st.caption("진행 중인 업무가 없습니다.")
        else: st.dataframe(todo_df[disp_cols], use_container_width=True, hide_index=True)

    with st.expander(f"✅ 완료 ({len(done_df)})", expanded=False):
        if done_df.empty: st.caption("완료된 업무가 없습니다.")
        else: st.dataframe(done_df[disp_cols], use_container_width=True, hide_index=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown("### ✏️ 업무 수정 / 삭제")
    
    e = tasks_df.copy()
    e.insert(0, "선택", False)
    e["시작일"] = pd.to_datetime(e["시작일"]).dt.date
    e["종료일"] = pd.to_datetime(e["종료일"]).dt.date

    edited = st.data_editor(
        e[["선택", "WBS_코드", "선행_업무", "업무명", "담당자", "팀", "상태", "시작일", "종료일", "기대_시간(TE)"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={
            "선택": st.column_config.CheckboxColumn("선택", width="small"),
            "상태": st.column_config.SelectboxColumn("상태", options=TASK_STATUS_OPTIONS),
            "WBS_코드": st.column_config.TextColumn("WBS", width="small"),
            "선행_업무": st.column_config.TextColumn("선행", width="small"),
            "기대_시간(TE)": st.column_config.NumberColumn("TE(일)", width="small"),
        }
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 수정사항 저장", type="primary", disabled=not can_edit(), use_container_width=True):
            wbs_list = edited["WBS_코드"].astype(str).str.strip().tolist()
            wbs_nonempty = [w for w in wbs_list if w and w != ""]
            if len(wbs_nonempty) != len(set(wbs_nonempty)):
                st.error("WBS 코드에 중복이 있습니다. 각 업무의 WBS 코드는 고유해야 합니다.")
            else:
                base = tasks_df.copy().reset_index(drop=True)
                edited["시작일"] = edited["시작일"].apply(safe_date_str)
                edited["종료일"] = edited["종료일"].apply(safe_date_str)
                update_cols = ["WBS_코드", "선행_업무", "업무명", "담당자", "팀", "상태", "시작일", "종료일", "기대_시간(TE)"]
                for col in update_cols:
                    if col in edited.columns:
                        base[col] = edited[col]
                st.session_state.tasks_df = base
                save_df_to_gsheet(base, WORKSHEET_TASKS)
                st.success("수정사항이 저장되었습니다.")
                st.rerun()
    with c2:
        if st.button("🗑️ 선택 삭제", disabled=not can_edit(), use_container_width=True):
            idx = edited.index[edited["선택"] == True].tolist()
            if not idx: st.warning("삭제할 업무를 선택하세요.")
            else:
                keep = tasks_df.drop(index=idx).reset_index(drop=True)
                st.session_state.tasks_df = keep
                save_df_to_gsheet(keep, WORKSHEET_TASKS)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()

# =========================
# Tab: 간트 차트 (CPM)
# =========================
elif menu == "📊 간트 차트":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">📊 간트 차트 — CPM</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">선행 업무 관계를 파악하고 핵심 경로를 붉은색으로 강조합니다. 오늘 날짜는 파란 선으로 표시됩니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    with fc1:
        hide_done = st.toggle("완료 업무 숨기기", value=True)
    with fc2:
        team_filter_gantt = st.selectbox("팀 필터", ["전체"] + TEAM_OPTIONS, key="gantt_team_filter")
    
    gdf = tasks_df.copy()
    if hide_done:
        gdf = gdf[~gdf["상태"].str.contains("완료", na=False)].copy()
    if team_filter_gantt != "전체":
        gdf = gdf[gdf["팀"].str.contains(team_filter_gantt, na=False)].copy()

    gdf["_sort"] = gdf["WBS_코드"].astype(str).str.strip()
    gdf = gdf.sort_values("_sort").drop(columns=["_sort"])

    components.html(render_gantt(gdf), height=max(600, len(gdf)*56 + 200), scrolling=True)

# =========================
# Tab: 캘린더
# =========================
elif menu == "📅 캘린더":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">📅 종합 캘린더</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">업무, 안건, 회의를 하나의 달력에서 확인하세요</p>
    </div>
    """, unsafe_allow_html=True)

    calendar_events = []
    
    for _, r in tasks_df.iterrows():
        if r["시작일"] and r["종료일"]:
            color = TEAM_COLORS.get(str(r["팀"]).split(",")[0].strip(), "#8899AA")
            end_date = (pd.to_datetime(r["종료일"]) + timedelta(days=1)).strftime("%Y-%m-%d")
            calendar_events.append({
                "title": f"📋 {r['업무명']} ({r['담당자']})", "start": r["시작일"], "end": end_date,
                "backgroundColor": f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)}, 0.15)",
                "borderColor": color, "textColor": color
            })
            
    for _, r in meetings_df.iterrows():
        if r["회의일자"]:
            calendar_events.append({
                "title": f"📄 {r['제목']}", "start": r["회의일자"],
                "backgroundColor": "rgba(94, 234, 160, 0.15)", "borderColor": "#5EEAA0", "textColor": "#5EEAA0", "allDay": True
            })

    for _, r in agenda_df.iterrows():
        if r["입안일"]:
            calendar_events.append({
                "title": f"🗂️ {r['안건명']}", "start": r["입안일"],
                "backgroundColor": "rgba(255, 126, 179, 0.15)", "borderColor": "#FF7EB3", "textColor": "#FF7EB3", "allDay": True
            })

    calendar_options = {
        "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,listWeek"},
        "initialView": "dayGridMonth", "themeSystem": "standard", "eventDisplay": "block",
        "dayMaxEvents": 3,
    }
    
    custom_css = """
        .fc { font-family: 'Inter', system-ui, sans-serif; width: 100% !important; max-width: 100% !important; }
        .fc-view-harness { max-width: 100% !important; overflow-x: hidden !important; }
        .fc-scrollgrid { width: 100% !important; }
        .fc-theme-standard td, .fc-theme-standard th { border-color: rgba(140,170,220,0.08) !important; }
        .fc-toolbar-title { font-weight: 900 !important; color: #E8EDF5 !important; font-size: 18px !important; }
        .fc-button { background-color: #1A2335 !important; border-color: rgba(140,170,220,0.15) !important; color: #9BAABB !important; box-shadow: none !important; font-weight: 600 !important; border-radius: 8px !important; }
        .fc-button:hover { background-color: #26334D !important; color: #E8EDF5 !important; }
        .fc-button-active { background-color: #6C9CFF !important; color: #0B0F14 !important; border-color: #6C9CFF !important; font-weight: 700; }
        .fc-day-today { background-color: rgba(108,156,255,0.06) !important; }
        .fc-event { border-radius: 5px; padding: 2px 5px; font-size: 11px; font-weight: 600; cursor: pointer; border-width: 1px !important; }
        .fc-daygrid-day-number { color: #9BAABB !important; font-weight: 600; font-size: 13px; }
        .fc-col-header-cell-cushion { color: #6B7B8D !important; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
    """
    
    st.markdown("""
    <div style='background: #101621; padding: 16px; border-radius: 20px; 
                border: 1px solid rgba(140,170,220,0.1); box-shadow: 0 4px 12px rgba(0,0,0,0.28);
                box-sizing: border-box; width: 100%; overflow: hidden;'>
    """, unsafe_allow_html=True)
    calendar(events=calendar_events, options=calendar_options, custom_css=custom_css, key="hallaon_calendar")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Tab: 대시보드
# =========================
elif menu == "📈 대시보드":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">📈 종합 대시보드</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">프로젝트 현황을 한눈에 파악하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    if tasks_df.empty:
        st.info("업무 데이터가 없습니다.")
    else:
        unique_df = tasks_df.drop_duplicates(subset=['업무명'])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("전체 태스크", len(unique_df))
        m2.metric("진행 중", len(unique_df[unique_df['상태'].str.contains('진행|작업', na=False)]))
        m3.metric("막힘", len(unique_df[unique_df['상태'].str.contains('막힘', na=False)]))
        m4.metric("완료", len(unique_df[unique_df['상태'].str.contains('완료', na=False)]))

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("##### 상태별 분포")
            s = unique_df["상태"].value_counts().reset_index()
            s.columns = ["상태","개수"]
            fig1 = px.pie(s, names="상태", values="개수", hole=0.6, color="상태", color_discrete_map=STATUS_COLORS)
            fig1.update_layout(template="plotly_dark", height=380, showlegend=True, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=40, l=20, r=20))
            st.plotly_chart(fig1, use_container_width=True)

        with chart_col2:
            st.markdown("##### 담당자별 태스크")
            a = unique_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#6C9CFF"])
            fig2.update_layout(template="plotly_dark", height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=40, l=40, r=20), bargap=0.35)
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# Tab: 안건
# =========================
elif menu == "🗂️ 안건":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">🗂️ 안건 관리</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">팀 안건을 등록하고 상태를 추적하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not can_edit(): st.info("조회 권한입니다.")

    with st.expander("➕ 새 안건 추가", expanded=False):
        with st.form("add_agenda_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                안건명 = st.text_input("안건명", placeholder="안건명을 입력하세요")
                팀 = st.multiselect("팀", TEAM_OPTIONS, default=[])
            with c2:
                입안자 = st.text_input("입안자", placeholder="입안자 이름")
                입안일 = st.date_input("입안일", value=date.today())
            상태 = st.selectbox("상태", AGENDA_STATUS_OPTIONS, index=0)
            add_btn = st.form_submit_button("➕ 안건 추가", type="primary", disabled=not can_edit())

    if add_btn and 안건명.strip():
        new_row = {
            "id": str(uuid.uuid4()), "안건명": 안건명.strip(), "입안자": 입안자.strip() or "미정",
            "팀": ", ".join(팀) or "미지정", "상태": 상태, "입안일": safe_date_str(입안일), "sent": "False"
        }
        agenda_df = pd.concat([agenda_df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.agenda_df = agenda_df
        save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
        st.success("안건이 추가되었습니다.")
        st.rerun()

    ag_m1, ag_m2, ag_m3, ag_m4 = st.columns(4)
    ag_m1.metric("전체 안건", len(agenda_df))
    ag_m2.metric("진행 중", len(agenda_df[agenda_df["상태"] == "진행 중"]))
    ag_m3.metric("보류", len(agenda_df[agenda_df["상태"] == "보류"]))
    ag_m4.metric("완료", len(agenda_df[agenda_df["상태"] == "완료"]))

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: search_q = st.text_input("검색", placeholder="안건명으로 검색...", label_visibility="collapsed")
    with c2: team_f = st.selectbox("팀 필터", ["전체"] + TEAM_OPTIONS)
    with c3: status_f = st.selectbox("상태 필터", ["전체"] + AGENDA_STATUS_OPTIONS)

    f = agenda_df.copy()
    if search_q: f = f[f["안건명"].str.contains(search_q, case=False, na=False)]
    if team_f != "전체": f = f[f["팀"].str.contains(team_f, na=False)]
    if status_f != "전체": f = f[f["상태"] == status_f]
    f = f.sort_values("입안일", ascending=False)
    st.dataframe(f[["안건명","입안자","팀","상태","입안일"]], use_container_width=True, hide_index=True)

    st.markdown("### ✏️ 안건 수정 / 삭제")
    e_a = agenda_df.copy()
    e_a.insert(0, "선택", False)
    e_a["입안일"] = pd.to_datetime(e_a["입안일"]).dt.date

    edited_a = st.data_editor(
        e_a[["선택","안건명","입안자","팀","상태","입안일"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={
            "선택": st.column_config.CheckboxColumn("선택", width="small"),
            "상태": st.column_config.SelectboxColumn("상태", options=AGENDA_STATUS_OPTIONS)
        }
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 안건 수정사항 저장", type="primary", disabled=not can_edit(), use_container_width=True):
            base = agenda_df.copy().reset_index(drop=True)
            edited_a["입안일"] = edited_a["입안일"].apply(safe_date_str)
            base[["안건명","입안자","팀","상태","입안일"]] = edited_a[["안건명","입안자","팀","상태","입안일"]]
            st.session_state.agenda_df = base
            save_df_to_gsheet(base, WORKSHEET_AGENDA)
            st.success("안건 수정사항이 저장되었습니다.")
            st.rerun()
    with c2:
        if st.button("🗑️ 선택 안건 삭제", disabled=not can_edit(), use_container_width=True):
            idx = edited_a.index[edited_a["선택"] == True].tolist()
            if not idx: st.warning("삭제할 안건을 선택하세요.")
            else:
                keep = agenda_df.drop(index=idx).reset_index(drop=True)
                st.session_state.agenda_df = keep
                save_df_to_gsheet(keep, WORKSHEET_AGENDA)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()

# =========================
# Tab: 의사결정
# =========================
elif menu == "⚖️ 의사결정":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">⚖️ 의사결정 모델</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">가중치 평가(Weighted Scoring) 알고리즘으로 최적의 대안을 산출합니다</p>
    </div>
    """, unsafe_allow_html=True)

    if not can_edit(): st.info("조회 권한입니다.")

    if not decisions_df.empty:
        with st.expander(f"📋 저장된 의사결정 기록 ({len(decisions_df)}건)", expanded=False):
            st.dataframe(decisions_df[["안건명", "평가기준", "대안", "최종점수", "작성일"]], use_container_width=True, hide_index=True)

    if "criteria_count" not in st.session_state: st.session_state.criteria_count = 3
    if "alt_count" not in st.session_state: st.session_state.alt_count = 2

    active_agendas = agenda_df[agenda_df["상태"] != "완료"]["안건명"].tolist()

    with st.form("decision_model_form"):
        st.markdown("#### 1. 대상 안건 및 기준 설정")
        sel_agenda = st.selectbox("의사결정 대상 안건", active_agendas if active_agendas else ["등록된 안건 없음"])
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**평가 기준 및 가중치**")
            criteria = []; weights = []
            for i in range(st.session_state.criteria_count):
                col_c, col_w = st.columns([7, 3])
                with col_c: cr = st.text_input(f"기준 {i+1}", key=f"cr_{i}")
                with col_w: wt = st.number_input("가중치(%)", min_value=0, max_value=100, value=round(100 // st.session_state.criteria_count), key=f"wt_{i}")
                criteria.append(cr); weights.append(wt)
                
        with c2:
            st.markdown("**비교 대안**")
            alts = []
            for i in range(st.session_state.alt_count):
                al = st.text_input(f"대안 {i+1}", key=f"alt_{i}")
                alts.append(al)

        st.markdown("---")
        st.markdown("#### 2. 대안별 평가 (1~10점)")
        scores = {}
        valid_criteria = [c for c in criteria if c.strip()]
        valid_alts = [a for a in alts if a.strip()]
        
        for alt in valid_alts:
            scores[alt] = []
            st.markdown(f"**{alt}**")
            if valid_criteria:
                s_cols = st.columns(len(valid_criteria))
                for idx, cr in enumerate(valid_criteria):
                    with s_cols[idx]:
                        score = st.slider(f"{cr}", 1, 10, 5, key=f"score_{alt}_{idx}")
                        scores[alt].append(score)

        submitted = st.form_submit_button("🧠 알고리즘 실행", type="primary", disabled=not can_edit())

    if submitted:
        valid_weights = weights[:len(valid_criteria)]
        if sum(valid_weights) != 100:
            st.error(f"가중치의 합이 100%가 되어야 합니다. (현재: {sum(valid_weights)}%)")
        elif not valid_alts or not valid_criteria:
            st.warning("대안 2개 이상, 평가 기준 1개 이상 입력해주세요.")
        else:
            results = []
            for alt, score_list in scores.items():
                total_score = sum((score * weight / 100) for score, weight in zip(score_list, valid_weights))
                results.append({"대안": alt, "최종 점수": round(total_score, 2)})
            
            res_df = pd.DataFrame(results).sort_values("최종 점수", ascending=False)
            best_alt = res_df.iloc[0]["대안"]
            best_score = res_df.iloc[0]["최종 점수"]

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(94,234,160,0.1) 0%, rgba(108,156,255,0.05) 100%);
                        border:1px solid rgba(94,234,160,0.25);border-radius:16px;padding:24px 28px;margin:16px 0;">
                <div style="font-size:13px;font-weight:700;color:#5EEAA0;text-transform:uppercase;">추천 결과</div>
                <div style="font-size:24px;font-weight:900;color:#E8EDF5;">{escape(best_alt)} ({best_score}점)</div>
            </div>
            """, unsafe_allow_html=True)
            
            fig = px.bar(res_df, x="대안", y="최종 점수", text="최종 점수", color="대안", color_discrete_sequence=["#6C9CFF", "#FF7EB3", "#5EEAA0", "#FFCB57"])
            fig.update_layout(template="plotly_dark", height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# =========================
# Tab: 문서 (회의록)
# =========================
elif menu == "📄 문서":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:900;margin:0;">📄 문서</h2>
        <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">회의록 및 팀 문서를 작성하고 관리하세요</p>
    </div>
    """, unsafe_allow_html=True)

    if "sel_mtg_id" not in st.session_state: st.session_state.sel_mtg_id = None
    if "is_edit_mtg" not in st.session_state: st.session_state.is_edit_mtg = False

    top_c1, top_c2, top_c3 = st.columns([1, 1, 2])
    with top_c1:
        if st.button("➕ 새 문서 작성", use_container_width=True, disabled=not can_edit(), type="primary"):
            st.session_state.sel_mtg_id = "NEW"
            st.session_state.is_edit_mtg = True
            st.rerun()
    with top_c2:
        if st.button("📋 전체 목록 보기", use_container_width=True):
            st.session_state.sel_mtg_id = None
            st.rerun()

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    if st.session_state.sel_mtg_id is None:
        folders = ["전체 회의"] + TEAM_OPTIONS
        for folder in folders:
            f_df = meetings_df[meetings_df["분류"] == folder].sort_values("회의일자", ascending=False)
            if f_df.empty: continue
            
            with st.expander(f"📁 {folder} ({len(f_df)}건)", expanded=True):
                for _, r in f_df.iterrows():
                    col_title, col_date, col_author, col_action = st.columns([4, 1.5, 1.5, 1])
                    with col_title: st.markdown(f"**{r['제목']}**")
                    with col_date: st.caption(r['회의일자'])
                    with col_author: st.caption(f"👤 {r['작성자']}")
                    with col_action:
                        if st.button("열기", key=f"open_{r['id']}", use_container_width=True):
                            st.session_state.sel_mtg_id = r["id"]
                            st.session_state.is_edit_mtg = False
                            st.rerun()

    elif st.session_state.sel_mtg_id == "NEW":
        st.markdown("<div style='background:#151C2A;border:1px solid rgba(140,170,220,0.1);border-radius:20px;padding:28px;margin-bottom:16px;'><h3 style='margin:0;'>✨ 새 문서 작성</h3></div>", unsafe_allow_html=True)
        with st.form("new_mtg_form"):
            f_title = st.text_input("제목")
            c1, c2, c3 = st.columns(3)
            with c1: f_folder = st.selectbox("분류", ["전체 회의"] + TEAM_OPTIONS)
            with c2: f_date = st.date_input("날짜", value=date.today())
            with c3: f_author = st.text_input("작성자", value=st.session_state.username)
            f_content = st.text_area("내용 (Markdown 지원)", height=500)
            
            btn_c1, btn_c2 = st.columns([1, 3])
            with btn_c1: save_btn = st.form_submit_button("💾 저장", type="primary")
            with btn_c2: cancel_btn = st.form_submit_button("취소")
            
            if save_btn and f_title:
                new_row = {"id": str(uuid.uuid4()), "분류": f_folder, "회의일자": safe_date_str(f_date), "제목": f_title, "작성자": f_author, "내용": f_content}
                meetings_df = pd.concat([meetings_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.meetings_df = meetings_df
                save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                st.session_state.sel_mtg_id = new_row["id"]; st.session_state.is_edit_mtg = False; st.rerun()
            if cancel_btn:
                st.session_state.sel_mtg_id = None; st.rerun()

    else:
        m_data = meetings_df[meetings_df["id"] == st.session_state.sel_mtg_id]
        if m_data.empty: st.error("문서를 찾을 수 없습니다.")
        else:
            mtg = m_data.iloc[0]
            if not st.session_state.is_edit_mtg:
                st.markdown(f"""
                <div style="background:#151C2A;border:1px solid rgba(140,170,220,0.1);border-radius:20px;padding:32px;margin-bottom:8px;">
                    <div style="display:flex;gap:8px;margin-bottom:16px;">
                        <span style="padding:4px 12px;border-radius:999px;background:rgba(108,156,255,0.12);color:#6C9CFF;font-size:11px;font-weight:700;">📁 {escape(mtg['분류'])}</span>
                        <span style="padding:4px 12px;border-radius:999px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:11px;font-weight:600;">📅 {escape(mtg['회의일자'])}</span>
                        <span style="padding:4px 12px;border-radius:999px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:11px;font-weight:600;">👤 {escape(mtg['작성자'])}</span>
                    </div>
                    <h2 style="margin:0 0 20px 0;font-size:26px;">{escape(mtg['제목'])}</h2>
                    <div style="border-top:1px solid rgba(140,170,220,0.07);padding-top:20px;">{mtg['내용'].replace(chr(10), '<br>')}</div>
                </div>
                """, unsafe_allow_html=True)

                act_c1, act_c2, act_c3 = st.columns([1, 1, 4])
                with act_c1:
                    if can_edit() and st.button("✏️ 수정", use_container_width=True):
                        st.session_state.is_edit_mtg = True; st.rerun()
                with act_c2:
                    if can_edit() and st.button("🗑️ 삭제", use_container_width=True):
                        keep_m = meetings_df[meetings_df["id"] != mtg['id']].reset_index(drop=True)
                        st.session_state.meetings_df = keep_m
                        save_df_to_gsheet(keep_m, WORKSHEET_MEETINGS)
                        st.session_state.sel_mtg_id = None; st.rerun()
            else:
                with st.form("edit_mtg_form"):
                    f_title = st.text_input("제목", value=mtg['제목'])
                    c1, c2, c3 = st.columns(3)
                    with c1: f_folder = st.selectbox("분류", ["전체 회의"] + TEAM_OPTIONS, index=0)
                    with c2: f_date = st.date_input("날짜", value=pd.to_datetime(mtg['회의일자']).date())
                    with c3: f_author = st.text_input("작성자", value=mtg['작성자'])
                    f_content = st.text_area("내용", value=mtg['내용'], height=500)

                    btn_c1, btn_c2 = st.columns([1, 3])
                    with btn_c1:
                        if st.form_submit_button("💾 저장", type="primary"):
                            idx = meetings_df.index[meetings_df["id"] == mtg['id']].tolist()[0]
                            meetings_df.at[idx, '제목'] = f_title; meetings_df.at[idx, '분류'] = f_folder; meetings_df.at[idx, '회의일자'] = safe_date_str(f_date); meetings_df.at[idx, '작성자'] = f_author; meetings_df.at[idx, '내용'] = f_content
                            st.session_state.meetings_df = meetings_df
                            save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                            st.session_state.is_edit_mtg = False; st.rerun()
                    with btn_c2:
                        if st.form_submit_button("취소"): st.session_state.is_edit_mtg = False; st.rerun()

# =========================
# Tab: 작업 전송
# =========================
elif menu == "🤖 작업 전송":
    st.markdown("""
        <div style="margin-bottom:24px;">
            <h2 style="font-size:24px;font-weight:900;margin:0;">🤖 작업 전송</h2>
            <p style="color:#9BAABB;font-size:13px;margin:6px 0 0 0;">새로운 업무와 안건을 디스코드 팀 채널로 공유하세요</p>
        </div>
        """, unsafe_allow_html=True)

    if not can_edit(): 
        st.info("조회 권한에서는 디스코드 전송이 불가합니다. '권한 전환'으로 로그인하세요.")

    t_task, t_agenda = st.tabs(["📋 업무 전송", "🗂️ 안건 전송"])

    with t_task:
        u_tasks = tasks_df[tasks_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u_tasks.empty: 
            st.info("현재 미전송 상태인 신규 업무가 없습니다.")
        else:
            v_t = u_tasks.copy()
            v_t.insert(0, "전송", False)
            
            st.markdown("<div style='margin-bottom:12px;font-size:13px;font-weight:600;color:#E8EDF5;'>디스코드로 알릴 업무를 선택하세요:</div>", unsafe_allow_html=True)
            pick_t = st.data_editor(
                v_t[["전송", "WBS_코드", "업무명", "담당자", "팀", "상태", "시작일", "종료일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("선택", width="small")}
            )
            
            selected_task_indices = pick_t.index[pick_t["전송"] == True].tolist()
            if st.button("🚀 선택 업무 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_task_indices), use_container_width=True):
                sel_tasks = u_tasks.iloc[selected_task_indices].copy()
                fields = [{
                    "name": f"🔹 {r['업무명']} ({r['팀']})",
                    "value": f"👤 담당: {r['담당자']}\n🏷️ 상태: {r['상태']}\n📅 일정: {r['시작일']} → {r['종료일']}\n📝 WBS: {r.get('WBS_코드', '')}",
                    "inline": False
                } for _, r in sel_tasks.iterrows()]

                # 새로운 Accent Blue 색상 코드 (#6C9CFF -> 7118079)
                ok, msg = send_discord(fields, "🔔 신규 업무 알림", "Hallaon Roadmap Bot", color=7118079)
                if ok:
                    sent_ids = set(sel_tasks["id"].tolist())
                    tasks_df["sent"] = tasks_df["id"].apply(
                        lambda x: "True" if x in sent_ids or str(tasks_df.loc[tasks_df["id"]==x, "sent"].iloc[0]) == "True" else "False"
                    )
                    st.session_state.tasks_df = tasks_df
                    save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
                    st.success(msg)
                    st.rerun()
                else: 
                    st.error(msg)

    with t_agenda:
        u_agendas = agenda_df[agenda_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u_agendas.empty: 
            st.info("현재 미전송 상태인 신규 안건이 없습니다.")
        else:
            v_a = u_agendas.copy()
            v_a.insert(0, "전송", False)
            
            st.markdown("<div style='margin-bottom:12px;font-size:13px;font-weight:600;color:#E8EDF5;'>디스코드로 알릴 안건을 선택하세요:</div>", unsafe_allow_html=True)
            pick_a = st.data_editor(
                v_a[["전송", "안건명", "입안자", "팀", "상태", "입안일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("선택", width="small")}
            )
            
            selected_agenda_indices = pick_a.index[pick_a["전송"] == True].tolist()
            if st.button("📨 선택 안건 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_agenda_indices), use_container_width=True):
                sel_agendas = u_agendas.iloc[selected_agenda_indices].copy()
                fields = [{
                    "name": f"🗂️ {r['안건명']} ({r['팀']})",
                    "value": f"👤 입안: {r['입안자']}\n🏷️ 상태: {r['상태']}\n📅 입안일: {r['입안일']}",
                    "inline": False
                } for _, r in sel_agendas.iterrows()]

                # 새로운 Soft Rose 색상 코드 (#FF7EB3 -> 16744115)
                ok, msg = send_discord(fields, "📌 신규 안건 알림", "Hallaon Agenda Bot", color=16744115)
                if ok:
                    sent_ids = set(sel_agendas["id"].tolist())
                    agenda_df["sent"] = agenda_df["id"].apply(
                        lambda x: "True" if x in sent_ids or str(agenda_df.loc[agenda_df["id"]==x, "sent"].iloc[0]) == "True" else "False"
                    )
                    st.session_state.agenda_df = agenda_df
                    save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
                    st.success(msg)
                    st.rerun()
                else: 
                    st.error(msg)
