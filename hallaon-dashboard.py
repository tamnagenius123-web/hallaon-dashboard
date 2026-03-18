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
from streamlit_calendar import calendar

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
WORKSHEET_DECISIONS = "DECISIONS"

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

# Monday.com Vibe + Toss-inspired semantic color palette (dark theme)
TEAM_COLORS = {
    "PM":  "#6C9CFF",   # Calm blue — strategic, overview
    "CD":  "#FF7EB3",   # Soft rose — creative direction
    "FS":  "#5EEAA0",   # Mint green — field/execution
    "DM":  "#B18CFF",   # Lavender — data/digital
    "OPS": "#FFCB57",   # Warm amber — operations
}
STATUS_COLORS = {
    "완료":   "#5EEAA0",
    "막힘":   "#FF6B6B",
    "진행 중": "#FFCB57",
    "작업 중": "#FFB070",
    "대기":   "#B18CFF",
    "시작 전": "#8899AA",
    "보류":   "#6B7B8D",
}

# =========================
# 🎨 MASTER CSS — Toss + Monday Vibe + shadcn Dark Design System
# Principles applied:
#   1. Toss: "한 화면에 하나의 목적", 충분한 여백, 둥근 모서리, 부드러운 전환
#   2. Monday Vibe: 6-layer elevation, semantic color, accessible contrast (4.5:1+)
#   3. shadcn: Minimal ornamentation, purposeful shadows, composition-first
#   4. Mobile-first: 모바일 사이드바 가시성, 터치 타겟 48px+, 반응형 그리드
# =========================
st.markdown("""
<style>
/* ========== RESET & GLOBAL ========== */
#MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    /* Surface elevation (Monday Vibe 6-layer) */
    --sf-ground: #0B0F14;
    --sf-base:   #101621;
    --sf-raised: #151C2A;
    --sf-overlay: #1A2335;
    --sf-top:    #1F2A40;
    --sf-peak:   #26334D;

    /* Border (3-tier opacity ramp) */
    --bd-subtle:  rgba(140, 170, 220, 0.07);
    --bd-default: rgba(140, 170, 220, 0.12);
    --bd-strong:  rgba(140, 170, 220, 0.20);
    --bd-focus:   rgba(108, 156, 255, 0.5);

    /* Text — WCAG AA 4.5:1 on #101621 */
    --tx-primary:   #E8EDF5;         /* 13.2:1 */
    --tx-secondary: #9BAABB;         /* 6.4:1 */
    --tx-tertiary:  #6B7B8D;         /* 3.8:1 — decorative only */
    --tx-inverse:   #0B0F14;

    /* Accent — Monday-Vibe-inspired blue */
    --accent:       #6C9CFF;
    --accent-soft:  rgba(108, 156, 255, 0.12);
    --accent-hover: rgba(108, 156, 255, 0.20);
    --accent-press: rgba(108, 156, 255, 0.28);

    /* Semantic */
    --success: #5EEAA0; --warning: #FFCB57; --danger: #FF6B6B; --info: #6C9CFF;

    /* Shadows (shadcn-style: purposeful, layered) */
    --sh-xs: 0 1px 2px rgba(0,0,0,0.20);
    --sh-sm: 0 2px 6px rgba(0,0,0,0.24), 0 1px 2px rgba(0,0,0,0.16);
    --sh-md: 0 4px 12px rgba(0,0,0,0.28), 0 2px 4px rgba(0,0,0,0.16);
    --sh-lg: 0 8px 28px rgba(0,0,0,0.36), 0 4px 8px rgba(0,0,0,0.20);
    --sh-xl: 0 16px 48px rgba(0,0,0,0.44), 0 8px 16px rgba(0,0,0,0.24);

    /* Radius (Toss: generous roundness) */
    --r-xs: 6px; --r-sm: 8px; --r-md: 12px; --r-lg: 16px; --r-xl: 20px; --r-2xl: 24px; --r-full: 999px;

    /* Spacing (4px grid — Toss standard) */
    --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-5: 20px; --sp-6: 24px; --sp-8: 32px; --sp-10: 40px; --sp-12: 48px;

    /* Motion (Toss: ease-out, fast feedback) */
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
    --dur-fast: 120ms; --dur-normal: 200ms; --dur-slow: 350ms;
}

/* ========== APP SHELL ========== */
html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
.stApp {
    background: var(--sf-ground) !important;
    color: var(--tx-primary) !important;
    font-weight: 450;
    letter-spacing: 0.005em;
    line-height: 1.65;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

h1, h2, h3, h4, h5, h6 {
    color: var(--tx-primary) !important;
    font-weight: 800 !important;
    letter-spacing: -0.025em;
    line-height: 1.3;
}
h1 { font-size: 28px !important; }
h2 { font-size: 22px !important; }
h3 { font-size: 18px !important; }

p, div.stMarkdown, div.stText, label, span {
    color: var(--tx-primary) !important;
}
small, [data-testid="stCaptionContainer"] * {
    color: var(--tx-secondary) !important;
    font-size: 12px !important;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

a { color: var(--accent) !important; text-decoration: none; }
a:hover { text-decoration: underline; }
hr, .stMarkdown hr { border: none !important; border-top: 1px solid var(--bd-subtle) !important; margin: var(--sp-8) 0 !important; }

/* ========== SCROLLBAR (shadcn minimal) ========== */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bd-strong); border-radius: var(--r-full); }
::-webkit-scrollbar-thumb:hover { background: var(--tx-tertiary); }

/* ========== SIDEBAR (Monday Vibe nav-rail) ========== */
section[data-testid="stSidebar"] {
    background: var(--sf-base) !important;
    border-right: 1px solid var(--bd-subtle) !important;
    padding: var(--sp-5) var(--sp-4) !important;
    box-shadow: var(--sh-sm);
}
section[data-testid="stSidebar"] * { color: var(--tx-primary) !important; }

/* Sidebar radio → pill navigation (Toss tab style) */
section[data-testid="stSidebar"] [data-baseweb="radio"] label {
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: var(--r-md) !important;
    padding: var(--sp-3) var(--sp-4) !important;
    margin-bottom: 2px !important;
    transition: all var(--dur-fast) var(--ease-out);
    font-weight: 550;
    font-size: 14px;
    min-height: 44px;
    display: flex !important;
    align-items: center !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label[data-selected="true"],
section[data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div + label {
    background: var(--accent-soft) !important;
    border-color: transparent !important;
    box-shadow: inset 3px 0 0 var(--accent);
    color: var(--accent) !important;
    font-weight: 700;
}

/* ====== MOBILE SIDEBAR TOGGLE — CRITICAL FIX (Toss mobile UX) ====== */
/* Make the collapsed sidebar arrow MUCH more visible on mobile */
button[data-testid="stSidebarCollapsedControl"],
button[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    background: var(--accent) !important;
    border: none !important;
    border-radius: 0 var(--r-lg) var(--r-lg) 0 !important;
    width: 40px !important;
    height: 48px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: var(--sh-md), 0 0 16px rgba(108,156,255,0.3) !important;
    z-index: 99999 !important;
    position: fixed !important;
    top: 12px !important;
    left: 0 !important;
    transition: all var(--dur-normal) var(--ease-out);
    animation: sidebar-pulse 3s ease-in-out 2;
}
button[data-testid="stSidebarCollapsedControl"] svg,
button[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] svg {
    color: var(--tx-inverse) !important;
    fill: var(--tx-inverse) !important;
    width: 20px !important;
    height: 20px !important;
}
button[data-testid="stSidebarCollapsedControl"]:hover {
    width: 52px !important;
    box-shadow: var(--sh-lg), 0 0 24px rgba(108,156,255,0.5) !important;
}
@keyframes sidebar-pulse {
    0%,100% { box-shadow: var(--sh-md), 0 0 16px rgba(108,156,255,0.3); }
    50% { box-shadow: var(--sh-lg), 0 0 28px rgba(108,156,255,0.6); }
}

/* ========== METRIC CARDS (Monday Vibe card style) ========== */
div[data-testid="metric-container"] {
    background: var(--sf-raised) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-xl) !important;
    padding: var(--sp-6) !important;
    box-shadow: var(--sh-sm) !important;
    transition: all var(--dur-normal) var(--ease-out);
}
div[data-testid="metric-container"]:hover {
    box-shadow: var(--sh-md) !important;
    border-color: var(--bd-strong) !important;
    transform: translateY(-2px);
}
div[data-testid="stMetricLabel"] {
    color: var(--tx-secondary) !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
div[data-testid="stMetricValue"] {
    color: var(--tx-primary) !important;
    font-size: 32px !important;
    font-weight: 900 !important;
    letter-spacing: -0.03em;
}

/* ========== DATA TABLE & DATA EDITOR (Monday grid style) ========== */
div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] [role="grid"] {
    background: var(--sf-raised) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--sh-xs) !important;
    overflow: hidden;
}
div[data-testid="stDataFrame"] [role="columnheader"] {
    background: var(--sf-overlay) !important;
    color: var(--tx-secondary) !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border-bottom: 2px solid var(--bd-default) !important;
}
div[data-testid="stDataFrame"] [role="gridcell"] {
    border-bottom: 1px solid var(--bd-subtle) !important;
    font-weight: 450;
    color: var(--tx-primary) !important;
    font-size: 13px !important;
}

/* ★★★ FIX: data_editor input text visibility (critical UX bug) ★★★ */
div[data-testid="stDataFrame"] input,
div[data-testid="stDataFrame"] textarea,
div[data-testid="stDataFrame"] [contenteditable="true"],
div[data-testid="stDataFrame"] [data-baseweb="input"] input,
div[data-testid="stDataFrame"] [role="gridcell"] input {
    color: #FFFFFF !important;
    background: var(--sf-overlay) !important;
    caret-color: var(--accent) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
/* Glide Data Grid text overlay */
div[data-testid="stDataFrame"] canvas + div input,
div[data-testid="stDataFrame"] canvas + div textarea {
    color: #FFFFFF !important;
    background: var(--sf-top) !important;
    border: 2px solid var(--accent) !important;
    border-radius: var(--r-xs) !important;
    padding: 4px 8px !important;
    font-size: 13px !important;
    caret-color: var(--accent) !important;
}

/* ========== EXPANDER (shadcn accordion) ========== */
div[data-testid="stExpander"] details {
    background: var(--sf-raised) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--sh-xs) !important;
    overflow: hidden;
    transition: all var(--dur-normal) var(--ease-out);
    margin-bottom: var(--sp-3) !important;
}
div[data-testid="stExpander"] details:hover { box-shadow: var(--sh-sm) !important; }
div[data-testid="stExpander"] details[open] { box-shadow: var(--sh-md) !important; border-color: var(--bd-strong) !important; }
div[data-testid="stExpander"] summary {
    background: var(--sf-overlay) !important;
    color: var(--tx-primary) !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: var(--sp-4) var(--sp-5) !important;
    border-radius: var(--r-lg) !important;
    transition: background var(--dur-fast) var(--ease-out);
}
div[data-testid="stExpander"] summary:hover { background: var(--sf-top) !important; }
div[data-testid="stExpanderDetails"] {
    background: var(--sf-raised) !important;
    color: var(--tx-primary) !important;
    padding: var(--sp-5) !important;
}

/* ========== BUTTONS (Toss CTA hierarchy) ========== */
/* Primary — strong visual weight, gradient */
button[kind="primary"], button[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #6C9CFF 0%, #5580E0 100%) !important;
    color: var(--tx-inverse) !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    border: none !important;
    border-radius: var(--r-md) !important;
    padding: var(--sp-3) var(--sp-6) !important;
    min-height: 44px;
    box-shadow: var(--sh-sm), 0 0 12px rgba(108,156,255,0.15) !important;
    transition: all var(--dur-fast) var(--ease-out);
    letter-spacing: 0.01em;
}
button[kind="primary"]:hover, button[data-testid="stFormSubmitButton"] > button:hover {
    box-shadow: var(--sh-md), 0 0 20px rgba(108,156,255,0.3) !important;
    transform: translateY(-1px);
}
button[kind="primary"]:active, button[data-testid="stFormSubmitButton"] > button:active {
    transform: translateY(0);
    box-shadow: var(--sh-xs) !important;
}

/* Secondary — ghost style (Toss secondary CTA) */
button[kind="secondary"],
button:not([kind="primary"]):not([data-testid="stFormSubmitButton"]):not([data-testid="stSidebarCollapsedControl"]):not([data-testid="collapsedControl"]) {
    background: var(--sf-overlay) !important;
    color: var(--tx-primary) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-md) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    min-height: 44px;
    transition: all var(--dur-fast) var(--ease-out);
}
button[kind="secondary"]:hover {
    background: var(--sf-top) !important;
    border-color: var(--bd-strong) !important;
    box-shadow: var(--sh-xs) !important;
}

/* ========== INPUTS (Toss clean input style) ========== */
input, textarea {
    background: var(--sf-base) !important;
    color: var(--tx-primary) !important;
    border: 1.5px solid var(--bd-default) !important;
    border-radius: var(--r-sm) !important;
    padding: var(--sp-3) var(--sp-4) !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    transition: all var(--dur-fast) var(--ease-out);
    caret-color: var(--accent);
    min-height: 44px;
}
input:focus, textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
    outline: none !important;
    background: var(--sf-raised) !important;
}
input::placeholder, textarea::placeholder {
    color: var(--tx-tertiary) !important;
    font-weight: 400;
}

/* Select */
div[data-baseweb="select"] > div {
    background: var(--sf-base) !important;
    color: var(--tx-primary) !important;
    border: 1.5px solid var(--bd-default) !important;
    border-radius: var(--r-sm) !important;
    min-height: 44px;
    transition: all var(--dur-fast) var(--ease-out);
}
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
/* Select dropdown menu */
div[data-baseweb="popover"] > div,
ul[data-baseweb="menu"] {
    background: var(--sf-overlay) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--sh-lg) !important;
}
ul[data-baseweb="menu"] li {
    color: var(--tx-primary) !important;
    font-weight: 500;
}
ul[data-baseweb="menu"] li:hover {
    background: var(--accent-soft) !important;
}

/* ========== TABS (Monday Vibe tab bar) ========== */
div[data-testid="stTabs"] button {
    color: var(--tx-tertiary) !important;
    font-weight: 650 !important;
    font-size: 14px !important;
    padding: var(--sp-3) var(--sp-5) !important;
    border-radius: var(--r-sm) var(--r-sm) 0 0 !important;
    transition: all var(--dur-fast) var(--ease-out);
    min-height: 44px;
}
div[data-testid="stTabs"] button:hover {
    color: var(--tx-primary) !important;
    background: var(--accent-soft) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent) !important;
    font-weight: 800 !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background: var(--accent) !important;
    height: 3px !important;
    border-radius: 3px 3px 0 0 !important;
}

/* ========== MULTISELECT TAGS (Monday color chips) ========== */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background: var(--accent-soft) !important;
    border: 1px solid rgba(108,156,255,0.25) !important;
    border-radius: var(--r-sm) !important;
    min-height: 28px !important;
    padding: 2px 10px !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    color: var(--accent) !important;
    font-weight: 700 !important;
    overflow: visible !important;
}

/* ========== FORM (shadcn card) ========== */
[data-testid="stForm"] {
    background: var(--sf-raised) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-xl) !important;
    padding: var(--sp-6) !important;
    box-shadow: var(--sh-sm) !important;
}

/* ========== TOGGLE ========== */
div[data-testid="stToggle"] label span[data-baseweb="toggle"] {
    background: var(--sf-top) !important;
}

/* ========== TOAST / SUCCESS / ERROR / INFO / WARNING ========== */
div[data-testid="stToast"] {
    background: var(--sf-overlay) !important;
    border: 1px solid var(--bd-default) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--sh-lg) !important;
}

/* Info / Success / Warning / Error boxes */
.stAlert > div {
    border-radius: var(--r-md) !important;
    font-weight: 500 !important;
    font-size: 13px !important;
}

/* ========== CUSTOM CLASSES ========== */
.role-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    border-radius: var(--r-full);
    font-size: 12px;
    font-weight: 700;
    border: 1px solid var(--bd-default);
    background: var(--sf-overlay);
    color: var(--accent) !important;
    letter-spacing: 0.04em;
}
.folder-btn button {
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: var(--sp-2) var(--sp-3) !important;
    font-size: 13px !important;
    border-radius: var(--r-sm) !important;
    transition: all var(--dur-fast) var(--ease-out);
    min-height: 40px !important;
}
.folder-btn button:hover {
    background: var(--accent-soft) !important;
}
.folder-btn button span { color: var(--tx-primary) !important; }
.folder-btn button:hover span { color: var(--accent) !important; }

/* ========== RESPONSIVE BREAKPOINTS ========== */
/* Tablet (≤ 1024px) */
@media (max-width: 1024px) {
    h1 { font-size: 24px !important; }
    h2 { font-size: 20px !important; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; }
    .stApp > div > div > div > div { padding-left: 8px !important; padding-right: 8px !important; }
}

/* Mobile (≤ 768px) — Toss mobile-first principles */
@media (max-width: 768px) {
    h1 { font-size: 22px !important; }
    h2 { font-size: 18px !important; }
    h3 { font-size: 16px !important; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; }
    div[data-testid="metric-container"] { padding: var(--sp-4) !important; }
    
    /* Ensure sidebar toggle button is unmissable on mobile */
    button[data-testid="stSidebarCollapsedControl"],
    button[data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        width: 44px !important;
        height: 52px !important;
        top: 8px !important;
        border-radius: 0 var(--r-xl) var(--r-xl) 0 !important;
        animation: sidebar-pulse 2s ease-in-out 5 !important;
    }
    
    /* Touch targets minimum 44px */
    button, input, textarea, select, [data-baseweb="select"] > div {
        min-height: 44px !important;
    }
    
    /* Stack form columns on mobile */
    [data-testid="stForm"] .stColumns {
        flex-direction: column !important;
    }
    
    /* Expanders: slightly less padding */
    div[data-testid="stExpander"] summary { padding: var(--sp-3) var(--sp-4) !important; }
    div[data-testid="stExpanderDetails"] { padding: var(--sp-3) var(--sp-4) !important; }
}

/* Small mobile (≤ 480px) */
@media (max-width: 480px) {
    h1 { font-size: 20px !important; }
    .stApp { font-size: 14px; }
    div[data-testid="metric-container"] { padding: var(--sp-3) !important; border-radius: var(--r-lg) !important; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
}
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
    c = TEAM_COLORS.get(t, "#8899AA")
    return f"<span style='display:inline-flex;align-items:center;padding:4px 12px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.12);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.25);'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8899AA")
    return f"<span style='display:inline-flex;align-items:center;padding:4px 12px;border-radius:999px;background:rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.12);color:{c};font-size:11px;font-weight:700;letter-spacing:0.04em;border:1px solid rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.25);'>{escape(s)}</span>"

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
    """Forward-pass + backward-pass based Critical Path calculation."""
    df = df.copy()
    df["is_critical"] = False
    if "WBS_코드" not in df.columns or "선행_업무" not in df.columns or df.empty:
        return df

    # Parse dates
    df["_start"] = pd.to_datetime(df["시작일"], errors="coerce")
    df["_end"] = pd.to_datetime(df["종료일"], errors="coerce")
    df = df.dropna(subset=["_start", "_end"])
    if df.empty: return df
    
    # Build WBS → index lookup
    wbs_map = {}
    for idx, row in df.iterrows():
        wbs = str(row["WBS_코드"]).strip()
        if wbs: wbs_map[wbs] = idx
    
    # Forward pass: Earliest Start (ES) / Earliest Finish (EF)
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
                    if max_ef is None or pred_ef > max_ef:
                        max_ef = pred_ef
            if max_ef is not None:
                df.at[idx, "ES"] = max(df.at[idx, "ES"], max_ef + timedelta(days=1))
    
    # Backward pass: Latest Finish (LF) / Latest Start (LS)
    project_end = df["EF"].max()
    df["LF"] = project_end
    df["LS"] = project_end
    
    # Iterate in reverse
    for idx in reversed(df.index.tolist()):
        wbs = str(df.at[idx, "WBS_코드"]).strip()
        # Find all tasks that depend on this one
        for idx2, row2 in df.iterrows():
            preds = str(row2.get("선행_업무", "")).strip()
            if preds:
                pred_list = [p.strip() for p in preds.split(",") if p.strip()]
                if wbs in pred_list:
                    succ_ls = df.at[idx2, "LS"] if "LS" in df.columns else project_end
                    df.at[idx, "LF"] = min(df.at[idx, "LF"], succ_ls - timedelta(days=1))
        
        duration = (df.at[idx, "EF"] - df.at[idx, "ES"]).days
        df.at[idx, "LS"] = df.at[idx, "LF"] - timedelta(days=duration)
    
    # Float = LS - ES. If float ≤ 0, it's critical
    df["_float"] = (df["LS"] - df["ES"]).dt.days
    df["is_critical"] = df["_float"] <= 0
    
    # Cleanup temp columns
    df.drop(columns=["_start", "_end", "ES", "EF", "LS", "LF", "_float"], inplace=True, errors='ignore')
    
    return df

def render_gantt(df):
    if df.empty:
        return "<div style='padding:32px;color:#9BAABB;font-size:14px;text-align:center;'>표시할 업무가 없습니다.</div>"
    
    g = calculate_cpm(df.copy())
    g["시작일_dt"] = pd.to_datetime(g["시작일"], errors="coerce")
    g["종료일_dt"] = pd.to_datetime(g["종료일"], errors="coerce")
    g = g.dropna(subset=["시작일_dt","종료일_dt"])
    if g.empty:
        return "<div style='padding:32px;color:#9BAABB;font-size:14px;text-align:center;'>날짜 데이터가 유효하지 않습니다.</div>"

    min_d = g["시작일_dt"].min().date()
    max_d = g["종료일_dt"].max().date()
    tl_start = min_d - timedelta(days=min_d.weekday())
    days_total = max((max_d - tl_start).days + 14, 35)
    days_total = ((days_total // 7) + 1) * 7
    weeks = days_total // 7
    tl_end = tl_start + timedelta(days=days_total)
    step = 1 if weeks <= 12 else 2 if weeks <= 24 else 4
    today = date.today()
    
    # Determine today's position
    today_off = (today - tl_start).days
    today_pct = (today_off / days_total) * 100 if 0 <= today_off <= days_total else -100

    h = "<style>"
    h += """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    .gw{font-family:'Inter',system-ui,-apple-system,sans-serif;background:#0B0F14;border:1px solid rgba(140,170,220,0.12);border-radius:20px;overflow:auto;box-shadow:0 8px 28px rgba(0,0,0,0.36),0 4px 8px rgba(0,0,0,0.20);}
    .gh{display:flex;justify-content:space-between;align-items:center;padding:16px 24px;background:#101621;border-bottom:1px solid rgba(140,170,220,0.07);flex-wrap:wrap;gap:8px;}
    .chip-row{display:flex;flex-wrap:wrap;gap:6px;}
    .chip{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:8px;background:rgba(140,170,220,0.06);border:1px solid rgba(140,170,220,0.1);color:#9BAABB;font-size:10px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;}
    .dot{width:7px;height:7px;border-radius:50%;display:inline-block;}
    .gt{width:100%;min-width:1200px;border-collapse:collapse;table-layout:fixed;}
    .gt th,.gt td{border-right:1px solid rgba(140,170,220,0.05);border-bottom:1px solid rgba(140,170,220,0.05);color:#E8EDF5;padding:10px 10px;white-space:nowrap;}
    .gt th{background:#151C2A;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#6B7B8D;position:sticky;top:0;z-index:2;}
    .gt tbody tr:hover{background:rgba(108,156,255,0.04);}
    .wkh{min-width:80px;text-align:center;font-size:9px;color:#6B7B8D;font-weight:700;}
    .tl{padding:0 !important;position:relative;background:transparent;}
    .bg{position:absolute;inset:0;display:flex;pointer-events:none;}
    .bgc{flex:1;border-right:1px solid rgba(140,170,220,0.03);}
    .today-line{position:absolute;top:0;bottom:0;width:2px;background:rgba(108,156,255,0.5);z-index:1;pointer-events:none;}
    .today-line::before{content:'Today';position:absolute;top:-18px;left:-14px;font-size:8px;color:#6C9CFF;font-weight:700;letter-spacing:0.04em;}
    .barw{position:relative;height:44px;display:flex;align-items:center;}
    .bar{position:absolute;height:26px;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:10px;font-weight:700;color:#0B0F14;overflow:hidden;text-overflow:ellipsis;box-shadow:0 2px 6px rgba(0,0,0,0.25);transition:all 200ms;}
    .bar:hover{transform:scaleY(1.15);box-shadow:0 4px 12px rgba(0,0,0,0.35);}
    .bar.critical{background:linear-gradient(135deg,#FF6B6B 0%,#E04545 100%) !important;color:#fff;box-shadow:0 0 10px rgba(255,107,107,0.5);border:1px solid #FF9B9B;}
    """
    h += "</style>"

    h += "<div class='gw'><div class='gh'><div class='chip-row'>"
    for t, c in TEAM_COLORS.items():
        h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += f"<span class='chip' style='border-color:rgba(255,107,107,0.3);color:#FF9B9B;'><span class='dot' style='background:#FF6B6B'></span>Critical</span>"
    h += "</div><div style='color:#6B7B8D;font-size:11px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;'>PERT · CPM Gantt</div></div>"
    
    h += "<table class='gt'><thead><tr>"
    h += "<th style='width:55px;'>WBS</th><th style='width:180px;'>업무</th><th style='width:70px;'>선행</th><th style='width:55px;'>TE</th><th style='width:90px;'>상태</th>"
    for i in range(weeks):
        ws = tl_start + timedelta(days=i*7)
        full = f"W{i+1} ({ws.month}/{ws.day})"
        txt = full if i % step == 0 else ""
        h += f"<th class='wkh' title='{full}'>{txt}</th>"
    h += "</tr></thead><tbody>"

    for _, r in g.iterrows():
        wbs = str(r.get("WBS_코드", "")).strip()
        pred = str(r.get("선행_업무", "")).strip()
        te = str(r.get("기대_시간(TE)", "")).strip()
        status = str(r["상태"]).strip()
        task = str(r["업무명"]).strip()
        team = str(r["팀"]).split(",")[0].strip() if str(r["팀"]).strip() else "미지정"
        c = TEAM_COLORS.get(team, "#8899AA")
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
        
        # Today line
        today_html = f"<div class='today-line' style='left:{today_pct}%'></div>" if 0 <= today_pct <= 100 else ""

        h += "<tr>"
        h += f"<td style='font-size:12px;color:#6C9CFF;font-weight:800;'>{escape(wbs)}</td>"
        h += f"<td style='font-weight:600;font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis;'>{escape(task)}</td>"
        h += f"<td style='font-size:10px;color:#9BAABB;'>{escape(pred) if pred else '—'}</td>"
        h += f"<td style='font-size:11px;text-align:center;font-weight:600;'>{escape(te) if te else '—'}</td>"
        h += f"<td>{status_badge(status)}</td>"
        h += f"<td colspan='{weeks}' class='tl'><div class='bg'>{bg}</div>{today_html}<div class='barw'><div class='bar{crit_class}' style='left:{left}%;width:{width}%;background:linear-gradient(135deg,{c} 0%,{c}cc 100%);' title='{escape(task)} ({s} → {e})'>{escape(label)}</div></div></td>"
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
        <div style="text-align:center;max-width:360px;width:100%;">
            <div style="font-size:48px;margin-bottom:12px;">🏛️</div>
            <h1 style="font-size:28px;font-weight:900;margin:0 0 4px 0;letter-spacing:-0.03em;">Hallaon</h1>
            <p style="color:#6B7B8D;font-size:13px;margin-bottom:36px;font-weight:600;letter-spacing:0.04em;">WORKSPACE</p>
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
            <div style="font-size:18px;font-weight:900;letter-spacing:-0.03em;">Hallaon</div>
            <div style="font-size:10px;color:#6B7B8D;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">Workspace</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<span class='role-badge'>{'✏️ 편집' if can_edit() else '👁️ 조회'}</span>", unsafe_allow_html=True)
    
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    
    if st.button("🔄 새로고침 / 권한 전환", use_container_width=True):
        with st.spinner("데이터를 동기화 중입니다..."):
            init_data()
            st.session_state.role = None
        st.rerun()
    
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.caption("WORKSPACE")
    
    menu = st.radio(
        "메뉴",
        ["🏠 홈", "📋 업무 및 WBS", "📊 간트 차트", "📅 캘린더", "📈 대시보드", "🗂️ 안건", "⚖️ 의사결정", "📄 문서", "🤖 작업 전송"],
        label_visibility="collapsed"
    )
    
    # Sidebar: Quick stats (Monday Vibe style — always-visible pulse)
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.caption("QUICK STATUS")
    
    total_t = len(tasks_df)
    done_t = len(tasks_df[tasks_df["상태"].str.contains("완료", na=False)]) if total_t > 0 else 0
    blocked_t = len(tasks_df[tasks_df["상태"].str.contains("막힘", na=False)]) if total_t > 0 else 0
    progress_pct = int((done_t / total_t) * 100) if total_t > 0 else 0
    
    st.markdown(f"""
    <div style="background:#151C2A;border-radius:12px;padding:14px 16px;border:1px solid rgba(140,170,220,0.07);margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-size:12px;font-weight:700;color:#9BAABB;">진행률</span>
            <span style="font-size:14px;font-weight:900;color:#E8EDF5;">{progress_pct}%</span>
        </div>
        <div style="width:100%;height:6px;background:#1A2335;border-radius:999px;overflow:hidden;">
            <div style="width:{progress_pct}%;height:100%;background:linear-gradient(90deg,#5EEAA0,#3DC880);border-radius:999px;transition:width 0.5s ease;"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:10px;">
            <span style="font-size:11px;color:#6B7B8D;font-weight:600;">완료 {done_t}/{total_t}</span>
            <span style="font-size:11px;color:{'#FF6B6B' if blocked_t > 0 else '#6B7B8D'};font-weight:700;">{'🚨 막힘 ' + str(blocked_t) if blocked_t > 0 else '✅ 이상 없음'}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

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
        <div style="background:#151C2A;padding:24px;border-radius:16px;border:1px solid rgba(140,170,220,0.1);height:100%;transition:border-color 0.2s;">
            <div style="font-size:28px;margin-bottom:12px;">📋</div>
            <h4 style="color:#FF7EB3;margin:0 0 10px 0;font-size:15px;">WBS와 고유 코드</h4>
            <p style="color:#9BAABB;font-size:13px;line-height:1.7;margin:0;">
                <b style="color:#E8EDF5;">WBS(Work Breakdown Structure)</b>는 프로젝트를 실행 가능한 단위로 쪼개는 구조입니다.
                WBS 코드는 <b style="color:#FF7EB3;">절대 중복 불가</b> — 고유한 번호여야 합니다.
                예: 하위 업무는 <b style="color:#E8EDF5;">2.2.1</b>, <b style="color:#E8EDF5;">2.2.2</b>처럼 부여하세요.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div style="background:#151C2A;padding:24px;border-radius:16px;border:1px solid rgba(140,170,220,0.1);height:100%;transition:border-color 0.2s;">
            <div style="font-size:28px;margin-bottom:12px;">📊</div>
            <h4 style="color:#FFCB57;margin:0 0 10px 0;font-size:15px;">핵심 경로(CPM)와 PERT</h4>
            <p style="color:#9BAABB;font-size:13px;line-height:1.7;margin:0;">
                업무간 선행 관계를 연결하면 알고리즘이 <b style="color:#E8EDF5;">핵심 경로(Critical Path)</b>를 자동 계산합니다.
                간트 차트의 <b style="color:#FF6B6B;">붉은 막대</b>가 하루라도 지연되면 전체 일정이 밀립니다.
                PERT 3점 추정으로 현실적 소요일을 산출하세요.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div style="background:#151C2A;padding:24px;border-radius:16px;border:1px solid rgba(140,170,220,0.1);height:100%;transition:border-color 0.2s;">
            <div style="font-size:28px;margin-bottom:12px;">⚖️</div>
            <h4 style="color:#5EEAA0;margin:0 0 10px 0;font-size:15px;">의사결정 알고리즘</h4>
            <p style="color:#9BAABB;font-size:13px;line-height:1.7;margin:0;">
                가중치 평가(Weighted Scoring) 모델로 직감과 편향을 배제합니다.
                평가 기준과 가중치를 설정하고 대안별 점수를 입력하면
                알고리즘이 <b style="color:#5EEAA0;">최적 1순위 대안</b>을 과학적으로 추천합니다.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.markdown("### 🚀 3단계 빠른 시작")
    
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.info("**STEP 1. 업무 분할**\n\n`📋 업무 및 WBS` 메뉴에서 프로젝트를 WBS 코드로 나누고, 선행 업무와 PERT 예상 시간을 등록하세요.")
    with col_s2:
        st.warning("**STEP 2. 핵심 경로 파악**\n\n`📊 간트 차트` 메뉴에서 붉은색 핵심 경로(Critical Path) 업무를 확인하고 관리하세요.")
    with col_s3:
        st.success("**STEP 3. 알고리즘 의사결정**\n\n`⚖️ 의사결정` 탭의 가중치 모델을 활용해 객관적으로 결정하세요.")

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
    
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

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
            # Validate WBS code uniqueness
            existing_wbs = tasks_df["WBS_코드"].astype(str).str.strip().tolist()
            if WBS_코드.strip() and WBS_코드.strip() in existing_wbs:
                st.error(f"WBS 코드 '{WBS_코드}'가 이미 존재합니다. 고유한 코드를 입력하세요.")
            else:
                with st.spinner('WBS 데이터를 기록하고 있습니다...'):
                    TE = round((O_time + 4 * M_time + P_time) / 6, 1) if (O_time or M_time or P_time) else 0
                    start_d = date.today()
                    
                    # If predecessor exists, start after predecessor's end date
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

    # Summary stats (Monday Vibe top bar)
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
            # Validate WBS uniqueness on save
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
    
    # Filter options
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

    # Sort by WBS code for logical ordering
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
                "title": f"📋 {r['업무명']} ({r['담당자']})",
                "start": r["시작일"],
                "end": end_date,
                "backgroundColor": f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)}, 0.15)",
                "borderColor": color,
                "textColor": color
            })
            
    for _, r in meetings_df.iterrows():
        if r["회의일자"]:
            calendar_events.append({
                "title": f"📄 {r['제목']}",
                "start": r["회의일자"],
                "backgroundColor": "rgba(94, 234, 160, 0.15)",
                "borderColor": "#5EEAA0",
                "textColor": "#5EEAA0",
                "allDay": True
            })

    for _, r in agenda_df.iterrows():
        if r["입안일"]:
            calendar_events.append({
                "title": f"🗂️ {r['안건명']}",
                "start": r["입안일"],
                "backgroundColor": "rgba(255, 126, 179, 0.15)",
                "borderColor": "#FF7EB3",
                "textColor": "#FF7EB3",
                "allDay": True
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
        .fc-more-link { color: #6C9CFF !important; font-weight: 700; font-size: 11px; }
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
        st.info("업무 데이터가 없습니다. '📋 업무 및 WBS' 탭에서 업무를 등록하세요.")
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
            fig1.update_layout(
                template="plotly_dark", height=380, showlegend=True,
                legend=dict(font=dict(size=12, color="#E8EDF5", family="Inter"), bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=-0.15),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=40, l=20, r=20), font=dict(family="Inter, system-ui, sans-serif")
            )
            fig1.update_traces(textfont_size=12, textfont_color="#E8EDF5", textinfo='percent+label')
            st.plotly_chart(fig1, use_container_width=True)

        with chart_col2:
            st.markdown("##### 담당자별 태스크")
            a = unique_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#6C9CFF"])
            fig2.update_layout(
                template="plotly_dark", height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=40, l=40, r=20), font=dict(family="Inter, system-ui, sans-serif", color="#E8EDF5"),
                xaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""), yaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""),
                bargap=0.35,
            )
            fig2.update_traces(marker_line_width=0, marker=dict(cornerradius=8), textfont=dict(color="#E8EDF5", size=13, family="Inter"))
            st.plotly_chart(fig2, use_container_width=True)

        # Team distribution (additional insight)
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        
        tc1, tc2 = st.columns(2)
        with tc1:
            st.markdown("##### 팀별 업무 분배")
            team_data = []
            for _, row in unique_df.iterrows():
                teams = str(row["팀"]).split(",")
                for t in teams:
                    t = t.strip()
                    if t: team_data.append({"팀": t, "상태": row["상태"]})
            if team_data:
                tdf = pd.DataFrame(team_data)
                tc = tdf["팀"].value_counts().reset_index()
                tc.columns = ["팀", "개수"]
                team_color_list = [TEAM_COLORS.get(t, "#8899AA") for t in tc["팀"]]
                fig3 = px.bar(tc, x="팀", y="개수", text_auto=True, color="팀", 
                              color_discrete_map=TEAM_COLORS)
                fig3.update_layout(
                    template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=20, b=40, l=40, r=20), font=dict(family="Inter", color="#E8EDF5"),
                    xaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""),
                    yaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""),
                    showlegend=False, bargap=0.35,
                )
                fig3.update_traces(marker_line_width=0, marker=dict(cornerradius=8), textfont=dict(color="#E8EDF5", size=13, family="Inter"))
                st.plotly_chart(fig3, use_container_width=True)
        
        with tc2:
            st.markdown("##### 일정 현황")
            # Overdue / On-track / Upcoming
            today_dt = pd.Timestamp(date.today())
            unique_df_copy = unique_df.copy()
            unique_df_copy["종료일_dt"] = pd.to_datetime(unique_df_copy["종료일"], errors="coerce")
            active = unique_df_copy[~unique_df_copy["상태"].str.contains("완료", na=False)]
            
            overdue = len(active[active["종료일_dt"] < today_dt])
            on_track = len(active[(active["종료일_dt"] >= today_dt) & (active["종료일_dt"] <= today_dt + timedelta(days=7))])
            upcoming = len(active[active["종료일_dt"] > today_dt + timedelta(days=7)])
            
            timeline_data = pd.DataFrame({
                "구분": ["기한 초과", "이번 주 마감", "여유 있음"],
                "개수": [overdue, on_track, upcoming]
            })
            fig4 = px.bar(timeline_data, x="구분", y="개수", text_auto=True, 
                         color="구분", color_discrete_map={"기한 초과": "#FF6B6B", "이번 주 마감": "#FFCB57", "여유 있음": "#5EEAA0"})
            fig4.update_layout(
                template="plotly_dark", height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=40, l=40, r=20), font=dict(family="Inter", color="#E8EDF5"),
                xaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""),
                yaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""),
                showlegend=False, bargap=0.35,
            )
            fig4.update_traces(marker_line_width=0, marker=dict(cornerradius=8), textfont=dict(color="#E8EDF5", size=13, family="Inter"))
            st.plotly_chart(fig4, use_container_width=True)

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
    
    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

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

    # Summary
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

    if not can_edit(): st.info("조회 권한입니다. 편집은 '권한 전환'으로 로그인하세요.")

    # Show past decisions
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
            st.caption("예: 예산(40%), 실현가능성(30%), 파급력(30%)")
            criteria = []
            weights = []
            for i in range(st.session_state.criteria_count):
                col_c, col_w = st.columns([7, 3])
                with col_c: cr = st.text_input(f"기준 {i+1}", key=f"cr_{i}", placeholder=f"평가 기준 {i+1}")
                with col_w: wt = st.number_input("가중치(%)", min_value=0, max_value=100, value=round(100 // st.session_state.criteria_count), key=f"wt_{i}")
                criteria.append(cr)
                weights.append(wt)
                
        with c2:
            st.markdown("**비교 대안**")
            st.caption("예: A업체 진행, B업체 진행")
            alts = []
            for i in range(st.session_state.alt_count):
                al = st.text_input(f"대안 {i+1}", key=f"alt_{i}", placeholder=f"대안 {i+1}")
                alts.append(al)

        st.markdown("---")
        st.markdown("#### 2. 대안별 평가 (1~10점)")
        st.caption("각 대안이 해당 기준을 얼마나 잘 충족하는지 점수를 매겨주세요.")
        
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
        weight_sum = sum(valid_weights)
        
        if weight_sum != 100:
            st.error(f"가중치의 합이 100%가 되어야 합니다. (현재: {weight_sum}%)")
        elif not valid_alts:
            st.warning("비교할 대안을 최소 2개 입력해주세요.")
        elif not valid_criteria:
            st.warning("평가 기준을 최소 1개 입력해주세요.")
        elif not sel_agenda or sel_agenda == "등록된 안건 없음":
            st.warning("안건을 먼저 등록하고 선택해주세요.")
        else:
            results = []
            detail_rows = []
            for alt, score_list in scores.items():
                total_score = sum((score * weight / 100) for score, weight in zip(score_list, valid_weights))
                results.append({"대안": alt, "최종 점수": round(total_score, 2)})
                
                # Detail per criterion
                for idx, cr in enumerate(valid_criteria):
                    detail_rows.append({
                        "대안": alt,
                        "기준": cr,
                        "점수": score_list[idx],
                        "가중치": valid_weights[idx],
                        "가중 점수": round(score_list[idx] * valid_weights[idx] / 100, 2)
                    })
            
            res_df = pd.DataFrame(results).sort_values("최종 점수", ascending=False)
            best_alt = res_df.iloc[0]["대안"]
            best_score = res_df.iloc[0]["최종 점수"]

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(94,234,160,0.1) 0%, rgba(108,156,255,0.05) 100%);
                        border:1px solid rgba(94,234,160,0.25);border-radius:16px;padding:24px 28px;margin:16px 0;">
                <div style="font-size:13px;font-weight:700;color:#5EEAA0;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">
                    알고리즘 추천 결과
                </div>
                <div style="font-size:24px;font-weight:900;color:#E8EDF5;letter-spacing:-0.02em;">
                    {escape(best_alt)} <span style="color:#5EEAA0;font-size:18px;font-weight:700;">({best_score}점)</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            rc1, rc2 = st.columns(2)
            with rc1:
                fig = px.bar(res_df, x="대안", y="최종 점수", text="최종 점수", 
                             color="대안", color_discrete_sequence=["#6C9CFF", "#FF7EB3", "#5EEAA0", "#FFCB57", "#B18CFF"])
                fig.update_layout(
                    template="plotly_dark", height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter", color="#E8EDF5"), margin=dict(t=20, b=20, l=20, r=20),
                    xaxis=dict(gridcolor="rgba(140,170,220,0.05)", title=""),
                    yaxis=dict(gridcolor="rgba(140,170,220,0.05)", title="총점"),
                    showlegend=False, bargap=0.35,
                )
                fig.update_traces(marker_line_width=0, marker=dict(cornerradius=8), textfont=dict(color="#E8EDF5", size=14, family="Inter"))
                st.plotly_chart(fig, use_container_width=True)
            
            with rc2:
                st.markdown("##### 상세 평가표")
                detail_df = pd.DataFrame(detail_rows)
                st.dataframe(detail_df, use_container_width=True, hide_index=True)
            
            # Save decision result
            new_decision = {
                "id": str(uuid.uuid4()),
                "안건명": sel_agenda,
                "평가기준": ", ".join(valid_criteria),
                "대안": " vs ".join(valid_alts),
                "최종점수": f"1위: {best_alt} ({best_score}점)",
                "작성일": safe_date_str(date.today())
            }
            decisions_df = pd.concat([decisions_df, pd.DataFrame([new_decision])], ignore_index=True)
            st.session_state.decisions_df = decisions_df
            save_df_to_gsheet(decisions_df, WORKSHEET_DECISIONS)

    # Controls for criteria/alt count
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    adj1, adj2 = st.columns(2)
    with adj1:
        new_cc = st.number_input("평가 기준 개수", min_value=2, max_value=10, value=st.session_state.criteria_count)
        if new_cc != st.session_state.criteria_count:
            st.session_state.criteria_count = new_cc
            st.rerun()
    with adj2:
        new_ac = st.number_input("대안 개수", min_value=2, max_value=10, value=st.session_state.alt_count)
        if new_ac != st.session_state.alt_count:
            st.session_state.alt_count = new_ac
            st.rerun()

# =========================
# Tab: 문서 (회의록 → 문서로 변경)
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

    # ★★★ REDESIGN: Full-width document viewer (not crammed into a narrow column)
    # Step 1: Navigation as a top selector or a compact sidebar section
    
    # Top action bar
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

    # If no document is selected, show the document list (full width)
    if st.session_state.sel_mtg_id is None:
        # Show categorized documents
        folders = ["전체 회의"] + TEAM_OPTIONS
        
        for folder in folders:
            f_df = meetings_df[meetings_df["분류"] == folder].sort_values("회의일자", ascending=False)
            if f_df.empty: continue
            
            with st.expander(f"📁 {folder} ({len(f_df)}건)", expanded=True):
                for _, r in f_df.iterrows():
                    col_title, col_date, col_author, col_action = st.columns([4, 1.5, 1.5, 1])
                    with col_title:
                        st.markdown(f"**{r['제목']}**")
                    with col_date:
                        st.caption(r['회의일자'])
                    with col_author:
                        st.caption(f"👤 {r['작성자']}")
                    with col_action:
                        if st.button("열기", key=f"open_{r['id']}", use_container_width=True):
                            st.session_state.sel_mtg_id = r["id"]
                            st.session_state.is_edit_mtg = False
                            st.rerun()
        
        if meetings_df.empty:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:300px;color:#6B7B8D;">
                <div style="font-size:48px;margin-bottom:16px;">📄</div>
                <div style="font-size:16px;font-weight:700;">아직 문서가 없습니다</div>
                <div style="font-size:13px;margin-top:4px;">상단의 '새 문서 작성' 버튼으로 시작하세요</div>
            </div>
            """, unsafe_allow_html=True)

    # New document form — full width
    elif st.session_state.sel_mtg_id == "NEW":
        st.markdown("""
        <div style="background:#151C2A;border:1px solid rgba(140,170,220,0.1);border-radius:20px;padding:28px;margin-bottom:16px;">
            <h3 style="margin:0 0 4px 0;">✨ 새 문서 작성</h3>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("new_mtg_form"):
            f_title = st.text_input("제목", placeholder="문서 제목을 입력하세요")
            c1, c2, c3 = st.columns(3)
            with c1: f_folder = st.selectbox("분류", ["전체 회의"] + TEAM_OPTIONS)
            with c2: f_date = st.date_input("날짜", value=date.today())
            with c3: f_author = st.text_input("작성자", placeholder="작성자 이름")
            f_content = st.text_area("내용 (Markdown 지원)", height=500, placeholder="내용을 작성하세요...")
            
            btn_c1, btn_c2 = st.columns([1, 3])
            with btn_c1:
                save_btn = st.form_submit_button("💾 저장", type="primary")
            with btn_c2:
                cancel_btn = st.form_submit_button("취소")
            
            if save_btn:
                if not f_title: st.warning("제목을 입력하세요.")
                else:
                    new_row = {
                        "id": str(uuid.uuid4()), "분류": f_folder, "회의일자": safe_date_str(f_date),
                        "제목": f_title, "작성자": f_author or "미정", "내용": f_content
                    }
                    meetings_df = pd.concat([meetings_df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state.meetings_df = meetings_df
                    save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                    st.session_state.sel_mtg_id = new_row["id"]
                    st.session_state.is_edit_mtg = False
                    st.rerun()
            if cancel_btn:
                st.session_state.sel_mtg_id = None
                st.rerun()

    # View/Edit existing document — full width
    else:
        m_data = meetings_df[meetings_df["id"] == st.session_state.sel_mtg_id]
        if m_data.empty:
            st.error("문서를 찾을 수 없습니다.")
            st.session_state.sel_mtg_id = None
        else:
            mtg = m_data.iloc[0]
            if not st.session_state.is_edit_mtg:
                # Read mode — clean document view (Toss: one purpose per screen)
                st.markdown(f"""
                <div style="background:#151C2A;border:1px solid rgba(140,170,220,0.1);border-radius:20px;padding:32px 36px;margin-bottom:8px;">
                    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
                        <span style="display:inline-flex;align-items:center;padding:4px 12px;border-radius:999px;background:rgba(108,156,255,0.12);color:#6C9CFF;font-size:11px;font-weight:700;">📁 {escape(mtg['분류'])}</span>
                        <span style="display:inline-flex;align-items:center;padding:4px 12px;border-radius:999px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:11px;font-weight:600;">📅 {escape(mtg['회의일자'])}</span>
                        <span style="display:inline-flex;align-items:center;padding:4px 12px;border-radius:999px;background:rgba(140,170,220,0.06);color:#9BAABB;font-size:11px;font-weight:600;">👤 {escape(mtg['작성자'])}</span>
                    </div>
                    <h2 style="margin:0 0 20px 0;font-size:26px;font-weight:900;letter-spacing:-0.03em;">{escape(mtg['제목'])}</h2>
                    <div style="border-top:1px solid rgba(140,170,220,0.07);padding-top:20px;line-height:1.8;font-size:15px;color:#E8EDF5;font-weight:450;">
                        {mtg['내용'].replace(chr(10), '<br>')}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                act_c1, act_c2, act_c3 = st.columns([1, 1, 4])
                with act_c1:
                    if can_edit() and st.button("✏️ 수정", use_container_width=True):
                        st.session_state.is_edit_mtg = True
                        st.rerun()
                with act_c2:
                    if can_edit() and st.button("🗑️ 삭제", use_container_width=True):
                        keep_m = meetings_df[meetings_df["id"] != mtg['id']].reset_index(drop=True)
                        st.session_state.meetings_df = keep_m
                        save_df_to_gsheet(keep_m, WORKSHEET_MEETINGS)
                        st.session_state.sel_mtg_id = None
                        st.rerun()

            else:
                # Edit mode
                st.markdown("""
                <div style="background:#151C2A;border:1px solid rgba(140,170,220,0.1);border-radius:20px;padding:28px;margin-bottom:8px;">
                    <h3 style="margin:0;">✏️ 문서 수정</h3>
                </div>
                """, unsafe_allow_html=True)
                
                with st.form("edit_mtg_form"):
                    f_title = st.text_input("제목", value=mtg['제목'])
                    c1, c2, c3 = st.columns(3)
                    with c1: f_folder = st.selectbox("분류", ["전체 회의"] + TEAM_OPTIONS, index=(["전체 회의"]+TEAM_OPTIONS).index(mtg['분류']) if mtg['분류'] in (["전체 회의"]+TEAM_OPTIONS) else 0)
                    with c2: f_date = st.date_input("날짜", value=pd.to_datetime(mtg['회의일자']).date())
                    with c3: f_author = st.text_input("작성자", value=mtg['작성자'])
                    f_content = st.text_area("내용", value=mtg['내용'], height=500)

                    btn_c1, btn_c2 = st.columns([1, 3])
                    with btn_c1:
                        save_btn = st.form_submit_button("💾 저장", type="primary")
                    with btn_c2:
                        cancel_btn = st.form_submit_button("취소")
                    
                    if save_btn:
                        idx = meetings_df.index[meetings_df["id"] == mtg['id']].tolist()[0]
                        meetings_df.at[idx, '제목'] = f_title
                        meetings_df.at[idx, '분류'] = f_folder
                        meetings_df.at[idx, '회의일자'] = safe_date_str(f_date)
                        meetings_df.at[idx, '작성자'] = f_author
                        meetings_df.at[idx, '내용'] = f_content
                        st.session_state.meetings_df = meetings_df
                        save_df_to_gsheet(meetings_df, WORKSHEET_MEETINGS)
                        st.session_state.is_edit_mtg = False
                        st.rerun()
                    if cancel_btn:
                        st.session_state.is_edit_mtg = False
                        st.rerun()

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

