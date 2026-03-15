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
# Config
# =========================
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")
EDIT_PASSWORD = st.secrets.get("EDIT_PASSWORD", "")
VIEW_PASSWORD = st.secrets.get("VIEW_PASSWORD", "")

TASKS_CSV = "tasks_data.csv"
AGENDA_CSV = "agenda_data.csv"

TEAM_OPTIONS = ["PM", "CD", "FS", "DM", "OPS"]
TASK_STATUS_OPTIONS = ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"]
AGENDA_STATUS_OPTIONS = ["시작 전", "진행 중", "완료", "보류"]

TEAM_COLORS = {"PM": "#4f8cff", "CD": "#ff5c7c", "FS": "#14c9a2", "DM": "#8b6cff", "OPS": "#f5b031"}
STATUS_COLORS = {
    "완료": "#10c27c",
    "막힘": "#ef4e4e",
    "진행 중": "#f5b031",
    "작업 중": "#f5b031",
    "대기": "#8b6cff",
    "시작 전": "#8893a8",
    "보류": "#7f8aa3"
}

# =========================
# Style
# =========================
st.markdown("""
<style>
:root {
  --bg:#0a1222; --panel:#121d34; --line:#2f4775; --txt:#f4f8ff; --muted:#b5c4e3;
}
.stApp {
  background: radial-gradient(1200px 650px at 8% -10%, #1c2f56 0%, #0a1222 50%, #091020 100%);
  color: var(--txt);
}
h1,h2,h3,h4,h5,h6,p,span,label,div { color: var(--txt) !important; }
small,[data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg,#15213d 0%, #101a30 100%);
  border-right:1px solid var(--line);
}
section[data-testid="stSidebar"] * { color:#ecf3ff !important; }
section[data-testid="stSidebar"] [data-baseweb="radio"] label {
  background:#1a2a4b; border:1px solid #35558e; border-radius:10px; padding:8px 10px; margin-bottom:8px;
}

div[data-testid="metric-container"] {
  background: linear-gradient(180deg,#213a69 0%, #1a2f57 100%) !important;
  border:1px solid #4a6aa5 !important;
  border-radius:14px !important;
}
div[data-testid="metric-container"] * { color:#ffffff !important; }

div[data-testid="stExpander"] details {
  background:#121d34 !important; border:1px solid #2f4775 !important; border-radius:10px !important;
}
div[data-testid="stExpander"] summary {
  background:#121d34 !important; color:#f4f8ff !important;
}

div[data-testid="stDataFrame"] [role="grid"] { background:#121d34 !important; }
div[data-testid="stDataFrame"] * { color:#f4f8ff !important; }
div[data-testid="stDataFrame"] button {
  background:#1b2d52 !important; border:1px solid #35558e !important; color:#f4f8ff !important;
}

div[data-baseweb="select"] > div {
  background:#121d34 !important; border:1px solid #35558e !important; color:#f4f8ff !important;
}
div[data-baseweb="popover"] ul { background:#121d34 !important; border:1px solid #35558e !important; }
div[data-baseweb="popover"] li { background:#121d34 !important; color:#f4f8ff !important; }

div[data-baseweb="calendar"] { background:#121d34 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }
div[data-baseweb="calendar"] * { color:#f4f8ff !important; }

div[data-baseweb="tag"] { padding-left:8px !important; padding-right:8px !important; min-height:28px !important; }
div[data-baseweb="tag"] span { overflow:visible !important; text-indent:0 !important; }

input, textarea { background:#121d34 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }
button[kind="primary"] { background:linear-gradient(180deg,#5b97ff 0%, #4b87f3 100%) !important; color:#fff !important; border:none !important; }
button[kind="secondary"] { background:#1a2d52 !important; color:#f4f8ff !important; border:1px solid #35558e !important; }

.role-badge {
  display:inline-block; padding:6px 10px; border-radius:999px; font-size:12px; font-weight:700;
  border:1px solid #4166a6; background:#1a2f57; color:#eaf2ff;
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* DataEditor column menu / toolbar popover dark fix */
[data-testid="stDataFrame"] [data-baseweb="popover"] > div,
[data-testid="stDataFrame"] [role="menu"],
[data-testid="stDataFrame"] [role="listbox"] {
  background: #121d34 !important;
  border: 1px solid #35558e !important;
  color: #f4f8ff !important;
}
[data-testid="stDataFrame"] [role="menu"] *,
[data-testid="stDataFrame"] [role="listbox"] * {
  color: #f4f8ff !important;
}
[data-testid="stDataFrame"] [role="menuitem"] {
  background: #121d34 !important;
}
[data-testid="stDataFrame"] [role="menuitem"]:hover {
  background: #1f3563 !important;
}
[data-testid="stDataFrame"] [aria-disabled="true"] {
  opacity: 0.45 !important;
}

/* grid header icons + toolbar contrast */
[data-testid="stDataFrame"] [class*="toolbar"] button,
[data-testid="stDataFrame"] [class*="header"] button {
  background: #1b2d52 !important;
  border: 1px solid #35558e !important;
  color: #f4f8ff !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Date input popover dark fix (global) */
[data-baseweb="popover"] [data-baseweb="calendar"],
[data-baseweb="calendar"] {
  background: #121d34 !important;
  border: 1px solid #35558e !important;
  color: #f4f8ff !important;
}
[data-baseweb="popover"] [data-baseweb="calendar"] *,
[data-baseweb="calendar"] * {
  color: #f4f8ff !important;
}
[data-baseweb="calendar"] table,
[data-baseweb="calendar"] thead,
[data-baseweb="calendar"] tbody,
[data-baseweb="calendar"] tr,
[data-baseweb="calendar"] td,
[data-baseweb="calendar"] th {
  background: #121d34 !important;
}
[data-baseweb="calendar"] button {
  background: transparent !important;
  color: #f4f8ff !important;
}
[data-baseweb="calendar"] [aria-selected="true"] {
  background: #ff5c7c !important;
  color: #ffffff !important;
  border-radius: 999px !important;
}
</style>
""", unsafe_allow_html=True)



# =========================
# Utils
# =========================
def safe_date_str(v):
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception:
        return date.today().strftime("%Y-%m-%d")

def load_csv(path, default_cols):
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=default_cols)
    for c in default_cols:
        if c not in df.columns:
            df[c] = ""
    return df[default_cols].copy()

def save_csv(df, path):
    df.to_csv(path, index=False)

def normalize_tasks_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["id","업무명","담당자","팀","상태","시작일","종료일","sent"])
    d = df.copy()
    if "작업명" in d.columns and "업무명" not in d.columns:
        d["업무명"] = d["작업명"]
    if "소유자" in d.columns and "담당자" not in d.columns:
        d["담당자"] = d["소유자"]
    req = ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]
    if "id" not in d.columns:
        d["id"] = [str(uuid.uuid4()) for _ in range(len(d))]
    if "업무명" not in d.columns:
        d["업무명"] = ""
    if "담당자" not in d.columns:
        d["담당자"] = "담당자 미정"
    if "팀" not in d.columns:
        d["팀"] = "미지정"
    if "상태" not in d.columns:
        d["상태"] = "시작 전"
    if "시작일" not in d.columns:
        d["시작일"] = date.today().strftime("%Y-%m-%d")
    if "종료일" not in d.columns:
        d["종료일"] = date.today().strftime("%Y-%m-%d")
    if "sent" not in d.columns:
        d["sent"] = "False"
    d["시작일"] = d["시작일"].apply(safe_date_str)
    d["종료일"] = d["종료일"].apply(safe_date_str)
    return d[req].fillna("")

def normalize_agenda_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=["id","안건명","입안자","팀","상태","입안일","sent"])
    d = df.copy()
    req = ["id","안건명","입안자","팀","상태","입안일","sent"]
    if "id" not in d.columns:
        d["id"] = [str(uuid.uuid4()) for _ in range(len(d))]
    if "안건명" not in d.columns:
        d["안건명"] = d["제목"] if "제목" in d.columns else ""
    if "입안자" not in d.columns:
        d["입안자"] = "담당자 미정"
    if "팀" not in d.columns:
        d["팀"] = "미지정"
    if "상태" not in d.columns:
        d["상태"] = "시작 전"
    if "입안일" not in d.columns:
        d["입안일"] = date.today().strftime("%Y-%m-%d")
    if "sent" not in d.columns:
        d["sent"] = "False"
    d["입안일"] = d["입안일"].apply(safe_date_str)
    return d[req].fillna("")

def init_data():
    task_cols = ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]
    agenda_cols = ["id","안건명","입안자","팀","상태","입안일","sent"]
    t_raw = load_csv(TASKS_CSV, task_cols)
    a_raw = load_csv(AGENDA_CSV, agenda_cols)
    t = normalize_tasks_df(t_raw)
    a = normalize_agenda_df(a_raw)
    st.session_state.tasks_df = t
    st.session_state.agenda_df = a
    save_csv(t, TASKS_CSV)
    save_csv(a, AGENDA_CSV)

def auth_gate():
    if EDIT_PASSWORD == "" and VIEW_PASSWORD == "":
        st.session_state.role = "edit"
        return
    if "role" not in st.session_state:
        st.session_state.role = None
    if st.session_state.role is not None:
        return
    st.title("🔐 로그인")
    role_choice = st.radio("권한", ["조회", "편집"], horizontal=True)
    pw = st.text_input("비밀번호", type="password")
    if st.button("로그인", type="primary"):
        if role_choice == "편집" and pw == EDIT_PASSWORD:
            st.session_state.role = "edit"
            st.rerun()
        elif role_choice == "조회" and pw == VIEW_PASSWORD:
            st.session_state.role = "view"
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

def can_edit():
    return st.session_state.get("role") == "edit"

def team_badge(team):
    t = str(team).split(",")[0].strip() if str(team).strip() else "미지정"
    c = TEAM_COLORS.get(t, "#7b8599")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8893a8")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(s)}</span>"

def send_discord(fields, title, username, color=3447003):
    if not DISCORD_WEBHOOK_URL:
        return False, "DISCORD_WEBHOOK_URL이 설정되지 않았습니다."
    try:
        sent = 0
        for i in range(0, len(fields), 25):
            batch = fields[i:i+25]
            payload = {
                "username": username,
                "embeds": [{
                    "title": title,
                    "color": color,
                    "fields": batch,
                    "footer": {"text": f"Hallaon Agile • {len(batch)}개"}
                }]
            }
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if r.status_code not in (200, 204):
                return False, f"HTTP {r.status_code}: {r.text[:120]}"
            sent += len(batch)
        return True, f"{sent}개 전송 완료"
    except Exception as e:
        return False, str(e)

def render_table_html(df, cols):
    if df.empty:
        return "<div style='padding:12px;color:#b5c4e3;'>항목이 없습니다.</div>"
    h = """
    <style>
    .tb-wrap{border:1px solid #2f4775;border-radius:10px;overflow:auto;background:#121d34;}
    .tb{width:100%;border-collapse:collapse;min-width:860px;}
    .tb th{background:#1a2c50;color:#f4f8ff;padding:10px;border-right:1px solid #2f4775;border-bottom:1px solid #2f4775;text-align:left;font-size:12px;font-weight:700;}
    .tb td{background:#121d34;color:#f4f8ff;padding:10px;border-right:1px solid #2f4775;border-bottom:1px solid #2f4775;font-size:14px;}
    .tb tr:hover td{background:#172746;}
    .tb th:last-child,.tb td:last-child{border-right:none;}
    </style>
    <div class='tb-wrap'><table class='tb'><thead><tr>
    """
    for c in cols:
        h += f"<th>{escape(c)}</th>"
    h += "</tr></thead><tbody>"
    for _, r in df.iterrows():
        h += "<tr>"
        for c in cols:
            if c == "팀":
                h += f"<td>{team_badge(r[c])}</td>"
            elif c == "상태":
                h += f"<td>{status_badge(r[c])}</td>"
            else:
                h += f"<td>{escape(str(r[c]))}</td>"
        h += "</tr>"
    h += "</tbody></table></div>"
    return h

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

# =========================
# Init
# =========================
if "tasks_df" not in st.session_state or "agenda_df" not in st.session_state:
    init_data()
auth_gate()

tasks_df = st.session_state.tasks_df.copy()
agenda_df = st.session_state.agenda_df.copy()

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.title("🏛️ Hallaon")
    role_txt = "편집" if can_edit() else "조회"
    st.markdown(f"<span class='role-badge'>권한: {role_txt}</span>", unsafe_allow_html=True)
    st.caption("편집: 추가/수정/삭제/전송 가능 · 조회: 보기만 가능")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("권한 전환"):
            st.session_state.role = None
            st.rerun()
    with c2:
        if st.button("새로고침"):
            init_data()
            st.rerun()
    st.markdown("---")
    menu = st.radio(
        "워크스페이스 메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🗂️ 안건", "🤖 최근 등록된 작업 전송", "🛠️ 백업/복원"]
    )

# =========================
# Tab 1 업무
# =========================
if menu == "📋 2026 한라온":
    st.header("📋 2026 한라온")
    if not can_edit():
        st.info("조회 권한입니다. 편집하려면 좌측 '권한 전환'을 눌러 편집 권한으로 로그인하세요.")

    with st.form("add_task_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            업무명 = st.text_input("업무명")
            담당자 = st.text_input("담당자")
        with c2:
            팀 = st.multiselect("팀", TEAM_OPTIONS, default=["PM"])
            상태 = st.selectbox("상태", TASK_STATUS_OPTIONS, index=0)
        with c3:
            시작일 = st.date_input("시작일", value=date.today())
            종료일 = st.date_input("종료일", value=date.today())
        add_btn = st.form_submit_button("업무 추가", type="primary", disabled=not can_edit())

    if add_btn and 업무명.strip():
        row = {
            "id": str(uuid.uuid4()),
            "업무명": 업무명.strip(),
            "담당자": 담당자.strip() if 담당자.strip() else "담당자 미정",
            "팀": ", ".join(팀) if 팀 else "미지정",
            "상태": 상태,
            "시작일": safe_date_str(시작일),
            "종료일": safe_date_str(종료일),
            "sent": "False"
        }
        tasks_df = pd.concat([tasks_df, pd.DataFrame([row])], ignore_index=True)
        st.session_state.tasks_df = tasks_df
        save_csv(tasks_df, TASKS_CSV)
        st.success("업무가 추가되었습니다.")
        st.rerun()

    todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)].copy()
    done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)].copy()

    with st.expander(f"할 일 ({len(todo_df)}개)", expanded=True):
        st.components.v1.html(
            render_table_html(todo_df[["업무명","담당자","팀","상태","시작일","종료일"]], ["업무명","담당자","팀","상태","시작일","종료일"]),
            height=max(220, len(todo_df)*45 + 90),
            scrolling=True
        )

    with st.expander(f"완료됨 ({len(done_df)}개)", expanded=False):
        st.components.v1.html(
            render_table_html(done_df[["업무명","담당자","팀","상태","시작일","종료일"]], ["업무명","담당자","팀","상태","시작일","종료일"]),
            height=max(180, len(done_df)*45 + 90),
            scrolling=True
        )

    st.markdown("### 업무 수정/삭제")
    e = tasks_df.copy()
    e.insert(0, "선택", False)
    edited = st.data_editor(
        e[["선택","업무명","담당자","팀","상태","시작일","종료일"]],
        use_container_width=True,
        hide_index=True,
        disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택")}
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("업무 수정사항 저장", type="primary", disabled=not can_edit()):
            base = tasks_df.copy().reset_index(drop=True)
            base[["업무명","담당자","팀","상태","시작일","종료일"]] = edited[["업무명","담당자","팀","상태","시작일","종료일"]]
            base["시작일"] = base["시작일"].apply(safe_date_str)
            base["종료일"] = base["종료일"].apply(safe_date_str)
            st.session_state.tasks_df = base
            save_csv(base, TASKS_CSV)
            st.success("수정사항이 저장되었습니다.")
            st.rerun()
    with c2:
        if st.button("선택 업무 삭제", disabled=not can_edit()):
            idx = edited.index[edited["선택"] == True].tolist()
            if not idx:
                st.warning("삭제할 업무를 선택하세요.")
            else:
                keep = tasks_df.drop(index=idx).reset_index(drop=True)
                st.session_state.tasks_df = keep
                save_csv(keep, TASKS_CSV)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()
                
    st.markdown("### 업무 상태 일괄 수정")
    if tasks_df.empty:
        st.info("수정할 업무가 없습니다.")
    else:
        c1, c2, c3 = st.columns([2,1,1])
        with c1:
            target_task = st.selectbox("대상 업무", tasks_df["업무명"].tolist(), key="task_status_target")
        with c2:
            new_task_status = st.selectbox("변경 상태", TASK_STATUS_OPTIONS, key="task_status_new")
        with c3:
            if st.button("업무 상태 변경", type="primary", disabled=not can_edit()):
                idx = tasks_df.index[tasks_df["업무명"] == target_task].tolist()
                if idx:
                    tasks_df.loc[idx, "상태"] = new_task_status
                    st.session_state.tasks_df = tasks_df
                    save_csv(tasks_df, TASKS_CSV)
                    st.success("업무 상태가 변경되었습니다.")
                    st.rerun()

# =========================
# Tab 2 간트
# =========================
elif menu == "📊 간트 차트":
    st.header("📊 간트 차트 (Agile Tools)")
    hide_done = st.toggle("완료 업무 숨기기", value=True)
    gdf = tasks_df.copy()
    if hide_done:
        gdf = gdf[~gdf["상태"].str.contains("완료", na=False)].copy()
    st.components.v1.html(render_gantt(gdf), height=max(700, len(gdf)*56 + 230), scrolling=True)


# =========================
# Tab 3 대시보드
# =========================
elif menu == "📈 대시보드":
    st.header("📈 2026 한라온 종합 대시보드")
    if tasks_df.empty:
        st.info("업무 데이터가 없습니다.")
    else:
        total = len(tasks_df)
        inprog = len(tasks_df[tasks_df["상태"].str.contains("진행|작업", na=False)])
        stuck = len(tasks_df[tasks_df["상태"].str.contains("막힘", na=False)])
        done = len(tasks_df[tasks_df["상태"].str.contains("완료", na=False)])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📦 전체 업무", total)
        m2.metric("⏳ 진행 중", inprog)
        m3.metric("🛑 막힘", stuck)
        m4.metric("✅ 완료", done)

        l, r = st.columns(2)
        with l:
            s = tasks_df["상태"].value_counts().reset_index()
            s.columns = ["상태","개수"]
            fig1 = px.pie(s, names="상태", values="개수", hole=0.5, color="상태", color_discrete_map=STATUS_COLORS)
            fig1.update_traces(textposition="inside", textinfo="percent+label")
            fig1.update_layout(
                template="plotly_dark",
                height=380,
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10,b=10,l=10,r=10)
            )
            st.plotly_chart(fig1, use_container_width=True)

        with r:
            a = tasks_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#5b97ff"])
            fig2.update_layout(
                template="plotly_dark",
                height=380,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10,b=10,l=10,r=10)
            )
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# Tab 4 안건
# =========================
elif menu == "🗂️ 안건":
    st.header("🗂️ 안건")
    if not can_edit():
        st.info("조회 권한입니다. 편집하려면 좌측 '권한 전환'을 눌러 편집 권한으로 로그인하세요.")

    with st.form("add_agenda_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            안건명 = st.text_input("안건명")
        with c2:
            팀 = st.multiselect("팀", TEAM_OPTIONS, default=["PM"])
        with c3:
            입안자 = st.text_input("입안자")
        with c4:
            입안일 = st.date_input("입안일", value=date.today())
        상태 = st.selectbox("상태", AGENDA_STATUS_OPTIONS, index=0)
        add_btn = st.form_submit_button("안건 추가", type="primary", disabled=not can_edit())

    if add_btn and 안건명.strip():
        row = {
            "id": str(uuid.uuid4()),
            "안건명": 안건명.strip(),
            "입안자": 입안자.strip() if 입안자.strip() else "담당자 미정",
            "팀": ", ".join(팀) if 팀 else "미지정",
            "상태": 상태,
            "입안일": safe_date_str(입안일),
            "sent": "False"
        }
        agenda_df = pd.concat([agenda_df, pd.DataFrame([row])], ignore_index=True)
        st.session_state.agenda_df = agenda_df
        save_csv(agenda_df, AGENDA_CSV)
        st.success("안건이 추가되었습니다.")
        st.rerun()

    c1, c2, c3, c4 = st.columns([2,1,1,1])
    with c1:
        q = st.text_input("검색", placeholder="안건명 검색")
    with c2:
        team_filter = st.selectbox("팀 필터", ["전체"] + sorted(agenda_df["팀"].dropna().unique().tolist()), index=0)
    with c3:
        status_filter = st.selectbox("상태 필터", ["전체"] + sorted(agenda_df["상태"].dropna().unique().tolist()), index=0)
    with c4:
        sort_opt = st.selectbox("정렬", ["입안일 최신순","입안일 오래된순"], index=0)

    f = agenda_df.copy()
    if q:
        f = f[f["안건명"].str.contains(q, case=False, na=False)]
    if team_filter != "전체":
        f = f[f["팀"] == team_filter]
    if status_filter != "전체":
        f = f[f["상태"] == status_filter]
    f["입안일_dt"] = pd.to_datetime(f["입안일"], errors="coerce")
    f = f.sort_values("입안일_dt", ascending=(sort_opt == "입안일 오래된순")).drop(columns=["입안일_dt"]).reset_index(drop=True)

    st.components.v1.html(
        render_table_html(f[["안건명","입안자","팀","상태","입안일"]], ["안건명","입안자","팀","상태","입안일"]),
        height=max(220, len(f)*45 + 90),
        scrolling=True
    )

    st.markdown("### 안건 수정/삭제")
    e = agenda_df.copy()
    e.insert(0, "선택", False)
    edited = st.data_editor(
        e[["선택","안건명","입안자","팀","상태","입안일"]],
        use_container_width=True,
        hide_index=True,
        disabled=not can_edit(),
        column_config={"선택": st.column_config.CheckboxColumn("선택")}
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("안건 수정사항 저장", type="primary", disabled=not can_edit()):
            base = agenda_df.copy().reset_index(drop=True)
            base[["안건명","입안자","팀","상태","입안일"]] = edited[["안건명","입안자","팀","상태","입안일"]]
            base["입안일"] = base["입안일"].apply(safe_date_str)
            st.session_state.agenda_df = base
            save_csv(base, AGENDA_CSV)
            st.success("수정사항이 저장되었습니다.")
            st.rerun()
    with c2:
        if st.button("선택 안건 삭제", disabled=not can_edit()):
            idx = edited.index[edited["선택"] == True].tolist()
            if not idx:
                st.warning("삭제할 안건을 선택하세요.")
            else:
                keep = agenda_df.drop(index=idx).reset_index(drop=True)
                st.session_state.agenda_df = keep
                save_csv(keep, AGENDA_CSV)
                st.success(f"{len(idx)}개 삭제 완료")
                st.rerun()
    st.markdown("### 안건 상태 일괄 수정")
    if agenda_df.empty:
        st.info("수정할 안건이 없습니다.")
    else:
        c1, c2, c3 = st.columns([2,1,1])
        with c1:
            target_agenda = st.selectbox("대상 안건", agenda_df["안건명"].tolist(), key="agenda_status_target")
        with c2:
            new_agenda_status = st.selectbox("변경 상태", AGENDA_STATUS_OPTIONS, key="agenda_status_new")
        with c3:
            if st.button("안건 상태 변경", type="primary", disabled=not can_edit()):
                idx = agenda_df.index[agenda_df["안건명"] == target_agenda].tolist()
                if idx:
                    agenda_df.loc[idx, "상태"] = new_agenda_status
                    st.session_state.agenda_df = agenda_df
                    save_csv(agenda_df, AGENDA_CSV)
                    st.success("안건 상태가 변경되었습니다.")
                    st.rerun()

# =========================
# Tab 5 전송
# =========================
elif menu == "🤖 최근 등록된 작업 전송":
    st.header("🤖 최근 등록된 작업 전송")
    if not can_edit():
        st.info("조회 권한에서는 전송이 불가합니다. 좌측 '권한 전환'으로 편집 권한 로그인하세요.")

    t1, t2 = st.tabs(["업무 전송", "안건 전송"])

    with t1:
        u = tasks_df[tasks_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u.empty:
            st.info("미전송 업무가 없습니다.")
        else:
            v = u.copy()
            v.insert(0, "전송", False)
            pick = st.data_editor(
                v[["전송","업무명","담당자","팀","상태","시작일","종료일"]],
                use_container_width=True,
                hide_index=True,
                disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            idx = pick.index[pick["전송"] == True].tolist()
            st.write(f"선택된 업무: {len(idx)}개")
            if st.button("🚀 선택 업무 디스코드 전송", type="primary", disabled=(not can_edit() or len(idx)==0)):
                sel = u.iloc[idx].copy()
                fields = [{
                    "name": f"🔹 {r['업무명']} ({r['팀']})",
                    "value": f"👤 담당자: {r['담당자']}\n🏷️ 상태: {r['상태']}\n📅 일정: {r['시작일']} → {r['종료일']}",
                    "inline": False
                } for _, r in sel.iterrows()]
                ok, msg = send_discord(fields, "🔔 신규 업무 알림", "Hallaon Roadmap Bot", color=3447003)
                if ok:
                    sent_ids = set(sel["id"].tolist())
                    tasks_df["sent"] = tasks_df["id"].apply(lambda x: "True" if x in sent_ids or str(tasks_df.loc[tasks_df["id"]==x, "sent"].iloc[0]) == "True" else "False")
                    st.session_state.tasks_df = tasks_df
                    save_csv(tasks_df, TASKS_CSV)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with t2:
        u = agenda_df[agenda_df["sent"].astype(str) != "True"].reset_index(drop=True)
        if u.empty:
            st.info("미전송 안건이 없습니다.")
        else:
            v = u.copy()
            v.insert(0, "전송", False)
            pick = st.data_editor(
                v[["전송","안건명","입안자","팀","상태","입안일"]],
                use_container_width=True,
                hide_index=True,
                disabled=not can_edit(),
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )
            idx = pick.index[pick["전송"] == True].tolist()
            st.write(f"선택된 안건: {len(idx)}개")
            if st.button("📨 선택 안건 디스코드 전송", type="primary", disabled=(not can_edit() or len(idx)==0)):
                sel = u.iloc[idx].copy()
                fields = [{
                    "name": f"🗂️ {r['안건명']} ({r['팀']})",
                    "value": f"👤 입안자: {r['입안자']}\n🏷️ 상태: {r['상태']}\n📅 입안일: {r['입안일']}",
                    "inline": False
                } for _, r in sel.iterrows()]
                ok, msg = send_discord(fields, "📌 신규 안건 알림", "Hallaon Agenda Bot", color=5793266)
                if ok:
                    sent_ids = set(sel["id"].tolist())
                    agenda_df["sent"] = agenda_df["id"].apply(lambda x: "True" if x in sent_ids or str(agenda_df.loc[agenda_df["id"]==x, "sent"].iloc[0]) == "True" else "False")
                    st.session_state.agenda_df = agenda_df
                    save_csv(agenda_df, AGENDA_CSV)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# =========================
# Tab 6 백업/복원
# =========================
elif menu == "🛠️ 백업/복원":
    st.header("🛠️ CSV 백업/복원")
    c1, c2 = st.columns(2)

    with c1:
        st.download_button("업무 CSV 다운로드", data=tasks_df.to_csv(index=False).encode("utf-8-sig"), file_name=f"tasks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")
        st.download_button("안건 CSV 다운로드", data=agenda_df.to_csv(index=False).encode("utf-8-sig"), file_name=f"agenda_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")

    with c2:
        if not can_edit():
            st.info("조회 권한에서는 복원을 사용할 수 없습니다.")
        else:
            up1 = st.file_uploader("업무 CSV 복원", type=["csv"], key="up_tasks")
            if up1 is not None and st.button("업무 CSV 적용"):
                d = pd.read_csv(up1, dtype=str).fillna("")
                d = normalize_tasks_df(d)
                st.session_state.tasks_df = d
                save_csv(d, TASKS_CSV)
                st.success("업무 복원 완료")
                st.rerun()

            up2 = st.file_uploader("안건 CSV 복원", type=["csv"], key="up_agenda")
            if up2 is not None and st.button("안건 CSV 적용"):
                d = pd.read_csv(up2, dtype=str).fillna("")
                d = normalize_agenda_df(d)
                st.session_state.agenda_df = d
                save_csv(d, AGENDA_CSV)
                st.success("안건 복원 완료")
                st.rerun()
