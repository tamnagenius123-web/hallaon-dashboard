import os
import uuid
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import gspread
import base64
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
from html import escape
import streamlit.components.v1 as components
from streamlit_calendar import calendar

st.set_page_config(page_title="HALLAON Workspace", layout="wide", initial_sidebar_state="expanded")

LOGO_IMAGE_PATH = "image_02c15f0a-577a-462d-8cd3-1ca275ece279.png"

# =========================
# Google Sheets DB
# =========================
def get_gsheets_client():
    try:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        creds_dict["private_key"] = creds_dict["private_key"].replace('\\n', '\n')
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 인증 실패.\n오류: {e}")
        st.stop()

WORKSHEET_TASKS = "Tasks"
WORKSHEET_AGENDA = "Agenda"
WORKSHEET_MEETINGS = "Meetings"
WORKSHEET_DECISIONS = "DECISIONS"
WORKSHEET_USERS = "Users"
WORKSHEET_SCHEDULES = "Schedules"

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
    except:
        return pd.DataFrame()

def save_df_to_gsheet(df, worksheet_name):
    try:
        sheet = get_sheet()
        try:
            worksheet = sheet.worksheet(worksheet_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=worksheet_name, rows="1000", cols="20")
        worksheet.clear()
        safe_df = df.fillna("")
        final_data = [safe_df.columns.values.tolist()] + safe_df.values.tolist()
        worksheet.update(final_data)
    except Exception as e:
        st.error(f"'{worksheet_name}' 시트에 저장 실패.\n오류: {e}")

# =========================
# Config
# =========================
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")
TEAM_OPTIONS = ["PM", "CD", "FS", "DM", "OPS"]
TASK_STATUS_OPTIONS = ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"]
AGENDA_STATUS_OPTIONS = ["시작 전", "진행 중", "완료", "보류"]

TEAM_COLORS = {"PM": "#6C9CFF", "CD": "#FF7EB3", "FS": "#5EEAA0", "DM": "#B18CFF", "OPS": "#FFCB57"}
STATUS_COLORS = {
    "완료": "#5EEAA0", "막힘": "#FF6B6B", "진행 중": "#FFCB57",
    "작업 중": "#FFB070", "대기": "#B18CFF", "시작 전": "#8899AA", "보류": "#6B7B8D",
}

# =========================
# CSS — Full Overhaul
# =========================
st.markdown("""
<style>
#MainMenu {visibility:hidden;} footer {visibility:hidden;} header[data-testid="stHeader"] {background:transparent !important; height:0 !important;}
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --sf-ground: #0B0F14; --sf-base: #101621; --sf-raised: #151C2A; --sf-overlay: #1A2335; --sf-top: #1F2A40;
    --bd-subtle: rgba(140,170,220,0.07); --bd-default: rgba(140,170,220,0.12); --bd-strong: rgba(140,170,220,0.20);
    --tx-primary: #E8EDF5; --tx-secondary: #9BAABB; --tx-tertiary: #6B7B8D; --tx-inverse: #0B0F14;
    --accent: #6C9CFF; --accent-soft: rgba(108,156,255,0.12); --accent-hover: rgba(108,156,255,0.22);
    --sh-sm: 0 2px 6px rgba(0,0,0,0.24); --sh-md: 0 4px 12px rgba(0,0,0,0.28); --sh-lg: 0 8px 28px rgba(0,0,0,0.36);
    --r-sm: 8px; --r-md: 12px; --r-lg: 16px; --r-xl: 20px; --r-full: 999px;
    --ease-out: cubic-bezier(0.16,1,0.3,1); --dur-fast: 120ms; --dur-normal: 200ms;
}

html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: var(--sf-ground) !important; color: var(--tx-primary) !important;
    font-weight: 450; line-height: 1.65; -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 { color: var(--tx-primary) !important; font-weight: 800 !important; letter-spacing: -0.025em; }
p, div.stMarkdown, label, span { color: var(--tx-primary) !important; }
small, [data-testid="stCaptionContainer"] * { color: var(--tx-secondary) !important; font-size: 12px !important; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; }

/* ─── LOGIN ─── */
.login-logo-container { display: flex; justify-content: center; margin-bottom: 20px; }
.login-logo-img {
    width: 160px; height: 160px; object-fit: contain;
    background: rgba(255,255,255,0.95); border-radius: 28px;
    padding: 18px; box-shadow: 0 8px 32px rgba(108,156,255,0.18), 0 0 60px rgba(108,156,255,0.06);
    border: 1px solid rgba(255,255,255,0.15);
}

/* ─── SIDEBAR ─── */
section[data-testid="stSidebar"] { background: var(--sf-base) !important; border-right: 1px solid var(--bd-subtle) !important; }
section[data-testid="stSidebar"] * { color: var(--tx-primary) !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label {
    border-radius: var(--r-md) !important; padding: 10px 14px !important;
    transition: all var(--dur-fast) var(--ease-out); margin-bottom: 2px !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover { background: var(--accent-soft) !important; }
section[data-testid="stSidebar"] .sidebar-logo { width: 36px; height: 36px; border-radius: 10px; background: #fff; padding: 4px; object-fit: contain; }

/* Sidebar collapse button */
button[data-testid="stSidebarCollapsedControl"] {
    background: var(--accent) !important; border-radius: 0 var(--r-lg) var(--r-lg) 0 !important;
    box-shadow: var(--sh-md), 0 0 16px rgba(108,156,255,0.3) !important;
    position: fixed !important; top: 12px !important; left: 0 !important; z-index: 9999;
}
button[data-testid="stSidebarCollapsedControl"] svg { color: var(--tx-inverse) !important; fill: var(--tx-inverse) !important; }

/* ─── METRICS ─── */
div[data-testid="metric-container"] {
    background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-xl) !important; padding: 20px 24px !important;
    transition: all var(--dur-normal) var(--ease-out);
}
div[data-testid="metric-container"]:hover { box-shadow: var(--sh-md) !important; transform: translateY(-2px); }
div[data-testid="stMetricLabel"] { color: var(--tx-secondary) !important; font-size: 12px !important; font-weight: 700 !important; text-transform: uppercase; letter-spacing: 0.06em; }
div[data-testid="stMetricValue"] { color: var(--tx-primary) !important; font-size: 30px !important; font-weight: 900 !important; }

/* ─── DATAFRAMES ─── */
div[data-testid="stDataFrame"] {
    background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-lg) !important; overflow: hidden;
}
div[data-testid="stDataFrame"] [role="columnheader"] {
    background: var(--sf-overlay) !important; color: var(--tx-secondary) !important;
    font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.05em;
}

/* ─── EXPANDERS ─── */
div[data-testid="stExpander"] details {
    background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-lg) !important; margin-bottom: 8px;
}
div[data-testid="stExpander"] summary { background: var(--sf-overlay) !important; padding: 14px 18px !important; }
div[data-testid="stExpanderDetails"] { background: var(--sf-raised) !important; }

/* ─── BUTTONS ─── */
button[kind="primary"], button[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #6C9CFF 0%, #5580E0 100%) !important;
    color: var(--tx-inverse) !important; border-radius: var(--r-md) !important;
    box-shadow: var(--sh-sm), 0 0 12px rgba(108,156,255,0.15) !important;
    font-weight: 700 !important; transition: all var(--dur-fast) var(--ease-out);
    border: none !important;
}
button[kind="primary"]:hover { box-shadow: var(--sh-md), 0 0 20px rgba(108,156,255,0.3) !important; transform: translateY(-1px); }
button[kind="secondary"] { background: var(--sf-overlay) !important; border: 1px solid var(--bd-default) !important; border-radius: var(--r-md) !important; color: var(--tx-primary) !important; }

/* ─── INPUTS — COMPLETE FIX ─── */
input, textarea,
div[data-baseweb="input"] input,
div[data-baseweb="base-input"] input,
div[data-baseweb="textarea"] textarea {
    background: var(--sf-base) !important;
    color: var(--tx-primary) !important;
    -webkit-text-fill-color: var(--tx-primary) !important;
    border: 1.5px solid var(--bd-default) !important;
    border-radius: var(--r-sm) !important;
    font-weight: 500 !important; font-size: 14px !important;
    caret-color: var(--accent) !important;
    transition: all var(--dur-fast) var(--ease-out);
}
input:focus, textarea:focus,
div[data-baseweb="input"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
    background: var(--sf-raised) !important;
}
input::placeholder, textarea::placeholder {
    color: var(--tx-tertiary) !important;
    -webkit-text-fill-color: var(--tx-tertiary) !important;
}

/* Autofill/Paste white bg fix */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active,
textarea:-webkit-autofill {
    -webkit-box-shadow: 0 0 0 1000px #101621 inset !important;
    -webkit-text-fill-color: #E8EDF5 !important;
    box-shadow: 0 0 0 1000px #101621 inset !important;
    background-color: #101621 !important;
    color: #E8EDF5 !important;
    border: 1.5px solid rgba(140,170,220,0.12) !important;
    transition: background-color 600000s 0s, color 600000s 0s;
}

/* ─── SELECT / DROPDOWN — 회색 네모 문제 수정 ─── */
div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div > div {
    background: var(--sf-base) !important;
    color: var(--tx-primary) !important;
    border: 1.5px solid var(--bd-default) !important;
    border-radius: var(--r-sm) !important;
    min-height: 42px !important;
}
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
/* Dropdown menu */
div[data-baseweb="popover"] > div,
ul[data-baseweb="menu"],
[data-baseweb="menu"] {
    background: var(--sf-overlay) !important;
    border: 1px solid var(--bd-strong) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--sh-lg) !important;
}
[data-baseweb="menu"] li,
ul[data-baseweb="menu"] li {
    background: transparent !important;
    color: var(--tx-primary) !important;
}
[data-baseweb="menu"] li:hover,
ul[data-baseweb="menu"] li:hover {
    background: var(--accent-soft) !important;
}
/* Selected value text in select */
div[data-baseweb="select"] span,
div[data-baseweb="select"] [data-baseweb="tag"] {
    color: var(--tx-primary) !important;
}

/* MultiSelect tags */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background: var(--accent-soft) !important;
    border: 1px solid rgba(108,156,255,0.3) !important;
    border-radius: var(--r-sm) !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    color: var(--accent) !important; font-weight: 700 !important; overflow: visible !important;
}

/* ─── FORMS ─── */
[data-testid="stForm"] {
    background: var(--sf-raised) !important; border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-xl) !important; padding: 24px !important;
}

/* ─── TABS ─── */
div[data-testid="stTabs"] button { color: var(--tx-tertiary) !important; font-weight: 600 !important; }
div[data-testid="stTabs"] button:hover { color: var(--tx-primary) !important; background: var(--accent-soft) !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--accent) !important; font-weight: 700 !important; }
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: var(--accent) !important; height: 3px !important; border-radius: 3px 3px 0 0 !important; }

/* ─── CALENDAR PICKER ─── */
[data-baseweb="calendar"], [data-baseweb="calendar"] * {
    background: var(--sf-overlay) !important; color: var(--tx-primary) !important; border-color: var(--bd-default) !important;
}
[data-baseweb="calendar"] [aria-selected="true"] { background: var(--accent) !important; color: var(--tx-inverse) !important; border-radius: var(--r-full) !important; }

/* ─── TOGGLE ─── */
[data-testid="stBaseButton-secondary"] { background: var(--sf-overlay) !important; }

/* ─── ROLE BADGE ─── */
.role-badge {
    display: inline-flex; align-items: center; gap: 6px; padding: 6px 16px;
    border-radius: var(--r-full); font-size: 12px; font-weight: 700;
    border: 1px solid var(--bd-default); background: var(--sf-overlay); color: var(--accent) !important;
}

/* ─── ALERTS ─── */
div[data-testid="stAlert"] { border-radius: var(--r-md) !important; border: 1px solid var(--bd-default) !important; }

/* ─── SCROLLBAR ─── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bd-strong); border-radius: var(--r-full); }
::-webkit-scrollbar-thumb:hover { background: var(--tx-tertiary); }

/* ─── BLOCK CONTAINER SPACING ─── */
.block-container { padding: 24px 32px !important; max-width: 1440px; }

/* ─── Number input arrows dark ─── */
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button { opacity: 0.6; }

/* ─── MOBILE RESPONSIVE ─── */
@media (max-width: 768px) {
    .block-container { padding: 12px 8px !important; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    div[data-testid="stMetricLabel"] { font-size: 10px !important; }
    h2 { font-size: 20px !important; }
    .login-logo-img { width: 120px; height: 120px; padding: 14px; border-radius: 22px; }
    div[data-testid="stExpander"] summary { padding: 10px 14px !important; font-size: 13px !important; }
    section[data-testid="stSidebar"] [data-baseweb="radio"] label { padding: 8px 10px !important; font-size: 13px !important; }
}
@media (max-width: 480px) {
    .block-container { padding: 8px 4px !important; }
    .login-logo-img { width: 100px; height: 100px; padding: 10px; border-radius: 18px; }
}
</style>
""", unsafe_allow_html=True)

# =========================
# Utils
# =========================
def safe_date_str(v):
    try: return pd.to_datetime(v).strftime("%Y-%m-%d")
    except: return date.today().strftime("%Y-%m-%d")

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8899AA")
    r, g, b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
    return f"<span style='display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;background:rgba({r},{g},{b},0.14);color:{c};font-size:11px;font-weight:700;border:1px solid rgba({r},{g},{b},0.25);white-space:nowrap;'>{escape(s)}</span>"

def team_badge(team):
    t = str(team).split(",")[0].strip() if str(team).strip() else "미지정"
    c = TEAM_COLORS.get(t, "#8899AA")
    r, g, b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
    return f"<span style='display:inline-flex;align-items:center;padding:3px 10px;border-radius:999px;background:rgba({r},{g},{b},0.14);color:{c};font-size:11px;font-weight:700;border:1px solid rgba({r},{g},{b},0.25);white-space:nowrap;'>{escape(t)}</span>"

def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def send_discord(fields, title, username, color=3447003):
    if not DISCORD_WEBHOOK_URL: return False, "DISCORD_WEBHOOK_URL이 설정되지 않았습니다."
    try:
        sent = 0
        for i in range(0, len(fields), 25):
            batch = fields[i:i+25]
            payload = {"username": username, "embeds": [{"title": title, "color": color, "fields": batch, "footer": {"text": f"HALLAON Agile • {len(batch)}건"}}]}
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if r.status_code not in (200, 204): return False, f"HTTP {r.status_code}: {r.text[:120]}"
            sent += len(batch)
        return True, f"{sent}건 전송 완료"
    except Exception as e: return False, str(e)

# =========================
# CPM
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
    df["ES"] = df["_start"]; df["EF"] = df["_end"]
    for idx, row in df.iterrows():
        preds = str(row.get("선행_업무", "")).strip()
        if preds:
            for p in [x.strip() for x in preds.split(",") if x.strip()]:
                if p in wbs_map:
                    pred_ef = df.at[wbs_map[p], "EF"]
                    if pred_ef is not None:
                        df.at[idx, "ES"] = max(df.at[idx, "ES"], pred_ef + timedelta(days=1))
    project_end = df["EF"].max()
    df["LF"] = project_end; df["LS"] = project_end
    for idx in reversed(df.index.tolist()):
        wbs = str(df.at[idx, "WBS_코드"]).strip()
        for idx2, row2 in df.iterrows():
            preds = str(row2.get("선행_업무", "")).strip()
            if preds and wbs in [x.strip() for x in preds.split(",") if x.strip()]:
                succ_ls = df.at[idx2, "LS"]
                df.at[idx, "LF"] = min(df.at[idx, "LF"], succ_ls - timedelta(days=1))
        duration = (df.at[idx, "EF"] - df.at[idx, "ES"]).days
        df.at[idx, "LS"] = df.at[idx, "LF"] - timedelta(days=duration)
    df["_float"] = (df["LS"] - df["ES"]).dt.days
    df["is_critical"] = df["_float"] <= 0
    df.drop(columns=["_start", "_end", "ES", "EF", "LS", "LF", "_float"], inplace=True, errors='ignore')
    return df

# =========================
# Gantt Chart — FIXED
# =========================
def render_gantt(df):
    if df.empty:
        return "<div style='padding:40px;color:#9BAABB;text-align:center;font-size:14px;'>표시할 업무가 없습니다.</div>"
    g = calculate_cpm(df.copy())
    g["시작일_dt"] = pd.to_datetime(g["시작일"], errors="coerce")
    g["종료일_dt"] = pd.to_datetime(g["종료일"], errors="coerce")
    g = g.dropna(subset=["시작일_dt","종료일_dt"])
    if g.empty:
        return "<div style='padding:40px;color:#9BAABB;text-align:center;'>유효한 날짜 데이터가 없습니다.</div>"

    min_d = g["시작일_dt"].min().date()
    max_d = g["종료일_dt"].max().date()
    today = date.today()
    tl_start = min_d - timedelta(days=min_d.weekday())
    if today < tl_start:
        tl_start = today - timedelta(days=today.weekday())
    days_total = max((max_d - tl_start).days + 14, 35)
    days_total = ((days_total // 7) + 1) * 7
    weeks = days_total // 7
    tl_end = tl_start + timedelta(days=days_total)
    step = 1 if weeks <= 10 else 2 if weeks <= 20 else 4

    today_off = (today - tl_start).days
    today_pct = (today_off / days_total) * 100 if 0 <= today_off <= days_total else -999

    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
.gw{font-family:'Inter',sans-serif;background:#0B0F14;border:1px solid rgba(140,170,220,0.12);border-radius:20px;overflow-x:auto;overflow-y:auto;}
.gh{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:#101621;border-bottom:1px solid rgba(140,170,220,0.07);flex-wrap:wrap;gap:8px;}
.chip-row{display:flex;flex-wrap:wrap;gap:5px;}
.chip{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:6px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:10px;font-weight:700;}
.dot{width:6px;height:6px;border-radius:50%;}
.gt{width:100%;min-width:1100px;border-collapse:collapse;}
.gt th,.gt td{border-right:1px solid rgba(140,170,220,0.04);border-bottom:1px solid rgba(140,170,220,0.04);color:#E8EDF5;padding:8px 8px;white-space:nowrap;font-size:12px;}
.gt th{background:#151C2A;font-size:10px;text-transform:uppercase;color:#6B7B8D;position:sticky;top:0;z-index:2;letter-spacing:0.05em;}
.gt tr:hover{background:rgba(108,156,255,0.03);}
.tl{padding:0 !important;position:relative;}
.barw{position:relative;height:40px;display:flex;align-items:center;}
.bar{position:absolute;height:22px;border-radius:5px;display:flex;align-items:center;padding:0 6px;font-size:9px;font-weight:700;color:#0B0F14;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:20px;transition:all 150ms;box-shadow:0 1px 4px rgba(0,0,0,0.3);}
.bar:hover{transform:scaleY(1.2);z-index:10;box-shadow:0 4px 12px rgba(0,0,0,0.4);}
.bar.crit{background:linear-gradient(135deg,#FF6B6B 0%,#E04545 100%) !important;color:#fff !important;box-shadow:0 0 8px rgba(255,107,107,0.4);}
.today-mark{position:absolute;top:0;bottom:0;width:2px;background:#6C9CFF;z-index:3;pointer-events:none;}
.today-dot{position:absolute;top:-3px;width:8px;height:8px;border-radius:50%;background:#6C9CFF;left:-3px;}
</style>"""

    h = css + "<div class='gw'><div class='gh'><div class='chip-row'>"
    for t, c in TEAM_COLORS.items():
        h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += "<span class='chip' style='color:#FF9B9B;'><span class='dot' style='background:#FF6B6B'></span>Critical</span>"
    h += "</div><div style='color:#6B7B8D;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;'>CPM GANTT</div></div>"

    h += "<table class='gt'><thead><tr>"
    h += "<th style='width:50px;'>WBS</th><th style='width:160px;'>업무</th><th style='width:60px;'>선행</th><th style='width:50px;'>TE</th><th style='width:80px;'>상태</th>"
    for i in range(weeks):
        ws = tl_start + timedelta(days=i*7)
        lbl = f"W{i+1}<br><span style='font-size:8px;color:#566780;'>{ws.month}/{ws.day}</span>" if i % step == 0 else ""
        h += f"<th style='min-width:60px;text-align:center;'>{lbl}</th>"
    h += "</tr></thead><tbody>"

    for _, r in g.iterrows():
        is_crit = r.get("is_critical", False)
        team = str(r["팀"]).split(",")[0].strip()
        c = TEAM_COLORS.get(team, "#8899AA")
        s = r["시작일_dt"].date(); e = r["종료일_dt"].date()
        cs = max(s, tl_start); ce = min(e, tl_end - timedelta(days=1))
        off = (cs - tl_start).days
        dur = max((ce - cs).days + 1, 1)
        left_pct = (off / days_total) * 100
        width_pct = (dur / days_total) * 100
        bar_label = str(r["업무명"])[:16]
        crit_cls = " crit" if is_crit else ""

        today_html = ""
        if 0 <= today_pct <= 100:
            today_html = f"<div class='today-mark' style='left:{today_pct}%;'><div class='today-dot'></div></div>"

        h += "<tr>"
        h += f"<td style='color:#6C9CFF;font-weight:800;font-size:11px;'>{escape(str(r.get('WBS_코드','')))}</td>"
        h += f"<td style='font-weight:600;font-size:12px;max-width:160px;overflow:hidden;text-overflow:ellipsis;' title='{escape(str(r['업무명']))}'>{escape(str(r['업무명']))}</td>"
        h += f"<td style='color:#9BAABB;font-size:11px;'>{escape(str(r.get('선행_업무','')))}</td>"
        h += f"<td style='font-size:11px;'>{escape(str(r.get('기대_시간(TE)','')))}</td>"
        h += f"<td>{status_badge(r['상태'])}</td>"
        h += f"<td colspan='{weeks}' class='tl'>{today_html}<div class='barw'>"
        if not is_crit:
            h += f"<div class='bar' style='left:{left_pct}%;width:{width_pct}%;background:linear-gradient(135deg,{c},{c}cc);' title='{escape(str(r['업무명']))} ({s}~{e})'>{escape(bar_label)}</div>"
        else:
            h += f"<div class='bar crit' style='left:{left_pct}%;width:{width_pct}%;' title='⚠ CRITICAL: {escape(str(r['업무명']))} ({s}~{e})'>{escape(bar_label)}</div>"
        h += "</div></td></tr>"

    h += "</tbody></table></div>"
    return h

# =========================
# Normalize DataFrames
# =========================
def normalize_users_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["이름","비밀번호","권한"])
    for c in ["이름","비밀번호","권한"]:
        if c not in d.columns: d[c] = ""
    return d

def normalize_tasks_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame()
    req = ["id","업무명","담당자","팀","상태","시작일","종료일","sent","WBS_코드","선행_업무","낙관적_시간(O)","가능성_높은_시간(M)","비관적_시간(P)","기대_시간(TE)"]
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
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","분류","회의일자","제목","작성자","내용","linked_tasks","linked_agendas"])
    req = ["id","분류","회의일자","제목","작성자","내용","linked_tasks","linked_agendas"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    d["회의일자"] = d["회의일자"].apply(safe_date_str)
    return d[req].fillna("")

def normalize_decisions_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","안건명","평가기준","대안","최종점수","작성일"])
    req = ["id","안건명","평가기준","대안","최종점수","작성일"]
    for c in req:
        if c not in d.columns: d[c] = ""
    if d.empty: return d[req]
    d["id"] = d["id"].apply(lambda x: str(uuid.uuid4()) if not x or x == "" else x)
    return d[req].fillna("")

def normalize_schedules_df(df):
    d = df.copy() if df is not None and not df.empty else pd.DataFrame(columns=["id","이름","날짜","종료일","반복","색상","활성"])
    req = ["id","이름","날짜","종료일","반복","색상","활성"]
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
    st.session_state.schedules_df = normalize_schedules_df(load_gsheet_to_df(WORKSHEET_SCHEDULES))

# =========================
# AUTH
# =========================
def auth_gate():
    if st.session_state.get("role") is not None:
        return

    logo_b64 = ""
    try:
        for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), LOGO_IMAGE_PATH), LOGO_IMAGE_PATH]:
            if os.path.exists(p):
                logo_b64 = get_base64_of_bin_file(p); break
    except: pass

    # Cinematic intro
    if "intro_played" not in st.session_state:
        st.session_state.intro_played = True
        if logo_b64:
            st.markdown(f"""
            <style>
            .cinema-overlay {{
                position:fixed;top:0;left:0;width:100vw;height:100vh;
                background:radial-gradient(ellipse at center, #0d1420 0%, #060a10 100%);
                z-index:999999;display:flex;flex-direction:column;justify-content:center;align-items:center;
                animation: cinemaFade 4s ease-in-out forwards; pointer-events:none;
            }}
            .cinema-logo {{
                width:180px;height:180px;object-fit:contain;
                background:rgba(255,255,255,0.97);border-radius:36px;padding:24px;
                box-shadow:0 0 80px rgba(108,156,255,0.25), 0 0 160px rgba(108,156,255,0.08);
                animation: cinemaLogoAnim 3.8s ease-in-out forwards;
            }}
            .cinema-text {{
                margin-top:20px;font-family:'Inter',sans-serif;font-size:14px;font-weight:800;
                letter-spacing:0.3em;color:rgba(108,156,255,0);text-transform:uppercase;
                animation: cinemaTextAnim 3.8s ease-in-out forwards;
            }}
            .cinema-line {{
                width:0;height:1px;background:linear-gradient(90deg,transparent,#6C9CFF,transparent);
                margin-top:12px;animation: cinemaLineAnim 3.8s ease-in-out forwards;
            }}
            @keyframes cinemaFade {{
                0%,75%{{opacity:1;visibility:visible;}} 100%{{opacity:0;visibility:hidden;z-index:-1;}}
            }}
            @keyframes cinemaLogoAnim {{
                0%{{opacity:0;transform:scale(0.6);filter:blur(12px);}}
                20%{{opacity:1;transform:scale(1);filter:blur(0);}}
                50%{{transform:scale(1);}}
                55%{{transform:translate(-4px,2px) skew(3deg);filter:drop-shadow(-2px 0 #FF6B6B) drop-shadow(2px 0 #6C9CFF);opacity:0.85;}}
                58%{{transform:translate(3px,-2px) skew(-2deg);filter:drop-shadow(2px 0 #FF6B6B) drop-shadow(-2px 0 #5EEAA0);opacity:0.9;}}
                62%{{transform:translate(0,0) skew(0);filter:none;opacity:1;}}
                80%{{opacity:1;transform:scale(1);}}
                100%{{opacity:0;transform:scale(1.15);filter:blur(6px);}}
            }}
            @keyframes cinemaTextAnim {{
                0%,15%{{opacity:0;letter-spacing:0.6em;color:rgba(108,156,255,0);}}
                35%{{opacity:1;letter-spacing:0.3em;color:rgba(108,156,255,0.9);}}
                75%{{opacity:1;}}
                100%{{opacity:0;}}
            }}
            @keyframes cinemaLineAnim {{
                0%,15%{{width:0;opacity:0;}}
                40%{{width:200px;opacity:1;}}
                75%{{width:200px;opacity:1;}}
                100%{{width:0;opacity:0;}}
            }}
            </style>
            <div class="cinema-overlay">
                <img src="data:image/png;base64,{logo_b64}" class="cinema-logo" />
                <div class="cinema-text">HALLAON</div>
                <div class="cinema-line"></div>
            </div>
            """, unsafe_allow_html=True)

    logo_html = f'<div class="login-logo-container"><img src="data:image/png;base64,{logo_b64}" class="login-logo-img" alt="HALLAON"/></div>' if logo_b64 else '<div style="font-size:56px;text-align:center;margin-bottom:16px;">🏛️</div>'

    st.markdown(f"""
    <div style="display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:72vh;text-align:center;">
        {logo_html}
        <h1 style="font-size:32px;font-weight:900;margin:0 0 2px 0;letter-spacing:0.08em;text-align:center;">HALLAON</h1>
        <p style="color:#6B7B8D;font-size:12px;margin:0 0 40px 0;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;text-align:center;">WORKSPACE · JEJU</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<p style='text-align:center;color:#9BAABB;font-size:13px;font-weight:600;margin-bottom:16px;'>팀 계정으로 로그인</p>", unsafe_allow_html=True)
            user_id = st.text_input("이름", placeholder="이름을 입력하세요")
            user_pw = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
            submit = st.form_submit_button("로그인", type="primary", use_container_width=True)
            if submit:
                if not user_id or not user_pw: st.warning("이름과 비밀번호를 모두 입력해주세요.")
                else:
                    users_df = st.session_state.users_df
                    user_row = users_df[users_df["이름"] == user_id]
                    if user_row.empty: st.error("등록되지 않은 이름입니다.")
                    else:
                        if user_pw == str(user_row.iloc[0]["비밀번호"]):
                            st.session_state.role = str(user_row.iloc[0]["권한"])
                            st.session_state.username = user_id
                            st.rerun()
                        else: st.error("비밀번호가 일치하지 않습니다.")
    st.stop()

def can_edit(): return st.session_state.get("role") == "edit"

# =========================
# INIT
# =========================
if "users_df" not in st.session_state:
    st.session_state.users_df = normalize_users_df(load_gsheet_to_df(WORKSHEET_USERS))
auth_gate()

required_dfs = ["tasks_df", "agenda_df", "meetings_df", "decisions_df", "schedules_df"]
if any(df not in st.session_state for df in required_dfs):
    with st.spinner("HALLAON 데이터를 불러오는 중..."):
        init_data()

tasks_df = st.session_state.tasks_df.copy()
agenda_df = st.session_state.agenda_df.copy()
meetings_df = st.session_state.meetings_df.copy()
decisions_df = st.session_state.decisions_df.copy()
schedules_df = st.session_state.schedules_df.copy()

# =========================
# Sidebar
# =========================
with st.sidebar:
    logo_b64_sidebar = ""
    try:
        for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), LOGO_IMAGE_PATH), LOGO_IMAGE_PATH]:
            if os.path.exists(p):
                logo_b64_sidebar = get_base64_of_bin_file(p); break
    except: pass
    
    logo_img_tag = f"<img src='data:image/png;base64,{logo_b64_sidebar}' class='sidebar-logo'/>" if logo_b64_sidebar else "🏛️"
    
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
        {logo_img_tag}
        <div>
            <div style="font-size:16px;font-weight:900;letter-spacing:0.06em;">HALLAON</div>
            <div style="font-size:9px;color:#6B7B8D;font-weight:700;letter-spacing:0.1em;">WORKSPACE</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<span class='role-badge'>👤 {st.session_state.get('username','')} · {'편집' if can_edit() else '조회'}</span>", unsafe_allow_html=True)
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if st.button("🔄 새로고침 / 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.caption("WORKSPACE")
    menu = st.radio("메뉴", [
        "🏠 홈 · 가이드", "📋 업무 및 WBS", "📊 간트 차트", "📅 캘린더",
        "📈 대시보드", "🗂️ 안건", "⚖️ 의사결정", "📄 문서", "🤖 작업 전송"
    ], label_visibility="collapsed")
    
    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.caption("ACCOUNT")
    with st.expander("🔑 비밀번호 변경"):
        with st.form("pw_change"):
            new_pw = st.text_input("새 비밀번호", type="password")
            new_pw2 = st.text_input("비밀번호 확인", type="password")
            if st.form_submit_button("변경", type="primary", use_container_width=True):
                if not new_pw or new_pw != new_pw2: st.error("비밀번호를 확인해주세요.")
                else:
                    udf = st.session_state.users_df
                    idx = udf.index[udf["이름"] == st.session_state.username].tolist()[0]
                    udf.at[idx, "비밀번호"] = new_pw
                    st.session_state.users_df = udf
                    save_df_to_gsheet(udf, WORKSHEET_USERS)
                    st.success("변경 완료")

# =========================
# 🏠 홈 · 가이드 (FULL MANUAL)
# =========================
if menu == "🏠 홈 · 가이드":
    st.markdown("""
    <div style="background:linear-gradient(135deg,rgba(108,156,255,0.08),rgba(94,234,160,0.04),transparent);
                padding:36px 32px;border-radius:24px;border:1px solid rgba(140,170,220,0.07);margin-bottom:28px;">
        <h1 style="font-size:30px;font-weight:900;margin:0 0 8px 0;">
            <span style="color:#6C9CFF;">HALLAON</span> Workspace
        </h1>
        <p style="color:#9BAABB;font-size:14px;line-height:1.8;margin:0;max-width:720px;">
            탐라영재관 자율회 한라온의 <b style="color:#E8EDF5;">데이터 기반 의사결정 · 일정 관리 · 협업 플랫폼</b>입니다.<br>
            아래 가이드를 참고하여 각 기능을 활용하세요.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # === SECTION: 업무 및 WBS ===
    with st.expander("📋 업무 및 WBS — 작업 분할 구조도", expanded=True):
        st.markdown("""
        **WBS(Work Breakdown Structure)** 란 프로젝트 전체를 작은 업무 단위로 **계층적으로 분해**하는 체계입니다.
        
        **WBS 코드 체계**
        - 대분류.중분류.소분류 형태로 부여합니다 (예: `1.0`, `1.1`, `1.1.1`)
        - **절대 중복 불가** — 각 업무에 고유한 코드를 부여해야 합니다
        - 코드 예시: `1.0 기획`, `1.1 요구사항 분석`, `1.2 기획서 작성`, `2.0 설계`, `2.1 UI 설계`...
        
        **선행 업무**
        - 해당 업무를 시작하기 전에 반드시 완료되어야 하는 업무의 WBS 코드를 입력합니다
        - 여러 개일 경우 쉼표(`,`)로 구분합니다 (예: `1.1, 1.2`)
        - 선행 업무가 없으면 비워둡니다
        
        **PERT 시간 예측**
        - **낙관적 시간(O)**: 모든 것이 순조로울 때 걸리는 최소 시간(일)
        - **가능성 높은 시간(M)**: 가장 현실적으로 걸릴 시간(일)
        - **비관적 시간(P)**: 문제가 많이 발생했을 때 걸리는 최대 시간(일)
        - **기대 시간(TE)** = (O + 4×M + P) ÷ 6 → 자동 계산됩니다
        - TE 값이 업무의 기간(종료일 - 시작일)으로 자동 설정됩니다
        
        **상태값**: `시작 전` → `대기` → `진행 중` → `작업 중` → `막힘`(블로커 발생) → `완료`
        """)

    # === SECTION: 간트 차트 ===
    with st.expander("📊 간트 차트 — CPM 핵심 경로", expanded=False):
        st.markdown("""
        **CPM(Critical Path Method)** 알고리즘이 선행 업무 관계를 분석하여 **핵심 경로**를 자동 식별합니다.
        
        - **붉은 막대(Critical)**: 이 업무가 지연되면 **프로젝트 전체 일정이 밀립니다**
        - **파란 세로선**: 오늘 날짜를 나타냅니다
        - **팀 필터**: 특정 팀의 업무만 필터링하여 확인 가능합니다
        - **완료 업무 숨기기**: 토글로 완료된 업무를 숨깁니다
        
        차트 위에 마우스를 올리면 업무명과 일정 상세를 확인할 수 있습니다.
        """)

    # === SECTION: 캘린더 ===
    with st.expander("📅 캘린더 — 종합 일정", expanded=False):
        st.markdown("""
        업무·안건·회의·정기 일정을 **하나의 달력**에서 확인합니다.
        
        - **토글 필터**: 업무, 안건, 회의, 정기 일정을 각각 켜고 끌 수 있습니다
        - **정기 일정 등록**: 반복되는 회의나 마감 등을 등록할 수 있습니다
        - **뷰 전환**: 월간 / 주간 / 목록 뷰를 선택할 수 있습니다
        - **색상 구분**: 업무(팀 색상), 안건(분홍), 회의(초록), 정기일정(노랑)으로 구분됩니다
        """)

    # === SECTION: 대시보드 ===
    with st.expander("📈 대시보드 — 프로젝트 현황", expanded=False):
        st.markdown("""
        프로젝트의 **전체 진행 상황**을 요약된 지표와 차트로 확인합니다.
        
        - **전체 지표**: 총 태스크 수, 진행 중, 막힘, 완료 건수
        - **완료율 진행바**: 프로젝트 전체 완료 퍼센트
        - **팀별 현황**: 각 팀이 담당한 업무의 상태 분포
        - **마감 임박 업무**: 종료일이 7일 이내인 업무 목록
        - **상태별 분포 차트**: 도넛 차트로 전체 상태 비율 확인
        - **담당자별 태스크 차트**: 담당자 상위 10명의 업무 분포 (너무 많아도 깔끔하게 표시)
        """)

    # === SECTION: 안건 ===
    with st.expander("🗂️ 안건 — 안건 등록 · 추적", expanded=False):
        st.markdown("""
        팀에서 논의해야 할 **안건(이슈, 제안, 보고사항)** 을 등록하고 상태를 추적합니다.
        
        - **안건 추가**: 안건명, 팀, 입안자, 상태, 입안일을 입력합니다
        - **검색 · 필터**: 안건명 검색, 팀별·상태별 필터링이 가능합니다
        - **수정 · 삭제**: 데이터 편집기에서 직접 수정하고 저장합니다
        - **상태값**: `시작 전` → `진행 중` → `완료` / `보류`
        """)

    # === SECTION: 의사결정 ===
    with st.expander("⚖️ 의사결정 — 가중치 평가 모델", expanded=False):
        st.markdown("""
        **Weighted Scoring Model**을 사용하여 주관을 배제한 데이터 기반 의사결정을 합니다.
        
        1. 의사결정 대상 안건을 선택합니다
        2. **평가 기준**을 정의하고 **가중치(%)**를 부여합니다 (합계 = 100%)
        3. **비교 대안**을 입력합니다 (최소 2개)
        4. 각 대안에 대해 기준별로 **1~10점 평가**합니다
        5. 알고리즘이 **가중 합산 점수**를 계산하여 최적 대안을 추천합니다
        """)

    # === SECTION: 문서 ===
    with st.expander("📄 문서 — 회의록 · 팀 문서", expanded=False):
        st.markdown("""
        **회의록과 팀 문서**를 작성하고 관리합니다.
        
        - **Markdown 문법** 지원: 제목(`#`), 굵게(`**`), 목록(`-`), 코드블록 등
        - **업무 링크**: 관련 업무의 WBS 코드를 연결할 수 있습니다
        - **안건 링크**: 관련 안건을 연결할 수 있습니다
        - **분류(폴더)**: 전체 회의, PM, CD, FS, DM, OPS별로 분류합니다
        - **수정 · 삭제**: 작성 후 언제든 수정하거나 삭제할 수 있습니다
        """)

    # === SECTION: 작업 전송 ===
    with st.expander("🤖 작업 전송 — 디스코드 알림", expanded=False):
        st.markdown("""
        새로 등록된 업무와 안건을 **디스코드 채널**로 알립니다.
        
        - **미전송 목록**: 아직 디스코드에 전송되지 않은 업무/안건이 표시됩니다
        - **선택 전송**: 체크박스로 전송할 항목을 선택합니다
        - **전송 완료 표시**: 한 번 전송된 항목은 자동으로 '전송됨'으로 표시되어 중복 전송을 방지합니다
        - **편집 권한 필요**: 조회 권한에서는 전송이 불가합니다
        """)

# =========================
# 📋 업무 및 WBS
# =========================
elif menu == "📋 업무 및 WBS":
    st.markdown("<h2 style='font-size:24px;margin:0;'>📋 업무 및 WBS</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>WBS + PERT 기반 일정 관리</p>", unsafe_allow_html=True)
    if not can_edit(): st.info("조회 권한입니다.")

    with st.expander("➕ 새 업무 추가", expanded=False):
        with st.form("add_wbs", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                WBS_코드 = st.text_input("WBS 코드", placeholder="예: 1.1, 2.3.1")
                업무명 = st.text_input("업무명", placeholder="업무명을 입력하세요")
                담당자 = st.text_input("담당자", placeholder="담당자 이름")
                팀 = st.multiselect("팀", TEAM_OPTIONS)
            with c2:
                선행_업무 = st.text_input("선행 업무 WBS 코드", placeholder="없으면 비워두세요")
                상태 = st.selectbox("상태", TASK_STATUS_OPTIONS)
                st.markdown("**PERT 소요 시간 (일)**")
                p1, p2, p3 = st.columns(3)
                with p1: O = st.number_input("낙관적(O)", min_value=0, step=1, value=0)
                with p2: M = st.number_input("보통(M)", min_value=0, step=1, value=0)
                with p3: P = st.number_input("비관적(P)", min_value=0, step=1, value=0)
            add_btn = st.form_submit_button("➕ 업무 추가", type="primary", disabled=not can_edit())

        if add_btn and 업무명:
            existing = tasks_df["WBS_코드"].astype(str).str.strip().tolist()
            if WBS_코드.strip() and WBS_코드.strip() in existing:
                st.error(f"WBS 코드 '{WBS_코드}'가 이미 존재합니다.")
            else:
                TE = round((O + 4*M + P) / 6, 1) if (O or M or P) else 0
                start_d = date.today()
                if 선행_업무.strip():
                    pr = tasks_df[tasks_df["WBS_코드"].astype(str).str.strip() == 선행_업무.strip()]
                    if not pr.empty:
                        pe = pd.to_datetime(pr.iloc[0]["종료일"], errors="coerce")
                        if pd.notna(pe): start_d = max(start_d, pe.date() + timedelta(days=1))
                end_d = start_d + timedelta(days=max(int(TE), 1))
                new_row = {
                    "id": str(uuid.uuid4()), "업무명": 업무명, "담당자": 담당자 or "미정",
                    "팀": ", ".join(팀) or "미지정", "상태": 상태,
                    "시작일": safe_date_str(start_d), "종료일": safe_date_str(end_d),
                    "sent": "False", "WBS_코드": WBS_코드, "선행_업무": 선행_업무,
                    "낙관적_시간(O)": O, "가능성_높은_시간(M)": M, "비관적_시간(P)": P, "기대_시간(TE)": TE
                }
                tasks_df = pd.concat([st.session_state.tasks_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.tasks_df = tasks_df
                save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
                st.success(f"'{업무명}' 추가 완료"); st.rerun()

    todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)]
    done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)]
    blocked_df = tasks_df[tasks_df["상태"].str.contains("막힘", na=False)]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("전체", len(tasks_df)); m2.metric("진행 중", len(todo_df)-len(blocked_df))
    m3.metric("막힘", len(blocked_df)); m4.metric("완료", len(done_df))

    disp = ["WBS_코드","선행_업무","업무명","담당자","팀","상태","기대_시간(TE)","시작일","종료일"]
    with st.expander(f"⏳ 진행 중 ({len(todo_df)})", expanded=True):
        if todo_df.empty: st.caption("없음")
        else: st.dataframe(todo_df[disp], use_container_width=True, hide_index=True)
    with st.expander(f"✅ 완료 ({len(done_df)})", expanded=False):
        if done_df.empty: st.caption("없음")
        else: st.dataframe(done_df[disp], use_container_width=True, hide_index=True)

    st.markdown("### ✏️ 업무 수정 / 삭제")
    e = tasks_df.copy(); e.insert(0, "선택", False)
    e["시작일"] = pd.to_datetime(e["시작일"]).dt.date; e["종료일"] = pd.to_datetime(e["종료일"]).dt.date
    edited = st.data_editor(
        e[["선택","WBS_코드","선행_업무","업무명","담당자","팀","상태","시작일","종료일","기대_시간(TE)"]],
        use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택",width="small"), "상태": st.column_config.SelectboxColumn("상태",options=TASK_STATUS_OPTIONS)}
    )
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 저장", type="primary", disabled=not can_edit(), use_container_width=True, key="save_task"):
            base = tasks_df.copy().reset_index(drop=True)
            edited["시작일"] = edited["시작일"].apply(safe_date_str); edited["종료일"] = edited["종료일"].apply(safe_date_str)
            for col in ["WBS_코드","선행_업무","업무명","담당자","팀","상태","시작일","종료일","기대_시간(TE)"]:
                if col in edited.columns: base[col] = edited[col]
            st.session_state.tasks_df = base; save_df_to_gsheet(base, WORKSHEET_TASKS)
            st.success("저장 완료"); st.rerun()
    with c2:
        if st.button("🗑️ 선택 삭제", disabled=not can_edit(), use_container_width=True, key="del_task"):
            idx = edited.index[edited["선택"]==True].tolist()
            if not idx: st.warning("선택하세요.")
            else:
                keep = tasks_df.drop(index=idx).reset_index(drop=True)
                st.session_state.tasks_df = keep; save_df_to_gsheet(keep, WORKSHEET_TASKS)
                st.success(f"{len(idx)}개 삭제"); st.rerun()

# =========================
# 📊 간트 차트
# =========================
elif menu == "📊 간트 차트":
    st.markdown("<h2 style='font-size:24px;margin:0;'>📊 간트 차트 — CPM</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>핵심 경로를 붉은색으로 강조합니다</p>", unsafe_allow_html=True)
    fc1, fc2 = st.columns([1, 1])
    with fc1: hide_done = st.toggle("완료 숨기기", value=True)
    with fc2: team_filter = st.selectbox("팀 필터", ["전체"] + TEAM_OPTIONS, key="gantt_tf", label_visibility="collapsed")
    gdf = tasks_df.copy()
    if hide_done: gdf = gdf[~gdf["상태"].str.contains("완료", na=False)]
    if team_filter != "전체": gdf = gdf[gdf["팀"].str.contains(team_filter, na=False)]
    gdf["_s"] = gdf["WBS_코드"].astype(str).str.strip()
    gdf = gdf.sort_values("_s").drop(columns=["_s"])
    components.html(render_gantt(gdf), height=max(550, len(gdf)*50 + 180), scrolling=True)

# =========================
# 📅 캘린더 (with toggles + recurring)
# =========================
elif menu == "📅 캘린더":
    st.markdown("<h2 style='font-size:24px;margin:0;'>📅 종합 캘린더</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 16px;'>모든 일정을 통합하여 확인하세요</p>", unsafe_allow_html=True)

    # Toggle filters
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1: show_tasks = st.toggle("📋 업무", value=True)
    with tc2: show_agendas = st.toggle("🗂️ 안건", value=True)
    with tc3: show_meetings = st.toggle("📄 회의", value=True)
    with tc4: show_schedules = st.toggle("📆 정기일정", value=True)

    # Add recurring schedule
    if can_edit():
        with st.expander("➕ 정기 일정 등록", expanded=False):
            with st.form("add_schedule", clear_on_submit=True):
                sc1, sc2, sc3 = st.columns(3)
                with sc1: sch_name = st.text_input("일정 이름", placeholder="예: 주간 회의")
                with sc2: sch_date = st.date_input("시작 날짜")
                with sc3: sch_end = st.date_input("종료 날짜 (반복일 경우 반복 종료)")
                sc4, sc5 = st.columns(2)
                with sc4: sch_repeat = st.selectbox("반복", ["없음", "매주", "격주", "매월"])
                with sc5: sch_color = st.selectbox("색상", ["노랑", "파랑", "초록", "분홍", "보라"])
                color_map = {"노랑": "#FFCB57", "파랑": "#6C9CFF", "초록": "#5EEAA0", "분홍": "#FF7EB3", "보라": "#B18CFF"}
                if st.form_submit_button("등록", type="primary"):
                    new_sch = {"id": str(uuid.uuid4()), "이름": sch_name, "날짜": safe_date_str(sch_date), "종료일": safe_date_str(sch_end), "반복": sch_repeat, "색상": color_map.get(sch_color, "#FFCB57"), "활성": "True"}
                    schedules_df = pd.concat([st.session_state.schedules_df, pd.DataFrame([new_sch])], ignore_index=True)
                    st.session_state.schedules_df = schedules_df
                    save_df_to_gsheet(schedules_df, WORKSHEET_SCHEDULES)
                    st.success("등록 완료"); st.rerun()

    cal_events = []
    if show_tasks:
        for _, r in tasks_df.iterrows():
            if r["시작일"] and r["종료일"]:
                c = TEAM_COLORS.get(str(r["팀"]).split(",")[0].strip(), "#8899AA")
                end_d = (pd.to_datetime(r["종료일"]) + timedelta(days=1)).strftime("%Y-%m-%d")
                rc, gc, bc = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
                cal_events.append({"title": f"📋 {r['업무명']}", "start": r["시작일"], "end": end_d,
                    "backgroundColor": f"rgba({rc},{gc},{bc},0.15)", "borderColor": c, "textColor": c})
    if show_agendas:
        for _, r in agenda_df.iterrows():
            if r["입안일"]:
                cal_events.append({"title": f"🗂️ {r['안건명']}", "start": r["입안일"],
                    "backgroundColor": "rgba(255,126,179,0.15)", "borderColor": "#FF7EB3", "textColor": "#FF7EB3", "allDay": True})
    if show_meetings:
        for _, r in meetings_df.iterrows():
            if r["회의일자"]:
                cal_events.append({"title": f"📄 {r['제목']}", "start": r["회의일자"],
                    "backgroundColor": "rgba(94,234,160,0.15)", "borderColor": "#5EEAA0", "textColor": "#5EEAA0", "allDay": True})
    if show_schedules:
        for _, r in schedules_df.iterrows():
            if str(r.get("활성","")) != "True": continue
            c = str(r.get("색상","#FFCB57"))
            s_date = pd.to_datetime(r["날짜"], errors="coerce")
            e_date = pd.to_datetime(r.get("종료일",""), errors="coerce")
            repeat = str(r.get("반복","없음"))
            if pd.isna(s_date): continue
            if repeat == "없음":
                end_str = (e_date + timedelta(days=1)).strftime("%Y-%m-%d") if pd.notna(e_date) else s_date.strftime("%Y-%m-%d")
                rc, gc, bc = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
                cal_events.append({"title": f"📆 {r['이름']}", "start": s_date.strftime("%Y-%m-%d"), "end": end_str,
                    "backgroundColor": f"rgba({rc},{gc},{bc},0.15)", "borderColor": c, "textColor": c, "allDay": True})
            else:
                delta = timedelta(weeks=1) if repeat == "매주" else timedelta(weeks=2) if repeat == "격주" else timedelta(days=30)
                end_limit = e_date if pd.notna(e_date) else s_date + timedelta(days=180)
                current = s_date
                rc, gc, bc = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
                while current <= end_limit:
                    cal_events.append({"title": f"🔄 {r['이름']}", "start": current.strftime("%Y-%m-%d"),
                        "backgroundColor": f"rgba({rc},{gc},{bc},0.15)", "borderColor": c, "textColor": c, "allDay": True})
                    current += delta

    cal_opts = {"headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,listWeek"}, "initialView": "dayGridMonth", "dayMaxEvents": 3}
    cal_css = """
        .fc{font-family:'Inter',sans-serif;} .fc-theme-standard td,.fc-theme-standard th{border-color:rgba(140,170,220,0.08) !important;}
        .fc-toolbar-title{font-weight:900 !important;color:#E8EDF5 !important;font-size:18px !important;}
        .fc-button{background:#1A2335 !important;border-color:rgba(140,170,220,0.15) !important;color:#9BAABB !important;border-radius:8px !important;font-weight:600 !important;}
        .fc-button:hover{background:#26334D !important;color:#E8EDF5 !important;}
        .fc-button-active{background:#6C9CFF !important;color:#0B0F14 !important;border-color:#6C9CFF !important;}
        .fc-day-today{background:rgba(108,156,255,0.06) !important;}
        .fc-event{border-radius:5px;padding:2px 5px;font-size:11px;font-weight:600;border-width:1px !important;}
        .fc-daygrid-day-number{color:#9BAABB !important;font-weight:600;font-size:13px;}
        .fc-col-header-cell-cushion{color:#6B7B8D !important;font-weight:700;font-size:12px;text-transform:uppercase;}
    """
    st.markdown("<div style='background:#101621;padding:16px;border-radius:20px;border:1px solid rgba(140,170,220,0.1);overflow:hidden;'>", unsafe_allow_html=True)
    calendar(events=cal_events, options=cal_opts, custom_css=cal_css, key="main_cal")
    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 📈 대시보드 (Enhanced — monday.com style)
# =========================
elif menu == "📈 대시보드":
    st.markdown("<h2 style='font-size:24px;margin:0;'>📈 종합 대시보드</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>프로젝트 현황 종합 리포트</p>", unsafe_allow_html=True)

    if tasks_df.empty:
        st.info("업무 데이터가 없습니다.")
    else:
        udf = tasks_df.drop_duplicates(subset=['업무명'])
        total = len(udf)
        progress = len(udf[udf["상태"].str.contains("진행|작업", na=False)])
        blocked = len(udf[udf["상태"].str.contains("막힘", na=False)])
        done = len(udf[udf["상태"].str.contains("완료", na=False)])
        pct = int(done / total * 100) if total > 0 else 0

        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("전체 태스크", total); m2.metric("진행 중", progress); m3.metric("막힘", blocked); m4.metric("완료", done)

        # Progress bar
        st.markdown(f"""
        <div style="margin:16px 0 24px;padding:16px 20px;background:#151C2A;border-radius:16px;border:1px solid rgba(140,170,220,0.1);">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-size:13px;font-weight:700;color:#E8EDF5;">프로젝트 완료율</span>
                <span style="font-size:13px;font-weight:800;color:#5EEAA0;">{pct}%</span>
            </div>
            <div style="height:10px;background:rgba(140,170,220,0.08);border-radius:999px;overflow:hidden;">
                <div style="height:100%;width:{pct}%;background:linear-gradient(90deg,#5EEAA0,#3DD68C);border-radius:999px;transition:width 0.5s;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Team breakdown
        st.markdown("##### 팀별 업무 현황")
        team_cols = st.columns(len(TEAM_OPTIONS))
        for i, team in enumerate(TEAM_OPTIONS):
            team_tasks = udf[udf["팀"].str.contains(team, na=False)]
            t_total = len(team_tasks)
            t_done = len(team_tasks[team_tasks["상태"].str.contains("완료", na=False)])
            t_pct = int(t_done / t_total * 100) if t_total > 0 else 0
            c = TEAM_COLORS[team]
            with team_cols[i]:
                st.markdown(f"""
                <div style="background:#151C2A;border-radius:14px;padding:16px;border:1px solid rgba(140,170,220,0.08);text-align:center;">
                    <div style="font-size:11px;font-weight:700;color:{c};text-transform:uppercase;letter-spacing:0.06em;">{team}</div>
                    <div style="font-size:24px;font-weight:900;color:#E8EDF5;margin:6px 0;">{t_total}</div>
                    <div style="height:4px;background:rgba(140,170,220,0.08);border-radius:999px;overflow:hidden;margin:8px 0;">
                        <div style="height:100%;width:{t_pct}%;background:{c};border-radius:999px;"></div>
                    </div>
                    <div style="font-size:10px;color:#9BAABB;">{t_done}건 완료 ({t_pct}%)</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # Deadline approaching
        st.markdown("##### 🔥 마감 임박 업무 (7일 이내)")
        today = date.today()
        udf_active = udf[~udf["상태"].str.contains("완료", na=False)].copy()
        udf_active["종료일_dt"] = pd.to_datetime(udf_active["종료일"], errors="coerce")
        deadline_soon = udf_active[(udf_active["종료일_dt"] - pd.Timestamp(today)).dt.days <= 7].copy()
        deadline_soon = deadline_soon.sort_values("종료일_dt")
        if deadline_soon.empty:
            st.caption("7일 이내 마감 업무 없음")
        else:
            st.dataframe(deadline_soon[["WBS_코드","업무명","담당자","팀","상태","종료일"]].head(10), use_container_width=True, hide_index=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # Charts
        chart_c1, chart_c2 = st.columns(2)
        with chart_c1:
            st.markdown("##### 상태별 분포")
            s = udf["상태"].value_counts().reset_index(); s.columns = ["상태","개수"]
            fig1 = px.pie(s, names="상태", values="개수", hole=0.6, color="상태", color_discrete_map=STATUS_COLORS)
            fig1.update_layout(template="plotly_dark", height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10), showlegend=True, legend=dict(font=dict(size=11)))
            st.plotly_chart(fig1, use_container_width=True)
        with chart_c2:
            st.markdown("##### 담당자별 태스크 (상위 10)")
            a = udf["담당자"].value_counts().head(10).reset_index(); a.columns = ["담당자","개수"]
            fig2 = px.bar(a, y="담당자", x="개수", orientation='h', text_auto=True, color_discrete_sequence=["#6C9CFF"])
            fig2.update_layout(template="plotly_dark", height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=10,b=10,l=10,r=10), bargap=0.3, yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# 🗂️ 안건
# =========================
elif menu == "🗂️ 안건":
    st.markdown("<h2 style='font-size:24px;margin:0;'>🗂️ 안건 관리</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>팀 안건을 등록하고 추적하세요</p>", unsafe_allow_html=True)
    if not can_edit(): st.info("조회 권한입니다.")

    with st.expander("➕ 새 안건 추가", expanded=False):
        with st.form("add_agenda", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1: 안건명 = st.text_input("안건명", placeholder="안건명"); 팀 = st.multiselect("팀", TEAM_OPTIONS)
            with c2: 입안자 = st.text_input("입안자", placeholder="입안자"); 입안일 = st.date_input("입안일")
            상태 = st.selectbox("상태", AGENDA_STATUS_OPTIONS)
            if st.form_submit_button("➕ 추가", type="primary", disabled=not can_edit()):
                if 안건명.strip():
                    new = {"id": str(uuid.uuid4()), "안건명": 안건명, "입안자": 입안자 or "미정", "팀": ", ".join(팀) or "미지정", "상태": 상태, "입안일": safe_date_str(입안일), "sent": "False"}
                    agenda_df = pd.concat([agenda_df, pd.DataFrame([new])], ignore_index=True)
                    st.session_state.agenda_df = agenda_df; save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
                    st.success("추가 완료"); st.rerun()

    am1, am2, am3, am4 = st.columns(4)
    am1.metric("전체", len(agenda_df)); am2.metric("진행 중", len(agenda_df[agenda_df["상태"]=="진행 중"]))
    am3.metric("보류", len(agenda_df[agenda_df["상태"]=="보류"])); am4.metric("완료", len(agenda_df[agenda_df["상태"]=="완료"]))

    # Search + filters — ALIGNED HEIGHT FIX
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1: search_q = st.text_input("안건 검색", placeholder="안건명으로 검색...", label_visibility="collapsed")
    with fc2: team_f = st.selectbox("팀 필터", ["전체"] + TEAM_OPTIONS, label_visibility="collapsed")
    with fc3: status_f = st.selectbox("상태 필터", ["전체"] + AGENDA_STATUS_OPTIONS, label_visibility="collapsed")

    f = agenda_df.copy()
    if search_q: f = f[f["안건명"].str.contains(search_q, case=False, na=False)]
    if team_f != "전체": f = f[f["팀"].str.contains(team_f, na=False)]
    if status_f != "전체": f = f[f["상태"] == status_f]
    f = f.sort_values("입안일", ascending=False)
    st.dataframe(f[["안건명","입안자","팀","상태","입안일"]], use_container_width=True, hide_index=True)

    st.markdown("### ✏️ 안건 수정 / 삭제")
    ea = agenda_df.copy(); ea.insert(0, "선택", False)
    ea["입안일"] = pd.to_datetime(ea["입안일"]).dt.date
    edited_a = st.data_editor(ea[["선택","안건명","입안자","팀","상태","입안일"]], use_container_width=True, hide_index=True, disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택",width="small"), "상태": st.column_config.SelectboxColumn("상태",options=AGENDA_STATUS_OPTIONS)})
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 저장", type="primary", disabled=not can_edit(), use_container_width=True, key="save_ag"):
            base = agenda_df.copy().reset_index(drop=True)
            edited_a["입안일"] = edited_a["입안일"].apply(safe_date_str)
            base[["안건명","입안자","팀","상태","입안일"]] = edited_a[["안건명","입안자","팀","상태","입안일"]]
            st.session_state.agenda_df = base; save_df_to_gsheet(base, WORKSHEET_AGENDA); st.success("저장 완료"); st.rerun()
    with c2:
        if st.button("🗑️ 삭제", disabled=not can_edit(), use_container_width=True, key="del_ag"):
            idx = edited_a.index[edited_a["선택"]==True].tolist()
            if idx:
                keep = agenda_df.drop(index=idx).reset_index(drop=True)
                st.session_state.agenda_df = keep; save_df_to_gsheet(keep, WORKSHEET_AGENDA); st.success(f"{len(idx)}개 삭제"); st.rerun()

# =========================
# ⚖️ 의사결정
# =========================
elif menu == "⚖️ 의사결정":
    st.markdown("<h2 style='font-size:24px;margin:0;'>⚖️ 의사결정 모델</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>가중치 평가로 최적 대안 산출</p>", unsafe_allow_html=True)
    if not can_edit(): st.info("조회 권한입니다.")
    if not decisions_df.empty:
        with st.expander(f"📋 기존 기록 ({len(decisions_df)}건)", expanded=False):
            st.dataframe(decisions_df[["안건명","평가기준","대안","최종점수","작성일"]], use_container_width=True, hide_index=True)

    if "criteria_count" not in st.session_state: st.session_state.criteria_count = 3
    if "alt_count" not in st.session_state: st.session_state.alt_count = 2
    active_ag = agenda_df[agenda_df["상태"]!="완료"]["안건명"].tolist()

    with st.form("decision"):
        st.markdown("#### 1. 기준 설정")
        sel_ag = st.selectbox("대상 안건", active_ag if active_ag else ["등록된 안건 없음"])
        c1, c2 = st.columns(2)
        criteria = []; weights = []
        with c1:
            st.markdown("**평가 기준 · 가중치**")
            for i in range(st.session_state.criteria_count):
                cc, cw = st.columns([7, 3])
                with cc: cr = st.text_input(f"기준 {i+1}", key=f"cr_{i}")
                with cw: wt = st.number_input("가중치(%)", 0, 100, round(100//st.session_state.criteria_count), key=f"wt_{i}")
                criteria.append(cr); weights.append(wt)
        alts = []
        with c2:
            st.markdown("**비교 대안**")
            for i in range(st.session_state.alt_count):
                al = st.text_input(f"대안 {i+1}", key=f"alt_{i}")
                alts.append(al)
        st.markdown("---"); st.markdown("#### 2. 평가 (1~10)")
        scores = {}
        vc = [c for c in criteria if c.strip()]; va = [a for a in alts if a.strip()]
        for alt in va:
            scores[alt] = []
            st.markdown(f"**{alt}**")
            if vc:
                cols = st.columns(len(vc))
                for j, cr in enumerate(vc):
                    with cols[j]: scores[alt].append(st.slider(cr, 1, 10, 5, key=f"s_{alt}_{j}"))
        submitted = st.form_submit_button("🧠 실행", type="primary", disabled=not can_edit())
    if submitted:
        vw = weights[:len(vc)]
        if sum(vw) != 100: st.error(f"가중치 합 = {sum(vw)}% (100% 필요)")
        elif not va or not vc: st.warning("대안 2개+, 기준 1개+ 필요")
        else:
            res = []
            for alt, sl in scores.items():
                total = sum(s*w/100 for s, w in zip(sl, vw))
                res.append({"대안": alt, "점수": round(total, 2)})
            rdf = pd.DataFrame(res).sort_values("점수", ascending=False)
            best = rdf.iloc[0]
            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(94,234,160,0.1),rgba(108,156,255,0.05));border:1px solid rgba(94,234,160,0.25);border-radius:16px;padding:24px;">
                <div style="font-size:12px;font-weight:700;color:#5EEAA0;text-transform:uppercase;">추천 결과</div>
                <div style="font-size:24px;font-weight:900;">{escape(best['대안'])} ({best['점수']}점)</div>
            </div>
            """, unsafe_allow_html=True)
            fig = px.bar(rdf, x="대안", y="점수", text="점수", color="대안", color_discrete_sequence=["#6C9CFF","#FF7EB3","#5EEAA0","#FFCB57"])
            fig.update_layout(template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

# =========================
# 📄 문서 (Enhanced — links + images)
# =========================
elif menu == "📄 문서":
    st.markdown("<h2 style='font-size:24px;margin:0;'>📄 문서</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>회의록 · 팀 문서 작성 및 관리</p>", unsafe_allow_html=True)

    if "sel_mtg_id" not in st.session_state: st.session_state.sel_mtg_id = None
    if "is_edit_mtg" not in st.session_state: st.session_state.is_edit_mtg = False

    tc1, tc2, tc3 = st.columns([1, 1, 2])
    with tc1:
        if st.button("➕ 새 문서", use_container_width=True, disabled=not can_edit(), type="primary"):
            st.session_state.sel_mtg_id = "NEW"; st.session_state.is_edit_mtg = True; st.rerun()
    with tc2:
        if st.button("📋 전체 목록", use_container_width=True):
            st.session_state.sel_mtg_id = None; st.rerun()

    if st.session_state.sel_mtg_id is None:
        folders = ["전체 회의"] + TEAM_OPTIONS
        for folder in folders:
            fdf = meetings_df[meetings_df["분류"] == folder].sort_values("회의일자", ascending=False)
            if fdf.empty: continue
            with st.expander(f"📁 {folder} ({len(fdf)}건)", expanded=True):
                for _, r in fdf.iterrows():
                    ct, cd, ca, cb = st.columns([4, 1.5, 1.5, 1])
                    with ct: st.markdown(f"**{r['제목']}**")
                    with cd: st.caption(r['회의일자'])
                    with ca: st.caption(f"👤 {r['작성자']}")
                    with cb:
                        if st.button("열기", key=f"o_{r['id']}", use_container_width=True):
                            st.session_state.sel_mtg_id = r["id"]; st.session_state.is_edit_mtg = False; st.rerun()

    elif st.session_state.sel_mtg_id == "NEW":
        st.markdown("### ✨ 새 문서 작성")
        with st.form("new_doc"):
            f_title = st.text_input("제목", placeholder="문서 제목")
            c1, c2, c3 = st.columns(3)
            with c1: f_folder = st.selectbox("분류", ["전체 회의"] + TEAM_OPTIONS)
            with c2: f_date = st.date_input("날짜")
            with c3: f_author = st.text_input("작성자", value=st.session_state.get("username",""))

            # Linked tasks & agendas
            st.markdown("**📎 관련 항목 연결**")
            lc1, lc2 = st.columns(2)
            with lc1:
                task_options = tasks_df["업무명"].tolist() if not tasks_df.empty else []
                linked_tasks = st.multiselect("관련 업무 연결", task_options)
            with lc2:
                agenda_options = agenda_df["안건명"].tolist() if not agenda_df.empty else []
                linked_agendas = st.multiselect("관련 안건 연결", agenda_options)

            f_content = st.text_area("내용 (Markdown 지원)", height=450, placeholder="내용을 작성하세요...\n\n# 제목\n## 소제목\n- 항목 1\n- 항목 2\n**굵게**, *이탤릭*")

            bc1, bc2 = st.columns([1, 3])
            with bc1: save = st.form_submit_button("💾 저장", type="primary")
            with bc2: cancel = st.form_submit_button("취소")
            if save and f_title:
                new = {"id": str(uuid.uuid4()), "분류": f_folder, "회의일자": safe_date_str(f_date), "제목": f_title, "작성자": f_author, "내용": f_content, "linked_tasks": ",".join(linked_tasks), "linked_agendas": ",".join(linked_agendas)}
                meetings_df = pd.concat([meetings_df, pd.DataFrame([new])], ignore_index=True)
                st.session_state.meetings_df = meetings_df; save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                st.session_state.sel_mtg_id = new["id"]; st.session_state.is_edit_mtg = False; st.rerun()
            if cancel: st.session_state.sel_mtg_id = None; st.rerun()

    else:
        md = meetings_df[meetings_df["id"] == st.session_state.sel_mtg_id]
        if md.empty: st.error("문서를 찾을 수 없습니다.")
        else:
            mtg = md.iloc[0]
            if not st.session_state.is_edit_mtg:
                # View mode
                st.markdown(f"""
                <div style="background:#151C2A;border:1px solid rgba(140,170,220,0.1);border-radius:20px;padding:28px;margin-bottom:12px;">
                    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
                        <span style="padding:4px 12px;border-radius:999px;background:rgba(108,156,255,0.12);color:#6C9CFF;font-size:11px;font-weight:700;">📁 {escape(mtg['분류'])}</span>
                        <span style="padding:4px 12px;border-radius:999px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:11px;font-weight:600;">📅 {escape(mtg['회의일자'])}</span>
                        <span style="padding:4px 12px;border-radius:999px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:11px;font-weight:600;">👤 {escape(mtg['작성자'])}</span>
                    </div>
                    <h2 style="margin:0 0 16px 0;font-size:24px;">{escape(mtg['제목'])}</h2>
                """, unsafe_allow_html=True)

                # Show linked items
                lt = str(mtg.get("linked_tasks","")).strip()
                la = str(mtg.get("linked_agendas","")).strip()
                if lt or la:
                    links_html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;'>"
                    if lt:
                        for t in lt.split(","):
                            if t.strip(): links_html += f"<span style='padding:3px 10px;border-radius:999px;background:rgba(108,156,255,0.1);color:#6C9CFF;font-size:10px;font-weight:700;border:1px solid rgba(108,156,255,0.2);'>📋 {escape(t.strip())}</span>"
                    if la:
                        for a in la.split(","):
                            if a.strip(): links_html += f"<span style='padding:3px 10px;border-radius:999px;background:rgba(255,126,179,0.1);color:#FF7EB3;font-size:10px;font-weight:700;border:1px solid rgba(255,126,179,0.2);'>🗂️ {escape(a.strip())}</span>"
                    links_html += "</div>"
                    st.markdown(links_html, unsafe_allow_html=True)

                st.markdown(f"<div style='border-top:1px solid rgba(140,170,220,0.07);padding-top:16px;'></div></div>", unsafe_allow_html=True)
                st.markdown(mtg['내용'].replace('\n', '  \n'))

                act1, act2, act3 = st.columns([1, 1, 4])
                with act1:
                    if can_edit() and st.button("✏️ 수정", use_container_width=True):
                        st.session_state.is_edit_mtg = True; st.rerun()
                with act2:
                    if can_edit() and st.button("🗑️ 삭제", use_container_width=True):
                        keep = meetings_df[meetings_df["id"]!=mtg['id']].reset_index(drop=True)
                        st.session_state.meetings_df = keep; save_df_to_gsheet(keep, WORKSHEET_MEETINGS)
                        st.session_state.sel_mtg_id = None; st.rerun()
            else:
                # Edit mode
                st.markdown("### ✏️ 문서 수정")
                with st.form("edit_doc"):
                    f_title = st.text_input("제목", value=mtg['제목'])
                    c1, c2, c3 = st.columns(3)
                    with c1: f_folder = st.selectbox("분류", ["전체 회의"]+TEAM_OPTIONS, index=(["전체 회의"]+TEAM_OPTIONS).index(mtg['분류']) if mtg['분류'] in ["전체 회의"]+TEAM_OPTIONS else 0)
                    with c2: f_date = st.date_input("날짜", value=pd.to_datetime(mtg['회의일자']).date())
                    with c3: f_author = st.text_input("작성자", value=mtg['작성자'])

                    st.markdown("**📎 관련 항목**")
                    lc1, lc2 = st.columns(2)
                    existing_lt = [t.strip() for t in str(mtg.get("linked_tasks","")).split(",") if t.strip()]
                    existing_la = [a.strip() for a in str(mtg.get("linked_agendas","")).split(",") if a.strip()]
                    with lc1: linked_tasks = st.multiselect("관련 업무", tasks_df["업무명"].tolist() if not tasks_df.empty else [], default=[t for t in existing_lt if t in tasks_df["업무명"].tolist()])
                    with lc2: linked_agendas = st.multiselect("관련 안건", agenda_df["안건명"].tolist() if not agenda_df.empty else [], default=[a for a in existing_la if a in agenda_df["안건명"].tolist()])

                    f_content = st.text_area("내용", value=mtg['내용'], height=450)
                    bc1, bc2 = st.columns([1, 3])
                    with bc1:
                        if st.form_submit_button("💾 저장", type="primary"):
                            idx = meetings_df.index[meetings_df["id"]==mtg['id']].tolist()[0]
                            meetings_df.at[idx,'제목'] = f_title; meetings_df.at[idx,'분류'] = f_folder
                            meetings_df.at[idx,'회의일자'] = safe_date_str(f_date); meetings_df.at[idx,'작성자'] = f_author
                            meetings_df.at[idx,'내용'] = f_content
                            meetings_df.at[idx,'linked_tasks'] = ",".join(linked_tasks)
                            meetings_df.at[idx,'linked_agendas'] = ",".join(linked_agendas)
                            st.session_state.meetings_df = meetings_df; save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                            st.session_state.is_edit_mtg = False; st.rerun()
                    with bc2:
                        if st.form_submit_button("취소"): st.session_state.is_edit_mtg = False; st.rerun()

# =========================
# 🤖 작업 전송
# =========================
elif menu == "🤖 작업 전송":
    st.markdown("<h2 style='font-size:24px;margin:0;'>🤖 작업 전송</h2><p style='color:#9BAABB;font-size:13px;margin:4px 0 20px;'>미전송 업무 · 안건을 디스코드로 공유</p>", unsafe_allow_html=True)
    if not can_edit(): st.info("편집 권한이 필요합니다.")

    t1, t2 = st.tabs(["📋 업무 전송", "🗂️ 안건 전송"])
    with t1:
        ut = tasks_df[tasks_df["sent"].astype(str)!="True"].reset_index(drop=True)
        if ut.empty: st.info("미전송 업무 없음")
        else:
            vt = ut.copy(); vt.insert(0, "전송", False)
            pt = st.data_editor(vt[["전송","WBS_코드","업무명","담당자","팀","상태","시작일","종료일"]], use_container_width=True, hide_index=True, disabled=not can_edit(), column_config={"전송": st.column_config.CheckboxColumn("선택",width="small")})
            sel = pt.index[pt["전송"]==True].tolist()
            if st.button("🚀 전송", type="primary", disabled=(not can_edit() or not sel), use_container_width=True, key="send_t"):
                st_sel = ut.iloc[sel]
                fields = [{"name": f"🔹 {r['업무명']} ({r['팀']})", "value": f"👤 {r['담당자']}\n🏷️ {r['상태']}\n📅 {r['시작일']}→{r['종료일']}\nWBS: {r.get('WBS_코드','')}", "inline": False} for _, r in st_sel.iterrows()]
                ok, msg = send_discord(fields, "🔔 신규 업무", "HALLAON Bot", 7118079)
                if ok:
                    ids = set(st_sel["id"])
                    tasks_df["sent"] = tasks_df["id"].apply(lambda x: "True" if x in ids or str(tasks_df.loc[tasks_df["id"]==x,"sent"].iloc[0])=="True" else "False")
                    st.session_state.tasks_df = tasks_df; save_df_to_gsheet(tasks_df, WORKSHEET_TASKS)
                    st.success(msg); st.rerun()
                else: st.error(msg)

    with t2:
        ua = agenda_df[agenda_df["sent"].astype(str)!="True"].reset_index(drop=True)
        if ua.empty: st.info("미전송 안건 없음")
        else:
            va = ua.copy(); va.insert(0, "전송", False)
            pa = st.data_editor(va[["전송","안건명","입안자","팀","상태","입안일"]], use_container_width=True, hide_index=True, disabled=not can_edit(), column_config={"전송": st.column_config.CheckboxColumn("선택",width="small")})
            sel = pa.index[pa["전송"]==True].tolist()
            if st.button("📨 전송", type="primary", disabled=(not can_edit() or not sel), use_container_width=True, key="send_a"):
                sa_sel = ua.iloc[sel]
                fields = [{"name": f"🗂️ {r['안건명']} ({r['팀']})", "value": f"👤 {r['입안자']}\n🏷️ {r['상태']}\n📅 {r['입안일']}", "inline": False} for _, r in sa_sel.iterrows()]
                ok, msg = send_discord(fields, "📌 신규 안건", "HALLAON Bot", 16744115)
                if ok:
                    ids = set(sa_sel["id"])
                    agenda_df["sent"] = agenda_df["id"].apply(lambda x: "True" if x in ids or str(agenda_df.loc[agenda_df["id"]==x,"sent"].iloc[0])=="True" else "False")
                    st.session_state.agenda_df = agenda_df; save_df_to_gsheet(agenda_df, WORKSHEET_AGENDA)
                    st.success(msg); st.rerun()
                else: st.error(msg)
