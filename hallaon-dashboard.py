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

# ═══════════════════════════════════════
#  🎨 DESIGN SYSTEM — Desaturated 200-tone palette
#  Material Design Dark + monday.com Vibe 참고
# ═══════════════════════════════════════

# Team colors: 기존 포화색 → 200-tone desaturated
TEAM_COLORS = {
    "PM":  "#82b1ff",   # was #4f8cff → Material Blue 200
    "CD":  "#ff8a9e",   # was #ff5c7c → Material Red 200
    "FS":  "#69f0ae",   # was #14c9a2 → Material Green A200
    "DM":  "#b39ddb",   # was #8b6cff → Material Deep Purple 200
    "OPS": "#ffe082",   # was #f5b031 → Material Amber 200
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

# ═══════════════════════════════════════
#  🎨 MASTER CSS — 6-layer elevation system
# ═══════════════════════════════════════
st.markdown("""
<style>
/* ──────────────────────────────────────────
   DESIGN TOKENS (CSS Custom Properties)
   6-layer elevation: dp00 → dp24
   Follows Material Design dark theme spec
   ────────────────────────────────────────── */
:root {
    /* Background layers (elevation via lightness) */
    --dp00: #0d1117;       /* Canvas — GitHub-style deep dark */
    --dp01: #131a24;       /* 5% overlay — sidebar bg */
    --dp02: #161e2a;       /* 7% overlay — card resting */
    --dp04: #1c2636;       /* 9% overlay — card hover / form */
    --dp08: #222e42;       /* 12% overlay — elevated card */
    --dp16: #2a3a52;       /* 15% overlay — modal / dropdown */
    --dp24: #324260;       /* 16% overlay — top bar / toast */

    /* Borders — very subtle, <4% opacity feel */
    --border-subtle: rgba(148, 180, 226, 0.08);
    --border-default: rgba(148, 180, 226, 0.12);
    --border-strong: rgba(148, 180, 226, 0.18);

    /* Typography */
    --text-primary: rgba(240, 246, 255, 0.92);    /* 87-92% white — high emphasis */
    --text-secondary: rgba(176, 196, 226, 0.72);  /* 60% — medium emphasis */
    --text-tertiary: rgba(148, 170, 204, 0.48);   /* 38% — low emphasis / disabled */

    /* Accent — desaturated blue */
    --accent: #82b1ff;
    --accent-muted: rgba(130, 177, 255, 0.16);
    --accent-hover: rgba(130, 177, 255, 0.24);

    /* Semantic */
    --success: #69f0ae;
    --warning: #ffe082;
    --danger: #ef9a9a;

    /* Shadows — layered for natural depth */
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.24), 0 1px 3px rgba(0,0,0,0.12);
    --shadow-md: 0 4px 8px rgba(0,0,0,0.28), 0 2px 4px rgba(0,0,0,0.16);
    --shadow-lg: 0 8px 24px rgba(0,0,0,0.36), 0 4px 8px rgba(0,0,0,0.20);
    --shadow-xl: 0 16px 48px rgba(0,0,0,0.44), 0 8px 16px rgba(0,0,0,0.24);

    /* Radii — generous for native feel */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
    --radius-full: 999px;

    /* Spacing grid (8px base) */
    --sp-1: 4px;
    --sp-2: 8px;
    --sp-3: 12px;
    --sp-4: 16px;
    --sp-5: 20px;
    --sp-6: 24px;
    --sp-8: 32px;
    --sp-10: 40px;

    /* Transitions */
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --duration-fast: 150ms;
    --duration-normal: 250ms;
}

/* ──────────────────────────────────────────
   GLOBAL APP SURFACE
   ────────────────────────────────────────── */
.stApp {
    background: var(--dp00) !important;
    color: var(--text-primary) !important;
    font-weight: 450;
    letter-spacing: 0.01em;
    line-height: 1.7;
}

/* Remove Streamlit default header bar gap */
header[data-testid="stHeader"] {
    background: transparent !important;
}

/* All text inherits */
h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; font-weight: 700 !important; letter-spacing: -0.02em; }
p, div.stMarkdown, div.stText, label { color: var(--text-primary) !important; }
small, [data-testid="stCaptionContainer"] * { color: var(--text-secondary) !important; }

/* ──────────────────────────────────────────
   SIDEBAR — Glassmorphism panel
   ────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(19,26,36,0.92) 0%, rgba(13,17,23,0.96) 100%) !important;
    backdrop-filter: blur(24px) saturate(140%);
    -webkit-backdrop-filter: blur(24px) saturate(140%);
    border-right: 1px solid var(--border-subtle) !important;
    padding: var(--sp-4) var(--sp-4) !important;
}
section[data-testid="stSidebar"] * {
    color: var(--text-primary) !important;
}

/* Sidebar nav radio → pill-style buttons */
section[data-testid="stSidebar"] [data-baseweb="radio"] label {
    background: var(--dp02) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--radius-md) !important;
    padding: var(--sp-3) var(--sp-4) !important;
    margin-bottom: var(--sp-2) !important;
    transition: all var(--duration-fast) var(--ease-out);
    font-weight: 550;
    font-size: 14px;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
    background: var(--accent-muted) !important;
    border-color: var(--accent) !important;
    transform: translateX(3px);
}
section[data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div + label,
section[data-testid="stSidebar"] [data-baseweb="radio"] label[data-selected="true"] {
    background: var(--accent-muted) !important;
    border-color: var(--accent) !important;
    box-shadow: inset 3px 0 0 var(--accent);
}

/* ──────────────────────────────────────────
   METRICS — Floating cards with glow
   ────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: linear-gradient(145deg, var(--dp04) 0%, var(--dp02) 100%) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-lg) !important;
    padding: var(--sp-5) var(--sp-6) !important;
    box-shadow: var(--shadow-md) !important;
    transition: all var(--duration-normal) var(--ease-out);
}
div[data-testid="metric-container"]:hover {
    box-shadow: var(--shadow-lg), 0 0 0 1px var(--accent-muted) !important;
    border-color: rgba(130,177,255,0.2) !important;
    transform: translateY(-2px);
}
div[data-testid="stMetricLabel"] { color: var(--text-secondary) !important; font-size: 13px !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.06em; }
div[data-testid="stMetricValue"] { color: var(--text-primary) !important; font-size: 28px !important; font-weight: 800 !important; }

/* ──────────────────────────────────────────
   CARDS — Data editors, DataFrames
   ────────────────────────────────────────── */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] [role="grid"] {
    background: var(--dp02) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-sm) !important;
    overflow: hidden;
}
/* DataFrame header cells */
div[data-testid="stDataFrame"] [role="columnheader"] {
    background: var(--dp04) !important;
    color: var(--text-secondary) !important;
    font-weight: 650 !important;
    font-size: 12px !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-default) !important;
}
div[data-testid="stDataFrame"] [role="gridcell"] {
    border-bottom: 1px solid var(--border-subtle) !important;
    font-weight: 450;
}

/* ──────────────────────────────────────────
   EXPANDERS — Elevated card treatment
   ────────────────────────────────────────── */
div[data-testid="stExpander"] details {
    background: var(--dp02) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-sm) !important;
    overflow: hidden;
    transition: box-shadow var(--duration-normal) var(--ease-out);
}
div[data-testid="stExpander"] details:hover {
    box-shadow: var(--shadow-md) !important;
}
div[data-testid="stExpander"] details[open] {
    box-shadow: var(--shadow-md) !important;
    border-color: var(--border-strong) !important;
}
div[data-testid="stExpander"] summary {
    background: var(--dp04) !important;
    color: var(--text-primary) !important;
    font-weight: 650 !important;
    padding: var(--sp-4) var(--sp-5) !important;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0 !important;
    transition: background var(--duration-fast) var(--ease-out);
}
div[data-testid="stExpander"] summary:hover {
    background: var(--dp08) !important;
}
div[data-testid="stExpanderDetails"] {
    background: var(--dp02) !important;
    color: var(--text-primary) !important;
    padding: var(--sp-4) var(--sp-5) !important;
}
div[data-testid="stExpanderDetails"] * { color: var(--text-primary); }

/* ──────────────────────────────────────────
   BUTTONS — Gradient primary, ghost secondary
   ────────────────────────────────────────── */
button[kind="primary"],
button[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #82b1ff 0%, #5c8de6 50%, #4a7bd4 100%) !important;
    color: #0d1117 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: var(--radius-md) !important;
    padding: var(--sp-3) var(--sp-6) !important;
    box-shadow: var(--shadow-sm), 0 0 16px rgba(130,177,255,0.15) !important;
    transition: all var(--duration-fast) var(--ease-out);
    letter-spacing: 0.01em;
}
button[kind="primary"]:hover,
button[data-testid="stFormSubmitButton"] > button:hover {
    box-shadow: var(--shadow-md), 0 0 24px rgba(130,177,255,0.25) !important;
    transform: translateY(-1px);
}
button[kind="primary"]:active,
button[data-testid="stFormSubmitButton"] > button:active {
    transform: translateY(0px);
    box-shadow: var(--shadow-sm) !important;
}

button[kind="secondary"],
button:not([kind="primary"]):not([data-testid]) {
    background: var(--dp04) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-md) !important;
    font-weight: 550 !important;
    transition: all var(--duration-fast) var(--ease-out);
}
button[kind="secondary"]:hover {
    background: var(--dp08) !important;
    border-color: var(--border-strong) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ──────────────────────────────────────────
   FORM INPUTS — Elevated input fields
   ────────────────────────────────────────── */
input, textarea {
    background: var(--dp01) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-sm) !important;
    padding: var(--sp-3) var(--sp-4) !important;
    font-weight: 450 !important;
    transition: all var(--duration-fast) var(--ease-out);
}
input:focus, textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-muted) !important;
    outline: none !important;
    background: var(--dp02) !important;
}
div[data-baseweb="select"] > div {
    background: var(--dp01) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-sm) !important;
    transition: all var(--duration-fast) var(--ease-out);
}
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-muted) !important;
}

/* ──────────────────────────────────────────
   TABS — Underline style like Notion
   ────────────────────────────────────────── */
div[data-testid="stTabs"] button {
    color: var(--text-tertiary) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: var(--sp-3) var(--sp-5) !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    transition: all var(--duration-fast) var(--ease-out);
}
div[data-testid="stTabs"] button:hover {
    color: var(--text-primary) !important;
    background: var(--accent-muted) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent) !important;
    font-weight: 700 !important;
    background: transparent !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background: var(--accent) !important;
    height: 3px !important;
    border-radius: 3px 3px 0 0 !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
    background: transparent !important;
    color: var(--text-primary) !important;
    padding-top: var(--sp-6);
}

/* ──────────────────────────────────────────
   MULTISELECT TAGS
   ────────────────────────────────────────── */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background: var(--accent-muted) !important;
    border: 1px solid rgba(130,177,255,0.3) !important;
    border-radius: var(--radius-sm) !important;
    min-height: 28px !important;
    padding: 2px 10px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    color: var(--accent) !important;
    font-weight: 650 !important;
    overflow: visible !important;
}

/* ──────────────────────────────────────────
   CALENDAR / DATEPICKER
   ────────────────────────────────────────── */
[data-baseweb="calendar"], [data-baseweb="calendar"] * {
    background: var(--dp04) !important;
    color: var(--text-primary) !important;
    border-color: var(--border-default) !important;
}
[data-baseweb="calendar"] button { background: transparent !important; }
[data-baseweb="calendar"] [aria-selected="true"] {
    background: var(--accent) !important;
    color: var(--dp00) !important;
    border-radius: var(--radius-full) !important;
    font-weight: 700;
}

/* ──────────────────────────────────────────
   FORMS — Card-wrapped appearance
   ────────────────────────────────────────── */
[data-testid="stForm"] {
    background: var(--dp02) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--radius-lg) !important;
    padding: var(--sp-6) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ──────────────────────────────────────────
   ROLE BADGE & FOLDER BUTTONS
   ────────────────────────────────────────── */
.role-badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: var(--radius-full);
    font-size: 12px;
    font-weight: 700;
    border: 1px solid var(--border-default);
    background: var(--dp04);
    color: var(--accent);
    letter-spacing: 0.04em;
}

.folder-btn button {
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: var(--sp-2) var(--sp-3) !important;
    font-size: 13px !important;
    border-radius: var(--radius-sm) !important;
    transition: all var(--duration-fast) var(--ease-out);
}
.folder-btn button:hover {
    background: var(--accent-muted) !important;
}
.folder-btn button span { color: var(--text-primary) !important; }
.folder-btn button:hover span { color: var(--accent) !important; }

/* ──────────────────────────────────────────
   DIVIDERS — Softer than default
   ────────────────────────────────────────── */
hr, .stMarkdown hr {
    border: none !important;
    border-top: 1px solid var(--border-subtle) !important;
    margin: var(--sp-6) 0 !important;
}

/* ──────────────────────────────────────────
   INFO / SUCCESS / WARNING / ERROR BANNERS
   ────────────────────────────────────────── */
div[data-testid="stAlert"] {
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--border-default) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ──────────────────────────────────────────
   PLOTLY CHARTS — Transparent bg
   ────────────────────────────────────────── */
.js-plotly-plot .plotly .main-svg {
    background: transparent !important;
}

/* ──────────────────────────────────────────
   SCROLLBAR — Thin, native feel
   ────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: var(--radius-full); }
::-webkit-scrollbar-thumb:hover { background: var(--text-tertiary); }

/* ──────────────────────────────────────────
   TOGGLE SWITCH
   ────────────────────────────────────────── */
[data-testid="stToggle"] label > div:first-child {
    border-radius: var(--radius-full) !important;
}

/* ──────────────────────────────────────────
   RESPONSIVE SPACING BOOST
   ────────────────────────────────────────── */
.block-container {
    padding: var(--sp-8) var(--sp-10) !important;
    max-width: 1400px;
}

/* Section headers */
.stMarkdown h2 {
    margin-top: var(--sp-6) !important;
    padding-bottom: var(--sp-3) !important;
    border-bottom: 1px solid var(--border-subtle) !important;
}
.stMarkdown h3 {
    margin-top: var(--sp-5) !important;
    color: var(--text-secondary) !important;
    font-size: 16px !important;
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
    c = TEAM_COLORS.get(t, "#90a4ae")
    return f"<span style='display:inline-block;padding:3px 10px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.16);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.3);'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#90a4ae")
    return f"<span style='display:inline-block;padding:3px 10px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.16);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.3);'>{escape(s)}</span>"

def render_gantt(df):
    if df.empty:
        return "<div style='padding:24px;color:rgba(176,196,226,0.72);font-size:14px;'>표시할 업무가 없습니다.</div>"
    g = df.copy()
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

    h = ""
    h += "<style>"
    h += """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    .gw{font-family:'Inter',system-ui,-apple-system,sans-serif;background:#0d1117;border:1px solid rgba(148,180,226,0.12);border-radius:16px;overflow:auto;box-shadow:0 8px 24px rgba(0,0,0,0.36),0 4px 8px rgba(0,0,0,0.20);}
    .gh{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;background:linear-gradient(135deg,#131a24 0%,#161e2a 100%);border-bottom:1px solid rgba(148,180,226,0.08);}
    .chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:8px;background:rgba(148,180,226,0.06);border:1px solid rgba(148,180,226,0.1);color:rgba(240,246,255,0.85);font-size:11px;font-weight:600;margin-right:6px;letter-spacing:0.03em;}
    .dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
    .gt{width:100%;min-width:1280px;border-collapse:collapse;table-layout:fixed;}
    .gt th,.gt td{border-right:1px solid rgba(148,180,226,0.06);border-bottom:1px solid rgba(148,180,226,0.06);color:rgba(240,246,255,0.9);padding:10px 10px;white-space:nowrap;}
    .gt th{background:#131a24;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:rgba(176,196,226,0.6);}
    .gt tbody tr{transition:background 150ms cubic-bezier(0.16,1,0.3,1);}
    .gt tbody tr:hover{background:rgba(130,177,255,0.04);}
    .wkh{min-width:92px;text-align:center;font-size:10px;color:rgba(176,196,226,0.5);font-weight:600;}
    .tl{padding:0 !important;position:relative;background:transparent;}
    .bg{position:absolute;inset:0;display:flex;pointer-events:none;}
    .bgc{flex:1;border-right:1px solid rgba(148,180,226,0.04);}
    .bgc:nth-child(even){background:rgba(130,177,255,0.02);}
    .barw{position:relative;height:48px;display:flex;align-items:center;}
    .bar{position:absolute;height:28px;border-radius:8px;display:flex;align-items:center;padding:0 10px;font-size:11px;font-weight:700;color:#0d1117;overflow:hidden;text-overflow:ellipsis;box-shadow:0 2px 8px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.15);transition:all 200ms cubic-bezier(0.16,1,0.3,1);}
    .bar:hover{transform:scaleY(1.08);box-shadow:0 4px 16px rgba(0,0,0,0.4),inset 0 1px 0 rgba(255,255,255,0.2);}
    .owner{display:inline-flex;align-items:center;gap:8px;font-weight:500;}
    .av{width:24px;height:24px;border-radius:8px;background:rgba(130,177,255,0.16);color:#82b1ff;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;border:1px solid rgba(130,177,255,0.2);}
    """
    h += "</style>"

    h += "<div class='gw'><div class='gh'><div>"
    for t, c in TEAM_COLORS.items():
        h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += "</div><div style='color:rgba(176,196,226,0.6);font-size:12px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;'>Gantt Chart</div></div>"
    h += "<table class='gt'><thead><tr>"
    h += "<th style='width:72px;text-align:center;'>TEAM</th><th style='width:230px;'>TASK</th><th style='width:130px;'>OWNER</th><th style='width:110px;'>STATUS</th>"
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
        c = TEAM_COLORS.get(team, "#90a4ae")

        s = r["시작일_dt"].date()
        e = r["종료일_dt"].date()
        cs = max(s, tl_start)
        ce = min(e + timedelta(days=1), tl_end)
        off = (cs - tl_start).days
        dur = max((ce - cs).days, 1)
        left = (off / days_total) * 100
        width = (dur / days_total) * 100
        label = "Done" if "완료" in status else "Blocked" if "막힘" in status else "In Progress" if ("진행" in status or "작업" in status) else "Scheduled"
        av = owner[0] if owner else "?"
        bg = "".join(["<div class='bgc'></div>" for _ in range(weeks)])

        h += "<tr>"
        h += f"<td style='text-align:center;'>{team_badge(team)}</td>"
        h += f"<td style='font-weight:600;font-size:13px;'>{escape(task)}</td>"
        h += f"<td><span class='owner'><span class='av'>{escape(av)}</span><span style='font-size:13px;'>{escape(owner)}</span></span></td>"
        h += f"<td>{status_badge(status)}</td>"
        h += f"<td colspan='{weeks}' class='tl'><div class='bg'>{bg}</div><div class='barw'><div class='bar' style='left:{left}%;width:{width}%;background:linear-gradient(135deg,{c} 0%,{c}cc 100%);'>{escape(label)}</div></div></td>"
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
    
    # ─── Styled login card ───
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
        init_data()
        st.session_state.role = None
        st.rerun()
    
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    st.caption("WORKSPACE")
    
    menu = st.radio(
        "메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🗂️ 안건", "📝 회의록", "🤖 작업 전송"],
        label_visibility="collapsed"
    )

# =========================
# Tab 1 업무
# =========================
if menu == "📋 2026 한라온":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📋 2026 한라온</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">팀 업무를 관리하고 추적하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    with st.form("add_task_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            업무명 = st.text_input("업무명", placeholder="새 업무를 입력하세요")
            담당자 = st.text_input("담당자", placeholder="담당자 이름")
        with c2:
            팀 = st.multiselect("팀", TEAM_OPTIONS, default=[])
            상태 = st.selectbox("상태", TASK_STATUS_OPTIONS, index=0)
        with c3:
            시작일 = st.date_input("시작일", value=date.today())
            종료일 = st.date_input("종료일", value=date.today())
        add_btn = st.form_submit_button("➕ 업무 추가", type="primary", disabled=not can_edit())

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

    with st.expander(f"⏳ 진행 중인 업무 ({len(todo_df)})", expanded=True):
        if todo_df.empty:
            st.caption("진행 중인 업무가 없습니다.")
        else:
            st.dataframe(todo_df[["업무명","담당자","팀","상태","시작일","종료일"]], use_container_width=True, hide_index=True)

    with st.expander(f"✅ 완료된 업무 ({len(done_df)})", expanded=False):
        if done_df.empty:
            st.caption("완료된 업무가 없습니다.")
        else:
            st.dataframe(done_df[["업무명","담당자","팀","상태","시작일","종료일"]], use_container_width=True, hide_index=True)

    st.markdown("### ✏️ 업무 수정 / 삭제")
    e = tasks_df.copy()
    e.insert(0, "선택", False)
    e["시작일"] = pd.to_datetime(e["시작일"]).dt.date
    e["종료일"] = pd.to_datetime(e["종료일"]).dt.date

    edited = st.data_editor(
        e[["선택","업무명","담당자","팀","상태","시작일","종료일"]],
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
            base[["업무명","담당자","팀","상태","시작일","종료일"]] = edited[["업무명","담당자","팀","상태","시작일","종료일"]]
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
# Tab 2 간트
# =========================
elif menu == "📊 간트 차트":
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 style="font-size:24px;font-weight:800;margin:0;border:none !important;">📊 간트 차트</h2>
        <p style="color:rgba(176,196,226,0.6);font-size:14px;margin:4px 0 0 0;">타임라인 기반으로 업무 진행 상황을 확인하세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    hide_done = st.toggle("완료 업무 숨기기", value=True)
    gdf = tasks_df.copy()
    if hide_done:
        gdf = gdf[~gdf["상태"].str.contains("완료", na=False)].copy()

    components.html(render_gantt(gdf), height=max(700, len(gdf)*60 + 250), scrolling=True)

# =========================
# Tab 3 대시보드
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
            fig1 = px.pie(s, names="상태", values="개수", hole=0.55, color="상태",
                         color_discrete_map=STATUS_COLORS)
            fig1.update_layout(
                template="plotly_dark",
                height=400,
                showlegend=True,
                legend=dict(font=dict(size=12, color="rgba(240,246,255,0.8)"), bgcolor="rgba(0,0,0,0)"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20, l=20, r=20),
                font=dict(family="Inter, system-ui, sans-serif")
            )
            fig1.update_traces(textfont_size=12, textfont_color="rgba(240,246,255,0.9)")
            st.plotly_chart(fig1, use_container_width=True)

        with chart_col2:
            st.markdown("##### 담당자별 태스크")
            a = unique_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True,
                         color_discrete_sequence=["#82b1ff"])
            fig2.update_layout(
                template="plotly_dark",
                height=400,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=40, l=40, r=20),
                font=dict(family="Inter, system-ui, sans-serif", color="rgba(240,246,255,0.8)"),
                xaxis=dict(gridcolor="rgba(148,180,226,0.06)"),
                yaxis=dict(gridcolor="rgba(148,180,226,0.06)"),
                bargap=0.3,
            )
            fig2.update_traces(
                marker_line_width=0,
                marker=dict(cornerradius=6),
                textfont=dict(color="rgba(240,246,255,0.9)", size=13, family="Inter")
            )
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# Tab 4 안건
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
# Tab 5 회의록
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
        # Viewer area with visual card wrapper
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
# Tab 6 전송
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
                v_t[["전송","업무명","담당자","팀","상태","시작일","종료일"]],
                use_container_width=True, hide_index=True, disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            selected_task_indices = pick_t.index[pick_t["전송"] == True].tolist()
            if st.button("🚀 선택 업무 디스코드 전송", type="primary", disabled=(not can_edit() or not selected_task_indices), use_container_width=True):
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
