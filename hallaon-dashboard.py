import os
import io
import uuid
import json
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, date, timedelta
from html import escape

st.set_page_config(page_title="Hallaon Workspace", layout="wide")

# =========================
# 설정
# =========================
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")
EDIT_PASSWORD = st.secrets.get("EDIT_PASSWORD", "")
VIEW_PASSWORD = st.secrets.get("VIEW_PASSWORD", "")

TASKS_CSV = "tasks_data.csv"
AGENDA_CSV = "agenda_data.csv"

TEAM_OPTIONS = ["PM", "CD", "FS", "DM", "OPS"]
STATUS_TASK_OPTIONS = ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"]
STATUS_AGENDA_OPTIONS = ["시작 전", "진행 중", "완료", "보류"]

TEAM_COLORS = {"PM": "#4f8cff", "CD": "#ff5c7c", "FS": "#14c9a2", "DM": "#8b6cff", "OPS": "#f5b031"}
STATUS_COLORS = {"완료": "#10c27c", "막힘": "#ef4e4e", "진행 중": "#f5b031", "작업 중": "#f5b031", "대기": "#8b6cff", "시작 전": "#8893a8"}

# =========================
# 스타일 (화이트 버그 강제 방지)
# =========================
st.markdown("""
<style>
:root {
  --bg:#0a1222; --panel:#121d34; --panel2:#162543; --line:#2f4775; --txt:#f4f8ff; --muted:#b5c4e3; --accent:#4f8cff;
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
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover { border-color:#6ca2ff; }

div[data-testid="metric-container"] {
  background: linear-gradient(180deg,#213a69 0%, #1a2f57 100%) !important;
  border:1px solid #4a6aa5 !important;
  border-radius:14px !important;
  box-shadow:0 8px 20px rgba(0,0,0,.25);
}
div[data-testid="metric-container"] * { color:#ffffff !important; }
div[data-testid="stMetricLabel"] p { font-weight:700 !important; letter-spacing:.2px; }
div[data-testid="stMetricValue"] { text-shadow:0 0 10px rgba(79,140,255,.35); }

div[data-testid="stExpander"] details {
  background:#121d34 !important; border:1px solid #2f4775 !important; border-radius:10px !important;
}
div[data-testid="stExpander"] summary {
  background:#121d34 !important; color:#f4f8ff !important; border-radius:10px !important;
}
div[data-testid="stExpander"] details[open] summary {
  border-bottom:1px solid #2f4775 !important; border-radius:10px 10px 0 0 !important;
}

/* DataFrame / DataEditor 화이트 방지 */
div[data-testid="stDataFrame"] [role="grid"] { background:#121d34 !important; }
div[data-testid="stDataFrame"] * { color:#f4f8ff !important; }
div[data-testid="stDataFrame"] button {
  background:#1b2d52 !important; border:1px solid #35558e !important; color:#f4f8ff !important;
}
[data-testid="stDataFrame"] [class*="header"] { background:#1b2d52 !important; color:#f4f8ff !important; }

/* Selectbox/멀티셀렉트/Dropdown 화이트 방지 */
div[data-baseweb="select"] > div {
  background:#121d34 !important; border:1px solid #35558e !important; color:#f4f8ff !important;
}
div[data-baseweb="popover"] ul {
  background:#121d34 !important; border:1px solid #35558e !important;
}
div[data-baseweb="popover"] li {
  background:#121d34 !important; color:#f4f8ff !important;
}
div[data-baseweb="popover"] li[aria-selected="true"] { background:#1f3563 !important; }

input, textarea {
  background:#121d34 !important; color:#f4f8ff !important; border:1px solid #35558e !important;
}
button[kind="primary"] {
  background:linear-gradient(180deg,#5b97ff 0%, #4b87f3 100%) !important;
  color:#fff !important; border:none !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# 유틸
# =========================
def load_df(path: str, cols: list) -> pd.DataFrame:
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str).fillna("")
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols].copy()
    return pd.DataFrame(columns=cols)

def save_df(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)

def today_str():
    return date.today().strftime("%Y-%m-%d")

def safe_date_str(v):
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception:
        return today_str()

def ensure_schema():
    task_cols = ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]
    agenda_cols = ["id","안건명","입안자","팀","상태","입안일","sent"]
    if "tasks_df" not in st.session_state:
        st.session_state.tasks_df = load_df(TASKS_CSV, task_cols)
    if "agenda_df" not in st.session_state:
        st.session_state.agenda_df = load_df(AGENDA_CSV, agenda_cols)

def role_guard():
    if EDIT_PASSWORD == "" and VIEW_PASSWORD == "":
        st.session_state.role = "edit"
        return
    if "role" not in st.session_state:
        st.session_state.role = None
    if st.session_state.role:
        return
    st.title("🔐 로그인")
    mode = st.radio("권한 선택", ["조회", "편집"], horizontal=True)
    pw = st.text_input("비밀번호", type="password")
    if st.button("로그인", type="primary"):
        if mode == "편집" and pw == EDIT_PASSWORD:
            st.session_state.role = "edit"
            st.rerun()
        elif mode == "조회" and pw == VIEW_PASSWORD:
            st.session_state.role = "view"
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

def can_edit():
    return st.session_state.get("role") == "edit"

def discord_send_fields(fields: list, title: str, username: str, color: int = 3447003):
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
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if res.status_code not in (200, 204):
                return False, f"HTTP {res.status_code}: {res.text[:120]}"
            sent += len(batch)
        return True, f"{sent}개 전송 완료"
    except Exception as e:
        return False, str(e)

def team_badge(team):
    t = str(team).split(",")[0].strip() if str(team).strip() else "미지정"
    c = TEAM_COLORS.get(t, "#7b8599")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(t)}</span>"

def status_badge(status):
    s = str(status).strip()
    c = STATUS_COLORS.get(s, "#8893a8")
    return f"<span style='display:inline-block;padding:2px 8px;border-radius:999px;background:{c};color:#fff;font-size:11px;font-weight:700;'>{escape(s)}</span>"

def render_table_html(df, is_task=True):
    if df.empty:
        return "<div style='padding:12px;color:#b5c4e3;'>항목이 없습니다.</div>"
    cols = ["업무명","담당자","팀","상태","시작일","종료일"] if is_task else ["안건명","입안자","팀","상태","입안일"]
    h = """
    <style>
    .tb-wrap{border:1px solid #2f4775;border-radius:10px;overflow:auto;background:#121d34;}
    .tb{width:100%;border-collapse:collapse;min-width:900px;}
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

def render_gantt_monday_style(df):
    if df.empty:
        return "<div style='padding:12px;color:#b5c4e3;'>표시할 업무가 없습니다.</div>"
    g = df.copy()
    g["시작일_dt"] = pd.to_datetime(g["시작일"], errors="coerce")
    g["종료일_dt"] = pd.to_datetime(g["종료일"], errors="coerce")
    g = g.dropna(subset=["시작일_dt","종료일_dt"]).copy()
    if g.empty:
        return "<div style='padding:12px;color:#b5c4e3;'>날짜 데이터가 유효하지 않습니다.</div>"

    min_date = g["시작일_dt"].min().date()
    max_date = g["종료일_dt"].max().date()
    timeline_start = min_date - timedelta(days=min_date.weekday())
    days_total = (max_date - timeline_start).days + 14
    days_total = max(days_total, 35)
    days_total = ((days_total // 7) + 1) * 7
    weeks = days_total // 7
    timeline_end = timeline_start + timedelta(days=days_total)

    step = 1 if weeks <= 12 else 2 if weeks <= 24 else 4

    h = ""
    h += "<style>"
    h += ".gw{background:#101a2f;border:1px solid #2f4775;border-radius:12px;overflow:auto;box-shadow:0 10px 26px rgba(0,0,0,.25);}"
    h += ".gh{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:#13213b;border-bottom:1px solid #2f4775;}"
    h += ".glg{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}"
    h += ".chip{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:7px;background:#1a2c50;border:1px solid #365a95;color:#f4f8ff;font-size:11px;font-weight:700;}"
    h += ".dot{width:8px;height:8px;border-radius:50%;display:inline-block;}"
    h += ".gt{width:100%;min-width:1320px;border-collapse:collapse;table-layout:fixed;}"
    h += ".gt th,.gt td{border-right:1px solid #243a64;border-bottom:1px solid #243a64;color:#f4f8ff;padding:9px 8px;white-space:nowrap;}"
    h += ".gt th{background:#162746;font-size:12px;font-weight:700;}"
    h += ".wkh{min-width:92px;text-align:center;font-size:11px;color:#c9d8f4;}"
    h += ".tl{padding:0 !important;position:relative;background:#101a2f;}"
    h += ".bg{position:absolute;inset:0;display:flex;pointer-events:none;}"
    h += ".bgc{flex:1;border-right:1px solid #243a64;background:linear-gradient(180deg, rgba(255,255,255,.02), rgba(255,255,255,.00));}"
    h += ".bgc:nth-child(even){background:linear-gradient(180deg, rgba(79,140,255,.06), rgba(79,140,255,.02));}"
    h += ".bgc:last-child{border-right:none;}"
    h += ".barw{position:relative;height:44px;display:flex;align-items:center;}"
    h += ".bar{position:absolute;height:24px;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:700;color:#fff;overflow:hidden;text-overflow:ellipsis;box-shadow:0 3px 8px rgba(0,0,0,.28);}"
    h += ".owner{display:inline-flex;align-items:center;gap:7px;}"
    h += ".av{width:21px;height:21px;border-radius:50%;background:#30466d;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;}"
    h += "</style>"

    h += "<div class='gw'>"
    h += "<div class='gh'><div class='glg'>"
    for t, c in TEAM_COLORS.items():
        h += f"<span class='chip'><span class='dot' style='background:{c}'></span>{t}</span>"
    h += "</div><div style='color:#b5c4e3;font-size:12px;font-weight:700;'>간트 차트 (Agile Tools)</div></div>"

    h += "<table class='gt'><thead><tr>"
    h += "<th style='width:72px;text-align:center;'>TEAM</th>"
    h += "<th style='width:230px;'>업무명</th>"
    h += "<th style='width:130px;'>담당자</th>"
    h += "<th style='width:110px;'>상태</th>"
    for i in range(weeks):
        ws = timeline_start + timedelta(days=i * 7)
        full = f"Week {i+1} ({ws.month}/{ws.day}~)"
        txt = full if i % step == 0 else "·"
        h += f"<th class='wkh' title='{full}'>{txt}</th>"
    h += "</tr></thead><tbody>"

    for _, r in g.iterrows():
        team = str(r["팀"]).split(",")[0].strip() if str(r["팀"]).strip() else "미지정"
        owner = str(r["담당자"]).strip() if str(r["담당자"]).strip() else "담당자 미정"
        status = str(r["상태"]).strip()
        task = str(r["업무명"]).strip()

        color = TEAM_COLORS.get(team, "#7b8599")
        s = r["시작일_dt"].date()
        e = r["종료일_dt"].date()
        cs = max(s, timeline_start)
        ce = min(e + timedelta(days=1), timeline_end)
        off = (cs - timeline_start).days
        dur = max((ce - cs).days, 1)
        left = (off / days_total) * 100
        width = (dur / days_total) * 100

        stxt = "✓ Done" if "완료" in status else "Blocked" if "막힘" in status else "In Progress" if ("진행" in status or "작업" in status) else "Scheduled"
        av = owner[0] if owner else "?"
        bg = "".join(["<div class='bgc'></div>" for _ in range(weeks)])

        h += "<tr>"
        h += f"<td style='text-align:center;'>{team_badge(team)}</td>"
        h += f"<td style='font-weight:700;'>{escape(task)}</td>"
        h += f"<td><span class='owner'><span class='av'>{escape(av)}</span>{escape(owner)}</span></td>"
        h += f"<td>{status_badge(status)}</td>"
        h += f"<td colspan='{weeks}' class='tl'><div class='bg'>{bg}</div><div class='barw'><div class='bar' style='left:{left}%;width:{width}%;background:{color};'>{escape(stxt)}</div></div></td>"
        h += "</tr>"

    h += "</tbody></table></div>"
    return h

def export_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")

def validate_task_df(df):
    req = ["id","업무명","담당자","팀","상태","시작일","종료일","sent"]
    return all(c in df.columns for c in req)

def validate_agenda_df(df):
    req = ["id","안건명","입안자","팀","상태","입안일","sent"]
    return all(c in df.columns for c in req)

# =========================
# 초기화 + 권한
# =========================
ensure_schema()
role_guard()

tasks_df = st.session_state.tasks_df.copy()
agenda_df = st.session_state.agenda_df.copy()

# =========================
# 사이드바
# =========================
with st.sidebar:
    st.title("🏛️ Hallaon")
    st.caption(f"권한: {'편집' if can_edit() else '조회'}")
    st.markdown("---")
    menu = st.radio(
        "워크스페이스 메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🗂️ 안건", "🤖 최근 등록된 작업 전송", "🛠️ 백업/복원"]
    )
    st.markdown("---")
    if st.button("로그아웃"):
        st.session_state.role = None
        st.rerun()

# =========================
# 탭 1: 업무
# =========================
if menu == "📋 2026 한라온":
    st.header("📋 2026 한라온")
    st.caption("업무명, 담당자, 팀, 상태, 일정을 직접 관리합니다.")

    if can_edit():
        with st.form("add_task_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                업무명 = st.text_input("업무명")
                담당자 = st.text_input("담당자")
            with c2:
                팀 = st.multiselect("팀", TEAM_OPTIONS, default=["PM"])
                상태 = st.selectbox("상태", STATUS_TASK_OPTIONS, index=0)
            with c3:
                시작일 = st.date_input("시작일", value=date.today())
                종료일 = st.date_input("종료일", value=date.today())
            add_task = st.form_submit_button("업무 추가", type="primary")
        if add_task and 업무명.strip():
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
            save_df(tasks_df, TASKS_CSV)
            st.success("업무가 추가되었습니다.")
            st.rerun()

    if tasks_df.empty:
        st.info("등록된 업무가 없습니다.")
    else:
        todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)].copy()
        done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)].copy()

        with st.expander(f"할 일 ({len(todo_df)}개)", expanded=True):
            st.components.v1.html(render_table_html(todo_df[["업무명","담당자","팀","상태","시작일","종료일"]], is_task=True), height=max(220, len(todo_df)*45 + 90), scrolling=True)

        with st.expander(f"완료됨 ({len(done_df)}개)", expanded=False):
            st.components.v1.html(render_table_html(done_df[["업무명","담당자","팀","상태","시작일","종료일"]], is_task=True), height=max(180, len(done_df)*45 + 90), scrolling=True)

        st.markdown("### 업무 수정/삭제")
        edit_view = tasks_df.copy()
        edit_view.insert(0, "선택", False)

        edited = st.data_editor(
            edit_view[["선택","업무명","담당자","팀","상태","시작일","종료일"]],
            use_container_width=True,
            hide_index=True,
            disabled=not can_edit(),
            column_config={"선택": st.column_config.CheckboxColumn("선택")}
        )

        if can_edit():
            c1, c2 = st.columns(2)
            with c1:
                if st.button("업무 수정사항 저장", type="primary"):
                    base = tasks_df.copy().reset_index(drop=True)
                    base[["업무명","담당자","팀","상태","시작일","종료일"]] = edited[["업무명","담당자","팀","상태","시작일","종료일"]]
                    base["시작일"] = base["시작일"].apply(safe_date_str)
                    base["종료일"] = base["종료일"].apply(safe_date_str)
                    st.session_state.tasks_df = base
                    save_df(base, TASKS_CSV)
                    st.success("업무 수정사항이 저장되었습니다.")
                    st.rerun()
            with c2:
                if st.button("선택 업무 삭제"):
                    idx = edited.index[edited["선택"] == True].tolist()
                    if len(idx) == 0:
                        st.warning("삭제할 업무를 선택하세요.")
                    else:
                        keep = tasks_df.drop(index=idx).reset_index(drop=True)
                        st.session_state.tasks_df = keep
                        save_df(keep, TASKS_CSV)
                        st.success(f"{len(idx)}개 업무를 삭제했습니다.")
                        st.rerun()

# =========================
# 탭 2: 간트
# =========================
elif menu == "📊 간트 차트":
    st.header("📊 간트 차트 (Agile Tools)")
    st.caption("monday.com 스타일에 가깝게 고대비/칩/주차그리드/바를 반영했습니다.")
    st.components.v1.html(render_gantt_monday_style(tasks_df), height=max(700, len(tasks_df)*56 + 230), scrolling=True)

# =========================
# 탭 3: 대시보드
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

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 전체 업무", total)
        c2.metric("⏳ 진행 중", inprog)
        c3.metric("🛑 막힘", stuck)
        c4.metric("✅ 완료", done)

        l, r = st.columns(2)

        with l:
            st.markdown("#### 상태별 분포")
            s = tasks_df["상태"].value_counts().reset_index()
            s.columns = ["상태","개수"]
            fig1 = px.pie(
                s, names="상태", values="개수", hole=0.5, color="상태",
                color_discrete_map={"완료":"#10c27c","막힘":"#ef4e4e","진행 중":"#f5b031","작업 중":"#f5b031","대기":"#8b6cff","시작 전":"#8893a8"}
            )
            fig1.update_traces(textposition="inside", textinfo="percent+label")
            fig1.update_layout(
                template="plotly_dark", height=380, showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig1, use_container_width=True)

        with r:
            st.markdown("#### 담당자별 업무")
            a = tasks_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자","개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#5b97ff"])
            fig2.update_layout(
                template="plotly_dark", height=380,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig2, use_container_width=True)

# =========================
# 탭 4: 안건
# =========================
elif menu == "🗂️ 안건":
    st.header("🗂️ 안건")
    st.caption("안건명, 입안자, 팀, 상태, 입안일을 직접 관리합니다.")

    if can_edit():
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
            상태 = st.selectbox("상태", STATUS_AGENDA_OPTIONS, index=0)
            add_agenda = st.form_submit_button("안건 추가", type="primary")
        if add_agenda and 안건명.strip():
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
            save_df(agenda_df, AGENDA_CSV)
            st.success("안건이 추가되었습니다.")
            st.rerun()

    if agenda_df.empty:
        st.info("등록된 안건이 없습니다.")
    else:
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

        st.components.v1.html(render_table_html(f[["안건명","입안자","팀","상태","입안일"]], is_task=False), height=max(220, len(f)*45 + 90), scrolling=True)

        st.markdown("### 안건 수정/삭제")
        edit_view = agenda_df.copy()
        edit_view.insert(0, "선택", False)

        edited = st.data_editor(
            edit_view[["선택","안건명","입안자","팀","상태","입안일"]],
            use_container_width=True,
            hide_index=True,
            disabled=not can_edit(),
            column_config={"선택": st.column_config.CheckboxColumn("선택")}
        )

        if can_edit():
            c1, c2 = st.columns(2)
            with c1:
                if st.button("안건 수정사항 저장", type="primary"):
                    base = agenda_df.copy().reset_index(drop=True)
                    base[["안건명","입안자","팀","상태","입안일"]] = edited[["안건명","입안자","팀","상태","입안일"]]
                    base["입안일"] = base["입안일"].apply(safe_date_str)
                    st.session_state.agenda_df = base
                    save_df(base, AGENDA_CSV)
                    st.success("안건 수정사항이 저장되었습니다.")
                    st.rerun()
            with c2:
                if st.button("선택 안건 삭제"):
                    idx = edited.index[edited["선택"] == True].tolist()
                    if len(idx) == 0:
                        st.warning("삭제할 안건을 선택하세요.")
                    else:
                        keep = agenda_df.drop(index=idx).reset_index(drop=True)
                        st.session_state.agenda_df = keep
                        save_df(keep, AGENDA_CSV)
                        st.success(f"{len(idx)}개 안건을 삭제했습니다.")
                        st.rerun()

# =========================
# 탭 5: 전송 (업무/안건 분리)
# =========================
elif menu == "🤖 최근 등록된 작업 전송":
    st.header("🤖 최근 등록된 작업 전송")
    t1, t2 = st.tabs(["업무 전송", "안건 전송"])

    with t1:
        unsent_t = tasks_df[tasks_df["sent"].astype(str) != "True"].copy().reset_index(drop=True)
        if unsent_t.empty:
            st.info("미전송 업무가 없습니다.")
        else:
            send_view = unsent_t.copy()
            send_view.insert(0, "전송", False)
            pick = st.data_editor(
                send_view[["전송","업무명","담당자","팀","상태","시작일","종료일"]],
                use_container_width=True,
                hide_index=True,
                column_config={"전송": st.column_config.CheckboxColumn("전송")},
                disabled=not can_edit()
            )
            idx = pick.index[pick["전송"] == True].tolist()
            st.write(f"선택된 업무: {len(idx)}개")
            if st.button("🚀 선택 업무 디스코드 전송", type="primary", disabled=(len(idx)==0 or not can_edit())):
                selected = unsent_t.iloc[idx].copy()
                fields = []
                for _, r in selected.iterrows():
                    fields.append({
                        "name": f"🔹 {r['업무명']} ({r['팀']})",
                        "value": f"👤 담당자: {r['담당자']}\n🏷️ 상태: {r['상태']}\n📅 일정: {r['시작일']} → {r['종료일']}",
                        "inline": False
                    })
                ok, msg = discord_send_fields(fields, "🔔 신규 업무 알림", "Hallaon Roadmap Bot", color=3447003)
                if ok:
                    sent_ids = set(selected["id"].tolist())
                    tasks_df["sent"] = tasks_df["id"].apply(lambda x: "True" if x in sent_ids or str(tasks_df.loc[tasks_df['id']==x, 'sent'].iloc[0])=="True" else "False")
                    st.session_state.tasks_df = tasks_df
                    save_df(tasks_df, TASKS_CSV)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with t2:
        unsent_a = agenda_df[agenda_df["sent"].astype(str) != "True"].copy().reset_index(drop=True)
        if unsent_a.empty:
            st.info("미전송 안건이 없습니다.")
        else:
            send_view = unsent_a.copy()
            send_view.insert(0, "전송", False)
            pick = st.data_editor(
                send_view[["전송","안건명","입안자","팀","상태","입안일"]],
                use_container_width=True,
                hide_index=True,
                column_config={"전송": st.column_config.CheckboxColumn("전송")},
                disabled=not can_edit()
            )
            idx = pick.index[pick["전송"] == True].tolist()
            st.write(f"선택된 안건: {len(idx)}개")
            if st.button("📨 선택 안건 디스코드 전송", type="primary", disabled=(len(idx)==0 or not can_edit())):
                selected = unsent_a.iloc[idx].copy()
                fields = []
                for _, r in selected.iterrows():
                    fields.append({
                        "name": f"🗂️ {r['안건명']} ({r['팀']})",
                        "value": f"👤 입안자: {r['입안자']}\n🏷️ 상태: {r['상태']}\n📅 입안일: {r['입안일']}",
                        "inline": False
                    })
                ok, msg = discord_send_fields(fields, "📌 신규 안건 알림", "Hallaon Agenda Bot", color=5793266)
                if ok:
                    sent_ids = set(selected["id"].tolist())
                    agenda_df["sent"] = agenda_df["id"].apply(lambda x: "True" if x in sent_ids or str(agenda_df.loc[agenda_df['id']==x, 'sent'].iloc[0])=="True" else "False")
                    st.session_state.agenda_df = agenda_df
                    save_df(agenda_df, AGENDA_CSV)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# =========================
# 탭 6: 백업/복원/내보내기
# =========================
elif menu == "🛠️ 백업/복원":
    st.header("🛠️ CSV 백업/복원")
    st.caption("업무/안건 CSV 내보내기, 업로드 복원을 지원합니다.")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 내보내기")
        st.download_button("업무 CSV 다운로드", data=export_csv_bytes(tasks_df), file_name=f"tasks_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")
        st.download_button("안건 CSV 다운로드", data=export_csv_bytes(agenda_df), file_name=f"agenda_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")

    with c2:
        st.markdown("### 복원")
        if can_edit():
            up_task = st.file_uploader("업무 CSV 복원", type=["csv"], key="up_task")
            if up_task is not None and st.button("업무 CSV 적용"):
                df = pd.read_csv(up_task, dtype=str).fillna("")
                if validate_task_df(df):
                    st.session_state.tasks_df = df
                    save_df(df, TASKS_CSV)
                    st.success("업무 CSV 복원이 완료되었습니다.")
                    st.rerun()
                else:
                    st.error("업무 CSV 스키마가 올바르지 않습니다.")
            up_agenda = st.file_uploader("안건 CSV 복원", type=["csv"], key="up_agenda")
            if up_agenda is not None and st.button("안건 CSV 적용"):
                df = pd.read_csv(up_agenda, dtype=str).fillna("")
                if validate_agenda_df(df):
                    st.session_state.agenda_df = df
                    save_df(df, AGENDA_CSV)
                    st.success("안건 CSV 복원이 완료되었습니다.")
                    st.rerun()
                else:
                    st.error("안건 CSV 스키마가 올바르지 않습니다.")
        else:
            st.info("조회 권한에서는 복원을 사용할 수 없습니다.")
