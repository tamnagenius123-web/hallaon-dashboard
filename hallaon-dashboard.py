import os
import uuid
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import date

st.set_page_config(page_title="Hallaon Workspace", layout="wide")

DISCORD_WEBHOOK_URL = st.secrets.get("DISCORD_WEBHOOK_URL", "")

TASKS_CSV = "tasks_data.csv"
AGENDA_CSV = "agenda_data.csv"

st.markdown("""
<style>
.stApp { background: #0b1220; color: #e6edf7; }
section[data-testid="stSidebar"] {
  background: #121a2b;
  border-right: 1px solid #2b3550;
}
section[data-testid="stSidebar"] * { color: #e6edf7 !important; }

div[data-testid="metric-container"] {
  background: #141f34 !important;
  border: 1px solid #2b3c62 !important;
  border-radius: 12px !important;
}

/* Expander 다크 */
div[data-testid="stExpander"] details {
  background: #121a2b !important;
  border: 1px solid #2b3550 !important;
  border-radius: 10px !important;
}
div[data-testid="stExpander"] summary {
  background: #121a2b !important;
  color: #e6edf7 !important;
}

/* Dataframe/DataEditor 다크 */
div[data-testid="stDataFrame"] [role="grid"] {
  background: #121a2b !important;
}
div[data-testid="stDataFrame"] * {
  color: #e6edf7 !important;
}

/* Selectbox/Dropdown 흰색 버그 수정 */
div[data-baseweb="select"] > div {
  background: #121a2b !important;
  border: 1px solid #30466d !important;
  color: #e6edf7 !important;
}
div[data-baseweb="popover"] ul {
  background: #121a2b !important;
  border: 1px solid #30466d !important;
}
div[data-baseweb="popover"] li {
  background: #121a2b !important;
  color: #e6edf7 !important;
}
div[data-baseweb="popover"] li[aria-selected="true"] {
  background: #1b2a47 !important;
}
</style>
""", unsafe_allow_html=True)

def load_df(path, cols):
    if os.path.exists(path):
        df = pd.read_csv(path)
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols]
    return pd.DataFrame(columns=cols)

def save_df(df, path):
    df.to_csv(path, index=False)

def send_discord(fields, title, username):
    if not DISCORD_WEBHOOK_URL:
        return False, "DISCORD_WEBHOOK_URL이 secrets에 없습니다."
    try:
        for i in range(0, len(fields), 25):
            batch = fields[i:i+25]
            payload = {
                "username": username,
                "embeds": [{
                    "title": title,
                    "color": 3447003,
                    "fields": batch
                }]
            }
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
            if r.status_code not in (200, 204):
                return False, f"HTTP {r.status_code}"
        return True, "전송 완료"
    except Exception as e:
        return False, str(e)

task_cols = ["id", "작업명", "담당자", "팀", "상태", "시작일", "종료일", "sent"]
agenda_cols = ["id", "안건명", "팀", "입안자", "입안일", "상태", "sent"]

if "tasks_df" not in st.session_state:
    st.session_state.tasks_df = load_df(TASKS_CSV, task_cols)
if "agenda_df" not in st.session_state:
    st.session_state.agenda_df = load_df(AGENDA_CSV, agenda_cols)

tasks_df = st.session_state.tasks_df.copy()
agenda_df = st.session_state.agenda_df.copy()

with st.sidebar:
    st.title("🏛️ Hallaon")
    st.markdown("---")
    menu = st.radio(
        "워크스페이스 메뉴",
        ["📋 2026 한라온", "📊 간트 차트", "📈 대시보드", "🗂️ 안건", "🤖 최근 등록된 작업 전송"]
    )
    st.markdown("---")
    st.caption("Local Agile Board")

if menu == "📋 2026 한라온":
    st.header("📋 2026 한라온")
    st.caption("노션 없이 이 페이지에서 직접 등록/수정합니다.")

    with st.form("add_task_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            task_name = st.text_input("작업명")
            owner = st.text_input("담당자")
        with c2:
            team = st.multiselect("팀", ["PM", "CD", "FS", "DM", "OPS"], default=["PM"])
            status = st.selectbox("상태", ["시작 전", "대기", "진행 중", "작업 중", "막힘", "완료"], index=0)
        with c3:
            start_d = st.date_input("시작일", value=date.today())
            end_d = st.date_input("종료일", value=date.today())
        submit = st.form_submit_button("작업 추가", type="primary")

    if submit and task_name.strip():
        new_row = {
            "id": str(uuid.uuid4()),
            "작업명": task_name.strip(),
            "담당자": owner.strip() if owner.strip() else "담당자 미정",
            "팀": ", ".join(team) if team else "미지정",
            "상태": status,
            "시작일": pd.to_datetime(start_d).strftime("%Y-%m-%d"),
            "종료일": pd.to_datetime(end_d).strftime("%Y-%m-%d"),
            "sent": False
        }
        tasks_df = pd.concat([tasks_df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.tasks_df = tasks_df
        save_df(tasks_df, TASKS_CSV)
        st.success("작업이 추가되었습니다.")
        st.rerun()

    if tasks_df.empty:
        st.info("등록된 작업이 없습니다.")
    else:
        todo_df = tasks_df[~tasks_df["상태"].str.contains("완료", na=False)].copy()
        done_df = tasks_df[tasks_df["상태"].str.contains("완료", na=False)].copy()

        with st.expander(f"할 일 ({len(todo_df)}개)", expanded=True):
            st.dataframe(todo_df[["작업명", "담당자", "상태", "팀", "시작일", "종료일"]], use_container_width=True, hide_index=True)

        with st.expander(f"완료됨 ({len(done_df)}개)", expanded=False):
            st.dataframe(done_df[["작업명", "담당자", "상태", "팀", "시작일", "종료일"]], use_container_width=True, hide_index=True)

        st.markdown("#### 작업 수정")
        edit_df = tasks_df.copy()
        edited = st.data_editor(
            edit_df[["작업명", "담당자", "팀", "상태", "시작일", "종료일"]],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )
        if st.button("작업 수정사항 저장"):
            base = tasks_df.copy()
            if len(edited) == len(base):
                base[["작업명", "담당자", "팀", "상태", "시작일", "종료일"]] = edited
                st.session_state.tasks_df = base
                save_df(base, TASKS_CSV)
                st.success("저장되었습니다.")
                st.rerun()
            else:
                st.warning("행 개수 변경은 추가 폼을 사용하세요.")

elif menu == "📊 간트 차트":
    st.header("📊 프로젝트 간트 차트")
    if tasks_df.empty:
        st.info("작업 데이터가 없습니다.")
    else:
        g = tasks_df.copy()
        g["시작일"] = pd.to_datetime(g["시작일"], errors="coerce")
        g["종료일"] = pd.to_datetime(g["종료일"], errors="coerce") + pd.Timedelta(days=1)
        g = g.dropna(subset=["시작일", "종료일"])
        if g.empty:
            st.info("표시 가능한 날짜 데이터가 없습니다.")
        else:
            fig = px.timeline(
                g,
                x_start="시작일",
                x_end="종료일",
                y="작업명",
                color="팀",
                hover_data=["담당자", "상태"]
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(
                template="plotly_dark",
                height=760,
                margin=dict(t=20, b=20, l=20, r=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)

elif menu == "📈 대시보드":
    st.header("📈 2026 한라온 종합 대시보드")
    if tasks_df.empty:
        st.info("작업 데이터가 없습니다.")
    else:
        total = len(tasks_df)
        in_prog = len(tasks_df[tasks_df["상태"].str.contains("진행|작업", na=False)])
        stuck = len(tasks_df[tasks_df["상태"].str.contains("막힘", na=False)])
        done = len(tasks_df[tasks_df["상태"].str.contains("완료", na=False)])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 모든 태스크", total)
        c2.metric("⏳ 진행 중", in_prog)
        c3.metric("🛑 막힘", stuck)
        c4.metric("✅ 완료", done)

        l, r = st.columns(2)
        with l:
            st.markdown("##### 상태별 태스크")
            s = tasks_df["상태"].value_counts().reset_index()
            s.columns = ["상태", "개수"]
            fig1 = px.pie(s, names="상태", values="개수", hole=0.45)
            fig1.update_layout(template="plotly_dark", height=360, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig1, use_container_width=True)

        with r:
            st.markdown("##### 담당자별 태스크")
            a = tasks_df["담당자"].value_counts().reset_index()
            a.columns = ["담당자", "개수"]
            fig2 = px.bar(a, x="담당자", y="개수", text_auto=True)
            fig2.update_layout(template="plotly_dark", height=360, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

elif menu == "🗂️ 안건":
    st.header("🗂️ 안건")
    st.caption("안건도 이 페이지에서 바로 등록/관리합니다.")

    with st.form("add_agenda_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            agenda_name = st.text_input("안건명")
        with c2:
            ag_team = st.multiselect("팀", ["PM", "CD", "FS", "DM", "OPS"], default=["PM"])
        with c3:
            proposer = st.text_input("입안자")
        with c4:
            agenda_date = st.date_input("입안일", value=date.today())
        ag_status = st.selectbox("상태", ["시작 전", "진행 중", "완료", "보류"], index=0)
        ag_submit = st.form_submit_button("안건 추가", type="primary")

    if ag_submit and agenda_name.strip():
        new_row = {
            "id": str(uuid.uuid4()),
            "안건명": agenda_name.strip(),
            "팀": ", ".join(ag_team) if ag_team else "미지정",
            "입안자": proposer.strip() if proposer.strip() else "담당자 미정",
            "입안일": pd.to_datetime(agenda_date).strftime("%Y-%m-%d"),
            "상태": ag_status,
            "sent": False
        }
        agenda_df = pd.concat([agenda_df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.agenda_df = agenda_df
        save_df(agenda_df, AGENDA_CSV)
        st.success("안건이 추가되었습니다.")
        st.rerun()

    if agenda_df.empty:
        st.info("안건 데이터가 없습니다.")
    else:
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            q = st.text_input("검색", placeholder="안건명 검색")
        with c2:
            teams = ["전체"] + sorted(agenda_df["팀"].dropna().unique().tolist())
            team_filter = st.selectbox("팀 필터", teams, index=0)
        with c3:
            statuses = ["전체"] + sorted(agenda_df["상태"].dropna().unique().tolist())
            status_filter = st.selectbox("상태 필터", statuses, index=0)
        with c4:
            sort_opt = st.selectbox("정렬", ["입안일 최신순", "입안일 오래된순"], index=0)

        f = agenda_df.copy()
        if q:
            f = f[f["안건명"].str.contains(q, case=False, na=False)]
        if team_filter != "전체":
            f = f[f["팀"] == team_filter]
        if status_filter != "전체":
            f = f[f["상태"] == status_filter]

        f["입안일_dt"] = pd.to_datetime(f["입안일"], errors="coerce")
        f = f.sort_values("입안일_dt", ascending=(sort_opt == "입안일 오래된순")).drop(columns=["입안일_dt"]).reset_index(drop=True)

        view = f.copy()
        view.insert(0, "전송", False)

        edited = st.data_editor(
            view[["전송", "안건명", "팀", "입안자", "입안일", "상태"]],
            use_container_width=True,
            hide_index=True,
            column_config={"전송": st.column_config.CheckboxColumn("전송")}
        )

        sel_idx = edited.index[edited["전송"] == True].tolist()
        st.write(f"선택된 안건:{len(sel_idx)}개")

        if st.button("📨 선택 안건 디스코드 전송", type="primary", disabled=(len(sel_idx) == 0)):
            sel = f.iloc[sel_idx].copy()
            fields = []
            for _, r in sel.iterrows():
                fields.append({
                    "name": f"🗂️ {r['안건명']} ({r['팀']})",
                    "value": f"👤 입안자: {r['입안자']}\n📅 입안일: {r['입안일']} | 🏷️ 상태: {r['상태']}",
                    "inline": False
                })
            ok, msg = send_discord(fields, "📌 안건 전송", "Hallaon Agenda Bot")
            if ok:
                st.success(msg)
            else:
                st.error(msg)

elif menu == "🤖 최근 등록된 작업 전송":
    st.header("🤖 최근 등록된 작업 전송")
    if tasks_df.empty:
        st.info("작업 데이터가 없습니다.")
    else:
        u = tasks_df[tasks_df["sent"].astype(str) != "True"].copy()
        if u.empty:
            st.info("미전송 작업이 없습니다.")
        else:
            u = u.reset_index(drop=True)
            ui = u.copy()
            ui.insert(0, "전송", False)

            edited = st.data_editor(
                ui[["전송", "작업명", "담당자", "상태", "팀", "시작일", "종료일"]],
                use_container_width=True,
                hide_index=True,
                column_config={"전송": st.column_config.CheckboxColumn("전송")}
            )

            sel_idx = edited.index[edited["전송"] == True].tolist()
            selected = u.iloc[sel_idx].copy()
            st.write(f"선택된 작업:{len(selected)}개")

            if st.button("🚀 선택 작업 디스코드 전송", type="primary", disabled=(len(selected) == 0)):
                fields = []
                for _, t in selected.iterrows():
                    fields.append({
                        "name": f"🔹 {t['작업명']} ({t['팀']})",
                        "value": f"👤 담당: {t['담당자']}\n📅 기간: {t['시작일']} → {t['종료일']} | 🏷️ 상태: {t['상태']}",
                        "inline": False
                    })
                ok, msg = send_discord(fields, "🔔 새 작업 알림", "Hallaon Roadmap Bot")
                if ok:
                    sent_ids = set(selected["id"].tolist())
                    tasks_df["sent"] = tasks_df.apply(lambda x: True if x["id"] in sent_ids or str(x["sent"]) == "True" else False, axis=1)
                    st.session_state.tasks_df = tasks_df
                    save_df(tasks_df, TASKS_CSV)
                    st.success("전송 완료")
                    st.rerun()
                else:
                    st.error(msg)
