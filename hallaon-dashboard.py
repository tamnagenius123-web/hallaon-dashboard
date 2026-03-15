import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px
from html import escape

st.set_page_config(page_title="Hallaon Workspace", layout="wide")

# =========================
# Secrets (반드시 Streamlit secrets 사용)
# =========================
# .streamlit/secrets.toml 예시:


NOTION_TOKEN = st.secrets.get("NOTION_TOKEN", "")
MAIN_DATABASE_ID = st.secrets.get("MAIN_DATABASE_ID", "")
AGENDA_DATABASE_ID = st.secrets.get("AGENDA_DATABASE_ID", "")
DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")

if not NOTION_TOKEN or not MAIN_DATABASE_ID:
    st.error("secrets 설정이 필요합니다. NOTION_TOKEN / MAIN_DATABASE_ID를 등록하세요.")
    st.stop()

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# =========================
# CSS
# =========================
st.markdown("""
<style>
:root {
  --bg: #0f1117;
  --panel: #151926;
  --card: #1b2130;
  --line: #2a3145;
  --text: #f3f5f8;
  --muted: #a7b0c0;
  --accent: #4f8cff;
}
.stApp { background: var(--bg); color: var(--text); }
h1, h2, h3, h4, h5, h6, p, div, span, label { color: var(--text); }
small, .caption, [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #141824 0%, #111522 100%);
  border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] * {
  color: #e8edf7 !important;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label {
  background: #1a2030;
  border: 1px solid #2c3550;
  border-radius: 10px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
section[data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
  border-color: #4f8cff;
}

div[data-testid="metric-container"] {
  background: linear-gradient(180deg, #1b2130 0%, #171d2a 100%) !important;
  border: 1px solid #2a3145 !important;
  border-radius: 12px;
  padding: 14px 16px;
}
div[data-testid="metric-container"] * { color: #ffffff !important; }

.block-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px;
}
</style>
""", unsafe_allow_html=True)

# =========================
# Utils
# =========================
def parse_iso_date(date_str):
    if not date_str:
        return None
    s = str(date_str).replace("Z", "+00:00")
    try:
        if "T" in s:
            return datetime.fromisoformat(s).date()
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def get_title(props, keys=("작업 이름", "안건명", "Name", "이름", "제목")):
    for k in keys:
        p = props.get(k, {})
        t = p.get("title", [])
        if t:
            return t[0].get("plain_text", "이름 없음")
    return "이름 없음"

def get_status(props, keys=("상태", "Status")):
    for k in keys:
        p = props.get(k, {})
        s = p.get("status", {})
        n = s.get("name")
        if n:
            return n
        sel = p.get("select", {})
        if sel and sel.get("name"):
            return sel["name"]
    return "시작 전"

def get_multi_select(props, keys=("팀", "Team")):
    for k in keys:
        p = props.get(k, {})
        arr = p.get("multi_select", [])
        if arr:
            return [x.get("name", "미지정") for x in arr]
    return ["미지정"]

def get_people(props, keys=("담당자", "임안자", "Owner", "Assignee")):
    for k in keys:
        p = props.get(k, {})
        ppl = p.get("people", [])
        if ppl:
            names = [x.get("name", "알 수 없음") for x in ppl]
            return ", ".join(names)
    return "담당자 미정"

def get_date_range(props, keys=("마감일", "타임라인", "날짜", "Date")):
    for k in keys:
        p = props.get(k, {})
        d = p.get("date")
        if d:
            s = parse_iso_date(d.get("start"))
            e = parse_iso_date(d.get("end")) if d.get("end") else s
            if s is None:
                continue
            if e is None:
                e = s
            return s, e
    today = datetime.now().date()
    return today, today

def notion_query_all(database_id):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    all_rows = []
    has_more = True
    cursor = None
    while has_more:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(url, headers=headers, json=payload, timeout=20)
        if r.status_code != 200:
            try:
                msg = r.json().get("message", "unknown error")
            except Exception:
                msg = r.text
            raise RuntimeError(f"Notion API 오류: {msg}")
        j = r.json()
        all_rows.extend(j.get("results", []))
        has_more = j.get("has_more", False)
        cursor = j.get("next_cursor")
    return all_rows

@st.cache_data(ttl=60)
def fetch_main_data():
    raw = notion_query_all(MAIN_DATABASE_ID)
    rows = []
    for item in raw:
        props = item.get("properties", {})
        page_id = item.get("id", "")
        name = get_title(props, ("작업 이름", "Name", "이름", "제목"))
        status = get_status(props)
        teams = get_multi_select(props)
        owner = get_people(props)
        s, e = get_date_range(props)
        display_end = e + timedelta(days=1)
        timeline = f"{s.strftime('%Y-%m-%d')} → {e.strftime('%Y-%m-%d')}"
        created = parse_iso_date(item.get("created_time"))
        for team in teams:
            rows.append({
                "page_id": page_id,
                "작업명": name,
                "담당자": owner,
                "팀": team,
                "상태": status,
                "시작일": s,
                "종료일": display_end,
                "타임라인": timeline,
                "생성일": created
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=120)
def fetch_agenda_data():
    raw = notion_query_all(AGENDA_DATABASE_ID)
    rows = []
    for item in raw:
        props = item.get("properties", {})
        name = get_title(props, ("안건명", "작업 이름", "Name", "이름", "제목"))
        team = ", ".join(get_multi_select(props))
        owner = get_people(props, ("임안자", "담당자", "Owner", "Assignee"))
        s, e = get_date_range(props, ("임안일", "마감일", "날짜", "Date"))
        rows.append({
            "안건명": name,
            "팀": team,
            "임안자": owner,
            "임안일": s.strftime("%m/%d/%Y"),
            "상태": get_status(props)
        })
    return pd.DataFrame(rows)

def build_display_df(df):
    if df.empty:
        return pd.DataFrame()
    g = df.groupby(
        ["page_id", "작업명", "담당자", "상태", "타임라인", "시작일", "종료일", "생성일"],
        as_index=False
    ).agg({"팀": lambda x: ", ".join(sorted(set(map(str, x))))})
    return g.sort_values(["생성일", "시작일"], ascending=[False, True]).reset_index(drop=True)

def render_notion_table(df_subset):
    if df_subset.empty:
        return "<div style='color:#9ca3af;padding:10px;font-size:14px;'>항목이 없습니다.</div>"
    html = """
    <style>
    .n-wrap{background:transparent;}
    .n-table{width:100%;border-collapse:collapse;text-align:left;font-family:Inter,sans-serif;}
    .n-table th{background:#1d2434;color:#aab5c9;font-size:12px;font-weight:600;padding:11px 14px;border-bottom:1px solid #2d3650;border-right:1px solid #2d3650;}
    .n-table td{padding:11px 14px;border-bottom:1px solid #2d3650;border-right:1px solid #2d3650;font-size:14px;color:#e6ebf5;background:#141b2b;}
    .n-table th:last-child,.n-table td:last-child{border-right:none;}
    .n-table tr:hover td{background:#182134;}
    .tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:600;}
    .tag-blue{background:#dbeafe;color:#1e40af;}
    .tag-green{background:#dcfce7;color:#166534;}
    .tag-yellow{background:#fef3c7;color:#92400e;}
    .tag-red{background:#fee2e2;color:#991b1b;}
    .tag-purple{background:#ede9fe;color:#5b21b6;}
    .tag-gray{background:#e5e7eb;color:#374151;}
    .owner{display:flex;align-items:center;gap:7px;}
    .av{width:22px;height:22px;border-radius:50%;background:#334155;color:#f8fafc;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;}
    </style>
    <div class="n-wrap"><table class="n-table"><thead><tr>
    <th style="width:280px;">태스크</th><th style="width:120px;">소유자</th><th style="width:120px;">상태</th><th style="width:90px;">팀</th><th>타임라인</th>
    </tr></thead><tbody>
    """
    for _, r in df_subset.iterrows():
        task = escape(str(r["작업명"]))
        owner = escape(str(r["담당자"]))
        status = escape(str(r["상태"]))
        team = str(r["팀"])
        first_team = escape(team.split(", ")[0] if ", " in team else team)
        tl = escape(str(r["타임라인"]))
        sc = "tag-gray"
        if "완료" in status:
            sc = "tag-green"
        elif ("작업" in status) or ("진행" in status):
            sc = "tag-yellow"
        elif "막힘" in status:
            sc = "tag-red"
        elif "대기" in status:
            sc = "tag-purple"
        tc = "tag-blue" if first_team == "PM" else "tag-red" if first_team == "CD" else "tag-green" if first_team == "FS" else "tag-purple" if first_team == "DM" else "tag-yellow"
        av = escape(owner[0]) if owner else "?"
        html += f"""
        <tr>
          <td style="font-weight:600;">{task}</td>
          <td><div class="owner"><div class="av">{av}</div><span>{owner}</span></div></td>
          <td><span class="tag {sc}">{status}</span></td>
          <td><span class="tag {tc}">{first_team}</span></td>
          <td>📅 {tl}</td>
        </tr>
        """
    html += "</tbody></table></div>"
    return html

def render_gantt_html(display_df):
    if display_df.empty:
        return "<div style='padding:12px;color:#9ca3af;'>표시할 일정이 없습니다.</div>"
    min_date = display_df["시작일"].min()
    max_date = display_df["종료일"].max()
    timeline_start = min_date - timedelta(days=min_date.weekday())
    days_total = (max_date - timeline_start).days + 14
    days_total = max(days_total, 35)
    days_total = ((days_total // 7) + 1) * 7
    total_weeks = days_total // 7
    timeline_end = timeline_start + timedelta(days=days_total)

    # week 라벨 뭉개짐 방지: 라벨 간격(step) 조절
    step = 1 if total_weeks <= 12 else 2 if total_weeks <= 24 else 4

    h = ""
    h += "<style>"
    h += ".gw{background:#141b2b;border:1px solid #2d3650;border-radius:10px;overflow:auto;}"
    h += ".gt{width:100%;min-width:1200px;border-collapse:collapse;table-layout:fixed;}"
    h += ".gt th,.gt td{border-bottom:1px solid #2d3650;border-right:1px solid #2d3650;padding:10px 10px;white-space:nowrap;font-size:12px;color:#e6ebf5;}"
    h += ".gt th:last-child,.gt td:last-child{border-right:none;}"
    h += ".gt th{background:#1b2438;color:#aeb8cb;font-weight:700;}"
    h += ".wk{min-width:84px;text-align:center;font-size:11px;line-height:1.2;letter-spacing:.1px;}"
    h += ".tl{padding:0 !important;position:relative;}"
    h += ".bg{position:absolute;inset:0;display:flex;pointer-events:none;}"
    h += ".col{flex:1;border-right:1px solid #2d3650;}"
    h += ".col:last-child{border-right:none;}"
    h += ".barw{position:relative;height:44px;display:flex;align-items:center;}"
    h += ".bar{position:absolute;height:24px;border-radius:6px;display:flex;align-items:center;padding:0 8px;font-size:11px;font-weight:700;color:white;overflow:hidden;text-overflow:ellipsis;}"
    h += ".badge{padding:3px 8px;border-radius:999px;font-weight:700;color:white;font-size:11px;display:inline-block;}"
    h += "</style>"
    h += "<div class='gw'><table class='gt'><thead><tr>"
    h += "<th style='width:70px;text-align:center;'>TEAM</th><th style='width:220px;'>TASK</th><th style='width:130px;'>OWNER</th><th style='width:110px;'>STATUS</th>"
    for i in range(total_weeks):
        ws = timeline_start + timedelta(days=i * 7)
        full = f"Week {i+1} ({ws.month}/{ws.day})"
        txt = full if (i % step == 0) else "·"
        h += f"<th class='wk' title='{full}'>{txt}</th>"
    h += "</tr></thead><tbody>"

    for _, r in display_df.iterrows():
        team_str = str(r["팀"])
        first_team = team_str.split(", ")[0] if ", " in team_str else team_str
        task = escape(str(r["작업명"]))
        owner = escape(str(r["담당자"]))
        status = escape(str(r["상태"]))
        s = r["시작일"]
        e = r["종료일"]
        color = {"PM":"#3b82f6","CD":"#ef4444","FS":"#10b981","DM":"#8b5cf6","OPS":"#eab308"}.get(first_team, "#6b7280")
        cs = max(s, timeline_start)
        ce = min(e, timeline_end)
        off = (cs - timeline_start).days
        dur = max((ce - cs).days, 1)
        left = (off / days_total) * 100
        wid = (dur / days_total) * 100
        bg = "".join(["<div class='col'></div>" for _ in range(total_weeks)])
        bar_txt = "✓ Done" if "완료" in status else "In Progress" if ("진행" in status or "작업" in status) else "Scheduled"

        h += "<tr>"
        h += f"<td style='text-align:center;'><span class='badge' style='background:{color};'>{escape(first_team)}</span></td>"
        h += f"<td style='font-weight:600;'>{task}</td>"
        h += f"<td>{owner}</td>"
        h += f"<td>{status}</td>"
        h += f"<td colspan='{total_weeks}' class='tl'><div class='bg'>{bg}</div><div class='barw'><div class='bar' style='left:{left}%;width:{wid}%;background:{color};'>{bar_txt}</div></div></td>"
        h += "</tr>"

    h += "</tbody></table></div>"
    return h

# =========================
# Data
# =========================
try:
    df = fetch_main_data()
except Exception as e:
    st.error(str(e))
    st.stop()

display_df = build_display_df(df)

if "sent_to_discord_ids" not in st.session_state:
    st.session_state.sent_to_discord_ids = set()

# =========================
# Sidebar
# =========================
with st.sidebar:
    st.title("🏛️ Hallaon")
    st.markdown("---")
    menu = st.radio(
        "워크스페이스 메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🗂️ 안건", "🤖 최근 등록된 작업 전송"]
    )
    st.markdown("---")
    st.caption("2026 Hallaon Agile System")

# =========================
# Main Views
# =========================
if display_df.empty and menu != "🗂️ 안건":
    st.info("데이터가 없습니다. Notion DB 연결/속성을 확인해 주세요.")
else:
    if menu == "📋 2026 한라온":
        st.header("📋 2026 한라온")
        st.caption("할 일과 완료됨을 접기/펼치기로 관리할 수 있습니다.")

        todo_df = display_df[display_df["상태"].str.contains("시작 전|대기|진행|작업|막힘", na=False)]
        done_df = display_df[display_df["상태"].str.contains("완료", na=False)]

        with st.expander(f"할 일 ({len(todo_df)}개)", expanded=True):
            st.components.v1.html(render_notion_table(todo_df), height=max(220, len(todo_df) * 52 + 70), scrolling=True)

        with st.expander(f"완료됨 ({len(done_df)}개)", expanded=False):
            st.components.v1.html(render_notion_table(done_df), height=max(180, len(done_df) * 52 + 70), scrolling=True)

    elif menu == "📊 간트 차트":
        st.header("📊 프로젝트 간트 차트")
        st.caption("반응형에서 week 라벨 뭉개짐을 줄이기 위해 라벨 밀도 조절을 적용했습니다.")
        g_html = render_gantt_html(display_df)
        st.components.v1.html(g_html, height=max(430, len(display_df) * 50 + 120), scrolling=True)

    elif menu == "📈 대시보드":
        st.header("📈 2026 한라온 종합 대시보드")

        total_tasks = len(display_df)
        in_progress = len(display_df[display_df["상태"].str.contains("진행|작업", na=False)])
        stuck = len(display_df[display_df["상태"].str.contains("막힘", na=False)])
        done = len(display_df[display_df["상태"].str.contains("완료", na=False)])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 모든 태스크", total_tasks)
        c2.metric("⏳ 진행 중", in_progress)
        c3.metric("🛑 막힘", stuck)
        c4.metric("✅ 완료", done)

        left, right = st.columns(2)

        with left:
            st.markdown("##### 상태별 태스크")
            status_counts = display_df["상태"].value_counts().reset_index()
            status_counts.columns = ["상태", "개수"]
            fig_pie = px.pie(
                status_counts,
                names="상태",
                values="개수",
                hole=0.45,
                color="상태",
                color_discrete_map={"완료":"#22c55e", "막힘":"#ef4444", "시작 전":"#6b7280", "작업 중":"#f59e0b", "진행 중":"#f59e0b", "대기":"#8b5cf6"}
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            fig_pie.update_layout(template="plotly_dark", height=360, margin=dict(t=10, b=10, l=10, r=10), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True)

        with right:
            st.markdown("##### 담당자별 태스크")
            assignee_counts = display_df["담당자"].value_counts().reset_index()
            assignee_counts.columns = ["담당자", "개수"]
            fig_bar = px.bar(assignee_counts, x="담당자", y="개수", text_auto=True, color_discrete_sequence=["#4f8cff"])
            fig_bar.update_layout(template="plotly_dark", height=360, margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar, use_container_width=True)

    elif menu == "🗂️ 안건":
        st.header("🗂️ 안건")
        st.caption("Notion 안건 DB를 불러와 게시합니다.")
        try:
            agenda_df = fetch_agenda_data()
        except Exception as e:
            st.error(f"안건 DB 조회 실패: {e}")
            st.stop()

        if agenda_df.empty:
            st.info("안건 데이터가 없습니다.")
        else:
            st.dataframe(agenda_df, use_container_width=True, hide_index=True)

    elif menu == "🤖 최근 등록된 작업 전송":
        st.header("🤖 최근 등록된 작업 전송")
        st.caption("미전송 작업을 선택해서 디스코드로 전송할 수 있습니다.")

        if not DISCORD_WEBHOOK_URL:
            st.warning("DISCORD_WEBHOOK_URL이 secrets에 설정되지 않았습니다.")
            st.stop()

        unsent = display_df[~display_df["page_id"].isin(st.session_state.sent_to_discord_ids)].copy()

        if unsent.empty:
            st.info("현재 미전송 작업이 없습니다.")
        else:
            unsent = unsent.sort_values(["생성일", "시작일"], ascending=[False, True]).reset_index(drop=True)
            unsent.insert(0, "전송", False)

            edited = st.data_editor(
                unsent[["전송", "page_id", "작업명", "담당자", "상태", "팀", "타임라인"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "전송": st.column_config.CheckboxColumn("전송"),
                    "page_id": st.column_config.TextColumn("ID", disabled=True),
                    "작업명": st.column_config.TextColumn("작업명", disabled=True),
                    "담당자": st.column_config.TextColumn("담당자", disabled=True),
                    "상태": st.column_config.TextColumn("상태", disabled=True),
                    "팀": st.column_config.TextColumn("팀", disabled=True),
                    "타임라인": st.column_config.TextColumn("타임라인", disabled=True),
                }
            )

            selected = edited[edited["전송"] == True].copy()
            st.write(f"선택됨: {len(selected)}개")

            if st.button("🚀 선택 작업 디스코드로 전송", type="primary", disabled=(len(selected) == 0)):
                fields = []
                for _, t in selected.iterrows():
                    fields.append({
                        "name": f"🔹 {t['작업명']} ({t['팀']})",
                        "value": f"👤 담당: {t['담당자']}\n📅 기간: {t['타임라인']} | 🏷️ 상태: {t['상태']}",
                        "inline": False
                    })

                ok_ids = []
                for i in range(0, len(fields), 25):
                    batch_fields = fields[i:i+25]
                    payload = {
                        "username": "Hallaon Roadmap Bot",
                        "embeds": [{
                            "title": "🔔 새 작업 알림",
                            "color": 3447003,
                            "fields": batch_fields,
                            "footer": {"text": f"Hallaon Agile Dashboard • {len(batch_fields)}개"}
                        }]
                    }
                    try:
                        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
                    except Exception as e:
                        st.error(f"전송 오류: {e}")
                        break

                    if res.status_code in (200, 204):
                        s = i
                        e = i + len(batch_fields)
                        ids = selected.iloc[s:e]["page_id"].tolist()
                        ok_ids.extend(ids)
                    else:
                        st.error(f"전송 실패: HTTP {res.status_code} / {res.text[:200]}")
                        break
                else:
                    st.session_state.sent_to_discord_ids.update(ok_ids)
                    st.success(f"{len(ok_ids)}개 작업 전송 완료")
                    st.rerun()
