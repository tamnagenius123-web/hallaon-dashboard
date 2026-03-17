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
import streamlit.components.v1 as components
from streamlit_calendar import calendar  # 달력 컴포넌트 추가

st.set_page_config(page_title="Hallaon Workspace", layout="wide", initial_sidebar_state="expanded")

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
WORKSHEET_DECISIONS = "DECISIONS"  # 의사결정 DB 추가

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

# Material Design Dark 200-tone palette
TEAM_COLORS = {
    "PM":  "#82b1ff",   # Material Blue 200
    "CD":  "#ff8a9e",   # Material Red 200
    "FS":  "#69f0ae",   # Material Green A200
    "DM":  "#b39ddb",   # Material Deep Purple 200
    "OPS": "#ffe082",   # Material Amber 200
}
STATUS_COLORS = {
    "완료":   "#69f0ae",
    "막힘":   "#ef9a9a",
    "진행 중": "#ffe082",
    "작업 중": "#ffcc80",
    "대기":   "#b39ddb",
    "시작 전": "#90a4ae",
    "보류":   "#78909c",
}

# =========================
# 🎨 MASTER CSS — Material 3 Dark (6-layer elevation)
# =========================
st.markdown("""
<style>
/* 기본 UI 숨기기 */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

:root {
    --dp00: #0d1117; --dp01: #131a24; --dp02: #161e2a; 
    --dp04: #1c2636; --dp08: #222e42; --dp16: #2a3a52; --dp24: #324260;
    --border-subtle: rgba(148, 180, 226, 0.08); --border-default: rgba(148, 180, 226, 0.12); --border-strong: rgba(148, 180, 226, 0.18);
    --text-primary: rgba(240, 246, 255, 0.92); --text-secondary: rgba(176, 196, 226, 0.72); --text-tertiary: rgba(148, 170, 204, 0.48);
    --accent: #82b1ff; --accent-muted: rgba(130, 177, 255, 0.16); --accent-hover: rgba(130, 177, 255, 0.24);
    --success: #69f0ae; --warning: #ffe082; --danger: #ef9a9a;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.24), 0 1px 3px rgba(0,0,0,0.12);
    --shadow-md: 0 4px 8px rgba(0,0,0,0.28), 0 2px 4px rgba(0,0,0,0.16);
    --shadow-lg: 0 8px 24px rgba(0,0,0,0.36), 0 4px 8px rgba(0,0,0,0.20);
    --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px; --radius-full: 999px;
    --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-5: 20px; --sp-6: 24px;
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1); --duration-fast: 150ms; --duration-normal: 250ms;
}

.stApp { background: var(--dp00) !important; color: var(--text-primary) !important; font-weight: 450; letter-spacing: 0.01em; line-height: 1.7; }
h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; font-weight: 700 !important; letter-spacing: -0.02em; }
p, div.stMarkdown, div.stText, label { color: var(--text-primary) !important; }
small, [data-testid="stCaptionContainer"] * { color: var(--text-secondary) !important; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(19,26,36,0.92) 0%, rgba(13,17,23,0.96) 100%) !important;
    backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
    border-right: 1px solid var(--border-subtle) !important; padding: var(--sp-4) var(--sp-4) !important;
}
section[data-testid="stSidebar"] * { color: var(--text-primary) !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label {
    background: var(--dp02) !important; border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important; padding: var(--sp-3) var(--sp-4) !important;
    margin-bottom: var(--sp-2) !important; transition: all var(--duration-fast) var(--ease-out);
    font-weight: 550; font-size: 14px;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
    background: var(--accent-muted) !important; border-color: var(--accent) !important; transform: translateX(3px);
}
section[data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div + label,
section[data-testid="stSidebar"] [data-baseweb="radio"] label[data-selected="true"] {
    background: var(--accent-muted) !important; border-color: var(--accent) !important; box-shadow: inset 3px 0 0 var(--accent);
}

div[data-testid="metric-container"] {
    background: linear-gradient(145deg, var(--dp04) 0%, var(--dp02) 100%) !important;
    border: 1px solid var(--border-default) !important; border-radius: var(--radius-lg) !important;
    padding: var(--sp-5) var(--sp-6) !important; box-shadow: var(--shadow-md) !important; transition: all var(--duration-normal) var(--ease-out);
}
div[data-testid="metric-container"]:hover { box-shadow: var(--shadow-lg), 0 0 0 1px var(--accent-muted) !important; border-color: rgba(130,177,255,0.2) !important; transform: translateY(-2px); }
div[data-testid="stMetricLabel"] { color: var(--text-secondary) !important; font-size: 13px !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.06em; }
div[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-size: 28px !important; font-weight: 800 !important; }

div[data-testid="stDataFrame"], div[data-testid="stDataFrame"] [role="grid"] { background: var(--dp02) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-md) !important; box-shadow: var(--shadow-sm) !important; overflow: hidden; }
div[data-testid="stDataFrame"] [role="columnheader"] { background: var(--dp04) !important; color: var(--text-secondary) !important; font-weight: 650 !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border-default) !important; }
div[data-testid="stDataFrame"] [role="gridcell"] { border-bottom: 1px solid var(--border-subtle) !important; font-weight: 450; }

div[data-testid="stExpander"] details { background: var(--dp02) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-lg) !important; box-shadow: var(--shadow-sm) !important; overflow: hidden; transition: box-shadow var(--duration-normal) var(--ease-out); }
div[data-testid="stExpander"] details:hover { box-shadow: var(--shadow-md) !important; }
div[data-testid="stExpander"] details[open] { box-shadow: var(--shadow-md) !important; border-color: var(--border-strong) !important; }
div[data-testid="stExpander"] summary { background: var(--dp04) !important; color: var(--text-primary) !important; font-weight: 650 !important; padding: var(--sp-4) var(--sp-5) !important; border-radius: var(--radius-lg) var(--radius-lg) 0 0 !important; transition: background var(--duration-fast) var(--ease-out); }
div[data-testid="stExpander"] summary:hover { background: var(--dp08) !important; }
div[data-testid="stExpanderDetails"] { background: var(--dp02) !important; color: var(--text-primary) !important; padding: var(--sp-4) var(--sp-5) !important; }

button[kind="primary"], button[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #82b1ff 0%, #5c8de6 50%, #4a7bd4 100%) !important; color: #0d1117 !important; font-weight: 700 !important;
    border: none !important; border-radius: var(--radius-md) !important; padding: var(--sp-3) var(--sp-6) !important;
    box-shadow: var(--shadow-sm), 0 0 16px rgba(130,177,255,0.15) !important; transition: all var(--duration-fast) var(--ease-out); letter-spacing: 0.01em;
}
button[kind="primary"]:hover, button[data-testid="stFormSubmitButton"] > button:hover { box-shadow: var(--shadow-md), 0 0 24px rgba(130,177,255,0.25) !important; transform: translateY(-1px); }
button[kind="primary"]:active, button[data-testid="stFormSubmitButton"] > button:active { transform: translateY(0px); box-shadow: var(--shadow-sm) !important; }

button[kind="secondary"], button:not([kind="primary"]):not([data-testid]) { background: var(--dp04) !important; color: var(--text-primary) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-md) !important; font-weight: 550 !important; transition: all var(--duration-fast) var(--ease-out); }
button[kind="secondary"]:hover { background: var(--dp08) !important; border-color: var(--border-strong) !important; box-shadow: var(--shadow-sm) !important; }

input, textarea { background: var(--dp01) !important; color: var(--text-primary) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-sm) !important; padding: var(--sp-3) var(--sp-4) !important; font-weight: 450 !important; transition: all var(--duration-fast) var(--ease-out); }
input:focus, textarea:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-muted) !important; outline: none !important; background: var(--dp02) !important; }
div[data-baseweb="select"] > div { background: var(--dp01) !important; color: var(--text-primary) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-sm) !important; transition: all var(--duration-fast) var(--ease-out); }
div[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-muted) !important; }

div[data-testid="stTabs"] button { color: var(--text-tertiary) !important; font-weight: 600 !important; font-size: 14px !important; padding: var(--sp-3) var(--sp-5) !important; border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important; transition: all var(--duration-fast) var(--ease-out); }
div[data-testid="stTabs"] button:hover { color: var(--text-primary) !important; background: var(--accent-muted) !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--accent) !important; font-weight: 700 !important; background: transparent !important; }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--accent) !important; height: 3px !important; border-radius: 3px 3px 0 0 !important; }

[data-testid="stMultiSelect"] [data-baseweb="tag"] { background: var(--accent-muted) !important; border: 1px solid rgba(130,177,255,0.3) !important; border-radius: var(--radius-sm) !important; min-height: 28px !important; padding: 2px 10px !important; }
[data-testid="stMultiSelect"] [data-baseweb="tag"] span { color: var(--accent) !important; font-weight: 650 !important; overflow: visible !important; }

[data-testid="stForm"] { background: var(--dp02) !important; border: 1px solid var(--border-default) !important; border-radius: var(--radius-lg) !important; padding: var(--sp-6) !important; box-shadow: var(--shadow-sm) !important; }

.role-badge { display: inline-block; padding: 6px 14px; border-radius: var(--radius-full); font-size: 12px; font-weight: 700; border: 1px solid var(--border-default); background: var(--dp04); color: var(--accent); letter-spacing: 0.04em; }
.folder-btn button { background: transparent !important; border: none !important; text-align: left !important; justify-content: flex-start !important; padding: var(--sp-2) var(--sp-3) !important; font-size: 13px !important; border-radius: var(--radius-sm) !important; transition: all var(--duration-fast) var(--ease-out); }
.folder-btn button:hover { background: var(--accent-muted) !important; }
.folder-btn button span { color: var(--text-primary) !important; }
.folder-btn button:hover span { color: var(--accent) !important; }

hr, .stMarkdown hr { border: none !important; border-top: 1px solid var(--border-subtle) !important; margin: var(--sp-6) 0 !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: var(--radius-full); }
::-webkit-scrollbar-thumb:hover { background: var(--text-tertiary); }
</style>
""", unsafe_allow_html=True)

# =========================
# Utils
# =========================
def safe_date_str(v):
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception: return date.today().strftime("%Y-%m-%d")

def team_badge(team):
    t = str(team).split(",")[0].strip() if str(team).strip() else "미지정"
    c = TEAM_COLORS.get(t, "#90a4ae")
    return f"<span style='display:inline-block;padding:3px 10px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.16);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.3);'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#90a4ae")
    return f"<span style='display:inline-block;padding:3px 10px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.16);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.3);'>{escape(s)}</span>"

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
# CPM 및 간트 차트 (PERT 계산 적용)
# =========================
def calculate_cpm(df):
    df = df.copy()
    df["is_critical"] = False
    if "WBS_코드" not in df.columns or "선행_업무" not in df.columns or df.empty:
        return df

    end_dates = pd.to_datetime(df["종료일"], errors="coerce")
    if end_dates.isna().all(): return df
    
    project_end_date = end_dates.max()
    critical_wbs = set()

    for _, row in df.iterrows():
        if pd.to_datetime(row["종료일"]) == project_end_date:
            critical_wbs.add(str(row["WBS_코드"]).strip())
        predecessors = str(row["선행_업무"]).split(",")
        for p in predecessors:
            if p.strip(): critical_wbs.add(p.strip())

    df["is_critical"] = df["WBS_코드"].astype(str).str.strip().apply(lambda x: x in critical_wbs if x else False)
    return df

def render_gantt(df):
    if df.empty:
        return "<div style='padding:24px;color:rgba(176,196,226,0.72);font-size:14px;'>표시할 업무가 없습니다.</div>"
    
    g = calculate_cpm(df.copy())
    g["시작일_dt"] = pd.to_datetime(g["시작일"], errors="coerce")
    g["종료일_dt"] = pd.to_datetime(g["종료일"], errors="coerce")
    g = g.dropna(subset=["시작일_dt","종료일_dt"])
    if g.empty:
        return "<div style='padding:24px;color:rgba(176,196,226,0.72);font-size:14px;'>날짜 데이터가 유효하지 않습니다.</div>"

    min_d = g["시작일_dt"].min().date()
    max_d = g["종료일_dt"].max().date()
    tl_start = min_d - timedelta(days=min_d.weekday())
    days_total = max((max_d - tl_start).days + 14, 35)
    days_total = ((days_total // 7) + 1) * 7
    weeks = days_total // 7
    tl_end = tl_start + timedelta(days=days_total)
    step = 1 if weeks <= 12 else 2 if weeks <= 24 else 4

    h = "<style>"
    h += """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    .gw{font-family:'Inter',system-ui,-apple-system,sans-serif;background:#0d1117;border:1px solid rgba(148,180,226,0.12);border-radius:16px;overflow:auto;box-shadow:0 8px 24px rgba(0,0,0,0.36),0 4px 8px rgba(0,0,0,0.20);}
    .gh{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;background:linear-gradient(135deg,#131a24 0%,#161e2a 100%);border-bottom:1px solid rgba(148,180,226,0.08);}
    .chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;background:rgba(148,180,226,0.06);border:1px solid rgba(148,180,226,0.1);color:rgba(240,246,255,0.85);font-size:11px;font-weight:600;margin-right:6px;letter-spacing:0.03em;}
    .dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
    .gt{width:100%;min-width:1380px;border-collapse:collapse;table-layout:fixed;}
    .gt th,.gt td{border-right:1px solid rgba(148,180,226,0.06);border-bottom:1px solid rgba(148,180,226,0.06);color:rgba(240,246,255,0.9);padding:10px 10px;white-space:nowrap;}
    .gt th{background:#131a24;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:rgba(176,196,226,0.6);}
    .wkh{min-width:92px;text-align:center;font-size:10px;color:rgba(176,196,226,0.5);font-weight:600;}
    .tl{padding:0 !important;position:relative;background:transparent;}
    .bg{position:absolute;inset:0;display:flex;pointer-events:none;}
    .bgc{flex:1;border-right:1px solid rgba(148,180,226,0.04);}
    .barw{position:relative;height:48px;display:flex;align-items:center;}
    .bar{position:absolute;height:28px;border-radius:8px;display:flex;align-items:center;padding:0 10px;font-size:11px;font-weight:700;color:#0d1117;overflow:hidden;text-overflow:ellipsis;box-shadow:0 2px 8px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.15);transition:all 200ms;}
    .bar.critical { background: linear-gradient(135deg, #ff5252 0%, #d50000 100%) !important; color: #fff; box-shadow: 0 0 12px rgba(255,82,82,0.6), inset 0 1px 0 rgba(255,255,255,0.3); border: 1px solid #ff8a80; }
    """
    h += "</style>"

    h += "<div class='gw'><div class='gh'><div>"
    for t, c in TEAM_COLORS.items():
        h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += "<span class='chip' style='margin-left:12px; border-color:#ff5252; color:#ff8a80;'><span class='dot' style='background:#ff5252'></span>Critical Path</span>"
    h += "</div><div style='color:rgba(176,196,226,0.6);font-size:12px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;'>PERT / CPM Gantt</div></div>"
    
    h += "<table class='gt'><thead><tr>"
    h += "<th style='width:60px;'>WBS</th><th style='width:200px;'>TASK</th><th style='width:80px;'>PRED.</th><th style='width:70px;'>TE(일)</th><th style='width:100px;'>상태</th>"
    for i in range(weeks):
        ws = tl_start + timedelta(days=i*7)
        full = f"Week {i+1} ({ws.month}/{ws.day}~)"
        txt = full if i % step == 0 else "·"
        h += f"<th class='wkh' title='{full}'>{txt}</th>"
    h += "</tr></thead><tbody>"

    for _, r in g.iterrows():
        wbs = str(r.get("WBS_코드", "")).strip()
        pred = str(r.get("선행_업무", "")).strip()
        te = str(r.get("기대_시간(TE)", "")).strip()
        status = str(r["상태"]).strip()
        task = str(r["업무명"]).strip()
        team = str(r["팀"]).split(",")[0].strip() if str(r["팀"]).strip() else "미지정"
        c = TEAM_COLORS.get(team, "#90a4ae")
        is_crit = r.get("is_critical", False)

        s = r["시작일_dt"].date()
        e = r["종료일_dt"].date()
        cs = max(s, tl_start)
        ce = min(e + timedelta(days=1), tl_end)
        off = (cs - tl_start).days
        dur = max((ce - cs).days, 1)
        
        left = (off / days_total) * 100
        width = (dur / days_total) * 100
        label = f"{escape(task)}" if not is_crit else f"🔥 {escape(task)}"
        bg = "".join(["<div class='bgc'></div>" for _ in range(weeks)])
        crit_class = " critical" if is_crit else ""

        h += "<tr>"
        h += f"<td style='font-size:12px; color:#82b1ff; font-weight:700;'>{escape(wbs)}</td>"
        h += f"<td style='font-weight:600;font-size:13px;'>{escape(task)}</td>"
        h += f"<td style='font-size:11px; color:#b0c4e2;'>{escape(pred)}</td>"
        h += f"<td style='font-size:12px; text-align:center;'>{escape(te)}</td>"
        h += f"<td>{status_badge(status)}</td>"
        h += f"<td colspan='{weeks}' class='tl'><div class='bg'>{bg}</div><div class='barw'><div class='bar{crit_class}' style='left:{left}%;width:{width}%;background:linear-gradient(135deg,{c} 0%,{c}cc 100%);'>{escape(label)}</div></div></td>"
        h += "</tr>"

    h += "</tbody></table></div>"
    return h

# =========================
# DB 정규화 (WBS, 의사결정 포함)
# =========================
def normalize_tasks_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame()
    req = ["id", "업무명", "담당자", "팀", "상태", "시작일", "종료일", "sent", 
           "WBS_코드", "선행_업무", "낙관적_시간(O)", "가능성_높은_시간(M)", "비관적_시간(P)", "기대_시간(TE)"]
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

def auth_gate():
    if EDIT_PASSWORD == "" and VIEW_PASSWORD == "":
        st.session_state.role = "edit"
        return
    if st.session_state.get("role") is not None: return
    
    st.markdown("""
    <div style="display:flex;justify-content:center;align-items:center;min-height:70vh;">
        <div style="text-align:center;">
            <div style="font-size:48px;margin-bottom:8px;">🏛️</div>
            <h1 style="font-size:28px;font-weight:800;margin-bottom:4px;">Hallaon Workspace</h1>
            <p style="color:rgba(176,196,226,0.6);font-size:14px;margin-bottom:32px;">팀 워크스페이스에 로그인하세요</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        role_choice = st.radio("권한", ["조회", "편집"], horizontal=True)
        pw = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("로그인", type="primary", use_container_width=True):
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
decisions_df = st.session_state.decisions_df.copy()

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
        <span style="font-size:28px;">🏛️</span>
        <div>
            <div style="font-size:18px;font-weight:800;letter-spacing:-0.02em;">Hallaon</div>
            <div style="font-size:11px;color:rgba(176,196,226,0.5);font-weight:600;letter-spacing:0.06em;text-transform:uppercase;">Workspace</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<span class='role-badge'>{'✏️ 편집' if can_edit() else '👁️ 조회'}</span>", unsafe_allow_html=True)
    
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    
    if st.button("🔄 새로고침 / 권한 전환", use_container_width=True):
        with st.spinner("데이터를 동기화 중입니다..."):
            init_data()
            st.session_state.role = None
        st.rerun()
    
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.caption("WORKSPACE")
    
    menu = st.radio(
        "메뉴",
        ["🏠 홈 (안내서)", "📋 업무 및 WBS", "📊 간트 차트 (CPM)", "📅 캘린더", "📈 대시보드", "🗂️ 안건", "⚖️ 의사결정", "📝 회의록", "🤖 작업 전송"],
        label_visibility="collapsed"
    )

# =========================
# Tab: 홈 (안내서)
# =========================
# =========================
# Tab: 홈 (안내서)
# =========================
if menu == "🏠 홈 (안내서)":
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(130, 177, 255, 0.1) 0%, rgba(13, 17, 23, 0) 100%); 
                padding: 40px 32px; border-radius: 24px; border: 1px solid var(--border-subtle); margin-bottom: 32px;">
        <h1 style="font-size:36px;font-weight:800;margin:0 0 12px 0;letter-spacing:-0.03em;">
            <span style="color:#82b1ff;">Hallaon</span> Workspace
        </h1>
        <p style="color:rgba(176,196,226,0.8);font-size:16px;line-height:1.6;margin:0;max-width:800px;">
            탐라영재관 자율회 한라온의 성공적인 프로젝트 완수를 위한 <b>데이터 기반 의사결정 및 일정 관리 플랫폼</b>입니다.<br>
            직감을 넘어, 체계적인 알고리즘과 시각화된 데이터로 팀의 목표를 달성하세요.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h3 style='margin-bottom: 16px;'>📖 한라온 필수 가이드 (처음 오셨다면 꼭 읽어주세요!)</h3>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("""
        <div style="background: var(--dp02); padding: 24px; border-radius: 16px; border: 1px solid var(--border-default); height: 100%;">
            <h4 style="color: #ff8a9e; margin-top: 0;">1. 📋 WBS 란 무엇인가요?</h4>
            <p style="color: var(--text-secondary); font-size: 14px;">
                <b>WBS(Work Breakdown Structure)</b>는 거대한 프로젝트를 아주 작은 단위의 '실행 가능한 업무'로 쪼개는 작업입니다.
            </p>
            <ul style="color: var(--text-secondary); font-size: 14px; padding-left: 20px;">
                <li><b>왜 필요한가요?</b> "체육대회 준비하기"라는 막연한 업무를 "장소 대관(1.1)", "예산안 작성(1.2)", "포스터 제작(2.1)" 등으로 잘게 나누어 <b>누가, 언제까지, 무엇을</b> 해야 하는지 명확하게 만듭니다.</li>
                <li><b>선행 업무:</b> 포스터(2.1)를 만들려면 장소(1.1)가 먼저 확정되어야겠죠? 이때 2.1 업무의 '선행 업무' 칸에 1.1을 적어주면 두 업무가 연결됩니다.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        # WBS의 이해를 돕기 위한 다이어그램 트리거
        

[Image of Work breakdown structure diagram]


    with c2:
        st.markdown("""
        <div style="background: var(--dp02); padding: 24px; border-radius: 16px; border: 1px solid var(--border-default); height: 100%;">
            <h4 style="color: #ffe082; margin-top: 0;">2. 📊 간트 차트와 핵심 경로(CPM)</h4>
            <p style="color: var(--text-secondary); font-size: 14px;">
                <b>간트 차트</b>는 WBS로 쪼갠 업무들을 달력 위에 막대그래프로 펼쳐놓아 한눈에 일정을 파악하는 도구입니다.
            </p>
            <ul style="color: var(--text-secondary); font-size: 14px; padding-left: 20px;">
                <li><b>PERT (3점 추정):</b> 업무를 추가할 때 낙관적(빠름), 보통, 비관적(느림) 시간을 입력하면 알고리즘이 가장 현실적인 소요일을 자동 계산합니다.</li>
                <li><b>🔥 핵심 경로 (Critical Path):</b> 간트 차트에서 <b><span style='color:#ff5252;'>붉은색 막대</span></b>로 표시된 업무들입니다. 이 업무들이 하루라도 지연되면 프로젝트 전체 일정이 지연되는 아주 중요한 '병목 업무'를 뜻합니다. 우선적으로 관리해 주세요!</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        # 간트 차트와 핵심 경로 이해를 돕기 위한 다이어그램 트리거
        

    st.markdown("<hr style='margin: 40px 0;'>", unsafe_allow_html=True)
    
    st.markdown("### 🚀 3단계 빠른 시작")
    col_step1, col_step2, col_step3 = st.columns(3)
    
    with col_step1:
        st.info("**STEP 1. 업무 분할 및 등록**\n\n좌측 `📋 업무 및 WBS` 메뉴로 이동하여 프로젝트를 WBS 코드로 나누고, 선행 업무와 PERT 예상 시간을 등록하세요.")
    with col_step2:
        st.warning("**STEP 2. 핵심 경로 파악**\n\n`📊 간트 차트` 메뉴에서 붉은색으로 표시된 핵심 경로(Critical Path) 업무를 확인하고 담당자를 독려하세요.")
    with col_step3:
        st.success("**STEP 3. 알고리즘 의사결정**\n\n팀 내 의견이 갈리거나 중요한 결정이 필요할 때, `⚖️ 의사결정` 탭의 가중치 모델을 활용해 객관적으로 결정하세요.")

# =========================
# Tab: 업무 및 WBS
# =========================
elif menu == "📋 업무 및 WBS":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📋 업무 및 WBS</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">작업 분할 구조도(WBS)와 PERT를 활용해 일정을 관리하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    with st.expander("➕ 새 업무/WBS 추가", expanded=True):
        with st.form("add_wbs_task_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1: 
                WBS_코드 = st.text_input("WBS 코드 (예: 1.1)")
                업무명 = st.text_input("업무명")
            with c2:
                담당자 = st.text_input("담당자")
                팀 = st.multiselect("팀", TEAM_OPTIONS)
            with c3:
                선행_업무 = st.text_input("선행 업무 WBS (없으면 공란)")
                상태 = st.selectbox("상태", TASK_STATUS_OPTIONS)
            with c4:
                st.caption("PERT 예상 소요 시간(일)")
                O_time = st.number_input("낙관적(O)", min_value=0, step=1)
                M_time = st.number_input("가능성 높음(M)", min_value=0, step=1)
                P_time = st.number_input("비관적(P)", min_value=0, step=1)
                
            add_btn = st.form_submit_button("➕ 업무 추가", type="primary", disabled=not can_edit())

        if add_btn and 업무명:
            with st.spinner('WBS 데이터를 기록하고 있습니다...'):
                TE = round((O_time + 4 * M_time + P_time) / 6, 1) if (O_time or M_time or P_time) else 0
                
                new_row = {
                    "id": str(uuid.uuid4()), "업무명": 업무명, "담당자": 담당자 or "담당자 미정",
                    "팀": ", ".join(팀) or "미지정", "상태": 상태, 
                    "시작일": safe_date_str(date.today()), "종료일": safe_date_str(date.today() + timedelta(days=TE)), 
                    "sent": "False", "WBS_코드": WBS_코드, "선행_업무": 선행_업무,
                    "낙관적_시간(O)": O_time, "가능성_높은_시간(M)": M_time, "비관적_시간(P)": P_time, "기대_시간(TE)": TE
                }
                tasks_df = pd.concat([st.session_state.tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.tasks_df = tasks_df
                save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
            
            st.toast(f"✅ '{업무명}' 업무가 추가되었습니다!", icon="🎉")
            st.rerun()

    todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)].copy()
    done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)].copy()
    disp_cols = ["WBS_코드", "선행_업무", "업무명", "담당자", "팀", "상태", "기대_시간(TE)"]

    with st.expander(f"⏳ 진행 중인 업무 ({len(todo_df)})", expanded=True):
        if todo_df.empty: st.caption("진행 중인 업무가 없습니다.")
        else: st.dataframe(todo_df[disp_cols], use_container_width=True, hide_index=True)

    with st.expander(f"✅ 완료된 업무 ({len(done_df)})", expanded=False):
        if done_df.empty: st.caption("완료된 업무가 없습니다.")
        else: st.dataframe(done_df[disp_cols], use_container_width=True, hide_index=True)

    st.markdown("### ✏️ 업무 수정 / 삭제")
    e = tasks_df.copy()
    e.insert(0, "선택", False)
    e["시작일"] = pd.to_datetime(e["시작일"]).dt.date
    e["종료일"] = pd.to_datetime(e["종료일"]).dt.date

    edited = st.data_editor(
        e[["선택", "WBS_코드", "선행_업무", "업무명", "담당자", "팀", "상태", "시작일", "종료일", "기대_시간(TE)"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={
            "선택": st.column_config.CheckboxColumn("선택"),
            "상태": st.column_config.SelectboxColumn("상태", options=TASK_STATUS_OPTIONS)
        }
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 수정사항 저장", type="primary", disabled=not can_edit(), use_container_width=True):
            base = tasks_df.copy().reset_index(drop=True)
            edited["시작일"] = edited["시작일"].apply(safe_date_str)
            edited["종료일"] = edited["종료일"].apply(safe_date_str)
            update_cols = ["WBS_코드", "선행_업무", "업무명", "담당자", "팀", "상태", "시작일", "종료일", "기대_시간(TE)"]
            base[update_cols] = edited[update_cols]
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
elif menu == "📊 간트 차트 (CPM)":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📊 간트 차트 (CPM 적용)</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">선행 업무 관계를 파악하고 핵심 경로(Critical Path)를 붉은색으로 강조합니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    hide_done = st.toggle("완료 업무 숨기기", value=True)
    gdf = tasks_df.copy()
    if hide_done:
        gdf = gdf[~gdf["상태"].str.contains("완료", na=False)].copy()

    components.html(render_gantt(gdf), height=max(700, len(gdf)*60 + 250), scrolling=True)

# =========================
# Tab: 캘린더
# =========================
elif menu == "📅 캘린더":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📅 종합 캘린더</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">업무 일정, 안건 심의, 회의록을 하나의 달력에서 확인하세요</p>
    </div>
    """, unsafe_allow_html=True)

# 이벤트 데이터 조립
    calendar_events = []
    
    # 1. 업무 데이터 (기간)
    for _, r in tasks_df.iterrows():
        if r["시작일"] and r["종료일"]:
            color = TEAM_COLORS.get(str(r["팀"]).split(",")[0].strip(), "#90a4ae")
            end_date = (pd.to_datetime(r["종료일"]) + timedelta(days=1)).strftime("%Y-%m-%d")
            calendar_events.append({
                "title": f"📋 {r['업무명']} ({r['담당자']})",
                "start": r["시작일"],
                "end": end_date,
                "backgroundColor": f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)}, 0.15)",
                "borderColor": color,
                "textColor": color # 🚨 여기를 흰색(#f0f6ff)에서 color 변수로 변경!
            })
            
    # 2. 회의 데이터 (당일)
    for _, r in meetings_df.iterrows():
        if r["회의일자"]:
            calendar_events.append({
                "title": f"📝 {r['제목']}",
                "start": r["회의일자"],
                "backgroundColor": "rgba(105, 240, 174, 0.15)",
                "borderColor": "#69f0ae",
                "textColor": "#69f0ae", # 🚨 변경
                "allDay": True
            })

    # 3. 안건 데이터 (당일)
    for _, r in agenda_df.iterrows():
        if r["입안일"]:
            calendar_events.append({
                "title": f"🗂️ {r['안건명']} (입안)",
                "start": r["입안일"],
                "backgroundColor": "rgba(255, 138, 158, 0.15)",
                "borderColor": "#ff8a9e",
                "textColor": "#ff8a9e", # 🚨 변경
                "allDay": True
            })

    calendar_options = {
        "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,listWeek"},
        "initialView": "dayGridMonth", "themeSystem": "standard", "eventDisplay": "block",
    }
    
    custom_css = """
        .fc { font-family: 'Inter', sans-serif; }
        .fc-theme-standard td, .fc-theme-standard th { border-color: rgba(148,180,226,0.1) !important; }
        .fc-toolbar-title { font-weight: 800 !important; color: rgba(240,246,255,0.92) !important; }
        .fc-button { background-color: #1c2636 !important; border-color: rgba(148,180,226,0.2) !important; color: #b0c4e2 !important; box-shadow: none !important; }
        .fc-button:hover { background-color: #2a3a52 !important; color: #fff !important; }
        .fc-button-active { background-color: #82b1ff !important; color: #0d1117 !important; border-color: #82b1ff !important; font-weight:bold; }
        .fc-day-today { background-color: rgba(130,177,255,0.05) !important; }
        .fc-event { border-radius: 4px; padding: 2px 4px; font-size: 11px; font-weight: 600; cursor: pointer; border-width: 1px !important;}
    """
    
    st.markdown("<div style='background: #131a24; padding: 20px; border-radius: 16px; border: 1px solid rgba(148,180,226,0.12); box-shadow: 0 4px 8px rgba(0,0,0,0.2);'>", unsafe_allow_html=True)
    calendar(events=calendar_events, options=calendar_options, custom_css=custom_css, key="hallaon_calendar")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# Tab: 대시보드
# =========================
elif menu == "📈 대시보드":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📈 종합 대시보드</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">2026 한라온 프로젝트 현황을 한눈에 파악하세요</p>
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
            st.markdown("##### 상태별 태스크 분포")
            s = unique_df["상태"].value_counts().reset_index()
            s.columns = ["상태","개수"]
            fig1 = px.pie(s, names="상태", values="개수", hole=0.55, color="상태", color_discrete_map=STATUS_COLORS)
            fig1.update_layout(
                template="plotly_dark", height=400, showlegend=True,
                legend=dict(font=dict(size=12, color="rgba(240,246,255,0.8)"), bgcolor="rgba(0,0,0,0)"),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20, l=20, r=20), font=dict(family="Inter, system-ui, sans-serif")
            )
            fig1.update_traces(textfont_size=12, textfont_color="rgba(240,246,255,0.9)")
            st.plotly_chart(fig1, use_container_width=True)

        with chart_col2:
            st.markdown("##### 담당자별 태스크")
            a = unique_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#82b1ff"])
            fig2.update_layout(
                template="plotly_dark", height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=40, l=40, r=20), font=dict(family="Inter, system-ui, sans-serif", color="rgba(240,246,255,0.8)"),
                xaxis=dict(gridcolor="rgba(148,180,226,0.06)"), yaxis=dict(gridcolor="rgba(148,180,226,0.06)"), bargap=0.3,
            )
            fig2.update_traces(marker_line_width=0, marker=dict(cornerradius=6), textfont=dict(color="rgba(240,246,255,0.9)", size=13, family="Inter"))
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# Tab: 안건
# =========================
elif menu == "🗂️ 안건":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">🗂️ 안건 관리</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">팀 안건을 등록하고 상태를 추적하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    with st.form("add_agenda_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: 안건명 = st.text_input("안건명", placeholder="안건명을 입력하세요")
        with c2: 팀 = st.multiselect("팀", TEAM_OPTIONS, default=[])
        with c3: 입안자 = st.text_input("입안자", placeholder="입안자 이름")
        with c4: 입안일 = st.date_input("입안일", value=date.today())
        상태 = st.selectbox("상태", AGENDA_STATUS_OPTIONS, index=0)
        add_btn = st.form_submit_button("➕ 안건 추가", type="primary", disabled=not can_edit())

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
            "선택": st.column_config.CheckboxColumn("선택"),
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
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">⚖️ 의사결정 모델</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">가중치 평가(Weighted Scoring) 알고리즘으로 직감을 배제한 최적의 대안을 산출합니다.</p>
    </div>
    """, unsafe_allow_html=True)

    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    if "criteria_count" not in st.session_state: st.session_state.criteria_count = 3
    if "alt_count" not in st.session_state: st.session_state.alt_count = 2

    active_agendas = agenda_df[agenda_df["상태"] != "완료"]["안건명"].tolist()

    with st.form("decision_model_form"):
        st.markdown("### 1. 대상 안건 및 기준 설정")
        sel_agenda = st.selectbox("의사결정이 필요한 안건 선택", active_agendas if active_agendas else ["등록된 안건 없음"])
        
        c1, c2 = st.columns(2)
        with c1:
            st.caption("평가 기준 (예: 예산, 실현가능성, 파급력)")
            criteria = []
            weights = []
            for i in range(st.session_state.criteria_count):
                col_c, col_w = st.columns([7, 3])
                with col_c: cr = st.text_input(f"기준 {i+1}", key=f"cr_{i}")
                with col_w: wt = st.number_input("가중치(%)", min_value=0, max_value=100, value=30, key=f"wt_{i}")
                criteria.append(cr)
                weights.append(wt)
                
        with c2:
            st.caption("비교할 대안 (예: A업체 진행, B업체 진행)")
            alts = []
            for i in range(st.session_state.alt_count):
                al = st.text_input(f"대안 {i+1}", key=f"alt_{i}")
                alts.append(al)

        st.markdown("---")
        st.markdown("### 2. 대안별 평가 (1~10점)")
        st.caption("각 대안이 해당 기준을 얼마나 잘 충족하는지 점수를 매겨주세요.")
        
        scores = {}
        for alt in alts:
            if alt.strip():
                scores[alt] = []
                st.markdown(f"**🔷 {alt}**")
                s_cols = st.columns(len(criteria))
                for idx, cr in enumerate(criteria):
                    if cr.strip():
                        with s_cols[idx]:
                            score = st.slider(f"{cr}", 1, 10, 5, key=f"score_{alt}_{idx}")
                            scores[alt].append(score)

        submitted = st.form_submit_button("🧠 알고리즘 실행", type="primary", disabled=not can_edit())

    if submitted:
        if sum(weights) != 100:
            st.error(f"가중치의 합이 100%가 되어야 합니다. (현재: {sum(weights)}%)")
        elif not sel_agenda or sel_agenda == "등록된 안건 없음":
            st.warning("안건을 먼저 등록하고 선택해주세요.")
        else:
            with st.spinner("최적의 대안을 계산 중입니다..."):
                results = []
                for alt, score_list in scores.items():
                    total_score = sum((score * weight / 100) for score, weight in zip(score_list, weights))
                    results.append({"대안": alt, "최종 점수": round(total_score, 2)})
                
                res_df = pd.DataFrame(results).sort_values("최종 점수", ascending=False)
                best_alt = res_df.iloc[0]["대안"]
                best_score = res_df.iloc[0]["최종 점수"]

                st.success(f"🎉 알고리즘 추천: **{best_alt}** (총점 {best_score}점)")
                
                fig = px.bar(res_df, x="대안", y="최종 점수", text="최종 점수", 
                             color="대안", color_discrete_sequence=["#82b1ff", "#ff8a9e", "#69f0ae"])
                fig.update_layout(
                    template="plotly_dark", height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter", color="rgba(240,246,255,0.8)"), margin=dict(t=20, b=20, l=20, r=20)
                )
                st.plotly_chart(fig, use_container_width=True)

# =========================
# Tab: 회의록
# =========================
elif menu == "📝 회의록":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📝 회의록</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">팀 회의 기록을 작성하고 관리하세요</p>
    </div>
    """, unsafe_allow_html=True)

    if "sel_mtg_id" not in st.session_state: st.session_state.sel_mtg_id = None
    if "is_edit_mtg" not in st.session_state: st.session_state.is_edit_mtg = False

    col_nav, col_viewer = st.columns([2.5, 7.5])

    with col_nav:
        if st.button("➕ 새 회의록 작성", use_container_width=True, disabled=not can_edit(), type="primary"):
            st.session_state.sel_mtg_id = "NEW"; st.session_state.is_edit_mtg = True; st.rerun()

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.caption("분류별 폴더")

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
        st.markdown("""
        <div style="border-left:1px solid rgba(148,180,226,0.08);padding-left:32px;min-height:600px;">
        """, unsafe_allow_html=True)

        if st.session_state.sel_mtg_id is None:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:400px;color:rgba(176,196,226,0.4);">
                <div style="font-size:48px;margin-bottom:16px;">📄</div>
                <div style="font-size:16px;font-weight:600;">회의록을 선택하거나 새로 작성하세요</div>
            </div>
            """, unsafe_allow_html=True)

        elif st.session_state.sel_mtg_id == "NEW":
            st.subheader("✨ 새 회의록 작성")
            with st.form("new_mtg_form"):
                f_title = st.text_input("회의 제목", placeholder="회의 제목을 입력하세요")
                c1, c2, c3 = st.columns(3)
                with c1: f_folder = st.selectbox("분류(폴더)", ["전체 회의"] + TEAM_OPTIONS)
                with c2: f_date = st.date_input("회의 일자", value=date.today())
                with c3: f_author = st.text_input("작성자", placeholder="작성자 이름")
                f_content = st.text_area("회의 내용 (Markdown 지원)", height=450, placeholder="회의 내용을 작성하세요...")
                if st.form_submit_button("💾 저장하기", type="primary"):
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

                    st.caption(f"📁 {mtg['분류']}  ·  📅 {mtg['회의일자']}  ·  👤 {mtg['작성자']}")
                    st.markdown("---")
                    st.markdown(mtg['내용'].replace('\n', '  \n'))

                    st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
                    if can_edit() and st.button("🗑️ 이 회의록 삭제", type="secondary"):
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
                            if st.form_submit_button("💾 저장하기", type="primary"):
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
# Tab: 작업 전송
# =========================
elif menu == "🤖 작업 전송":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">🤖 작업 전송</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">미전송 업무와 안건을 디스코드로 전송하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not can_edit(): st.info("조회 권한에서는 전송이 불가합니다. '권한 전환'으로 로그인하세요.")

    t_task, t_agenda = st.tabs(["📋 업무 전송", "🗂️ 안건 전송"])

    with t_task:
        u_tasks = tasks_df[tasks_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u_tasks.empty: st.info("미전송 업무가 없습니다.")
        else:
            v_t = u_tasks.copy()
            v_t.insert(0, "전송", False)
            pick_t = st.data_editor(
                v_t[["전송","WBS_코드","업무명","담당자","팀","상태","시작일","종료일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            selected_task_indices = pick_t.index[pick_t["전송"] == True].tolist()
            if st.button("🚀 선택 업무 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_task_indices), use_container_width=True):
                sel_tasks = u_tasks.iloc[selected_task_indices].copy()
                fields = [{
                    "name": f"🔹 {r['업무명']} ({r['팀']})",
                    "value": f"👤 담당: {r['담당자']}\n🏷️ 상태: {r['상태']}\n📅 일정: {r['시작일']} → {r['종료일']}\n📝 WBS: {r.get('WBS_코드', '')}",
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
        if u_agendas.empty: st.info("미전송 안건이 없습니다.")
        else:
            v_a = u_agendas.copy()
            v_a.insert(0, "전송", False)
            pick_a = st.data_editor(
                v_a[["전송","안건명","입안자","팀","상태","입안일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            selected_agenda_indices = pick_a.index[pick_a["전송"] == True].tolist()
            if st.button("📨 선택 안건 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_agenda_indices), use_container_width=True):
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
