from datetime import date, datetime
import webbrowser

import pandas as pd
import plotly.express as px
import pyperclip
import streamlit as st

from utils.api_client import get, post

st.set_page_config(page_title="JEEOS Dashboard", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #0B0F14;
        --card: #111827;
        --accent: #3B82F6;
        --text: #FFFFFF;
        --muted: #9CA3AF;
        --border: rgba(156,163,175,0.18);
    }
    .stApp {
        background: var(--bg);
        color: var(--text);
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .top-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: var(--text);
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: var(--muted);
        font-size: 0.98rem;
        margin-bottom: 1.8rem;
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 650;
        color: var(--text);
        margin: 1.35rem 0 0.8rem 0;
    }
    .kpi-card, .glass-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        box-shadow: 0 12px 24px rgba(0,0,0,0.22);
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text);
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.84rem;
        color: var(--muted);
        margin-top: 0.3rem;
    }
    .empty-state {
        background: rgba(17,24,39,0.7);
        border: 1px dashed var(--border);
        border-radius: 12px;
        padding: 1rem;
        color: var(--muted);
    }
    .stButton > button {
        border-radius: 999px;
        border: 1px solid rgba(59,130,246,0.35);
        background: linear-gradient(180deg, rgba(59,130,246,0.28), rgba(59,130,246,0.16));
        color: var(--text);
        font-weight: 600;
        padding: 0.45rem 1rem;
    }
    .stProgress > div > div {
        border-radius: 999px;
        background: linear-gradient(90deg, #2563EB, #3B82F6);
    }
    [data-testid="stSidebar"] {
        background: #0F172A;
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] * {
        color: var(--text);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def safe_get(path: str, fallback):
    try:
        return get(path)
    except Exception:
        return fallback


def safe_post(path: str, payload: dict):
    try:
        return post(path, payload)
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return {}


def card_metric(label: str, value: str):
    st.markdown(
        f"""
        <div class='kpi-card'>
            <div class='kpi-value'>{value}</div>
            <div class='kpi-label'>{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_message(msg: str):
    st.markdown(f"<div class='empty-state'>{msg}</div>", unsafe_allow_html=True)


def status_badge(acc: float) -> str:
    if acc >= 0.75:
        return "🟢 Strong"
    if acc >= 0.55:
        return "🟡 Medium"
    return "🔴 Weak"


chart_template = dict(
    paper_bgcolor="#111827",
    plot_bgcolor="#111827",
    font=dict(color="#FFFFFF"),
    margin=dict(l=20, r=20, t=40, b=20),
)

st.markdown("<div class='top-title'>JEEOS Dashboard</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>A focused and minimal preparation workspace.</div>", unsafe_allow_html=True)

cfg = safe_get("/config", {"first_time_setup_done": False, "demo_mode": True})
if not cfg.get("first_time_setup_done", False):
    with st.container(border=False):
        st.markdown("<div class='section-title'>Welcome to JEEOS</div>", unsafe_allow_html=True)
        st.caption("Set up your workspace to begin.")
        c1, c2 = st.columns(2)
        if c1.button("Start Fresh", type="primary", use_container_width=True):
            safe_post("/start-fresh", {})
            st.rerun()
        if c2.button("Use Demo Mode", use_container_width=True):
            safe_post("/config/demo-mode", {"enabled": True})
            st.rerun()
    st.stop()

menu = st.sidebar.radio("Navigation", ["Dashboard", "Daily System", "Syllabus", "Tests", "Analytics", "Strategy", "Ask AI"])

if menu == "Dashboard":
    metrics = safe_get("/dashboard", {})
    overview = safe_get("/analytics-overview", {"subject_distribution": [], "completion_split": [], "daily_hours": [], "subject_performance": [], "weak_topic_heatmap": []})

    k1, k2, k3 = st.columns(3, gap="large")
    with k1:
        card_metric("Study Hours Today", f"{metrics.get('today_hours', 0)}")
    with k2:
        card_metric("Current Streak", f"{metrics.get('streak', 0)}")
    with k3:
        card_metric("Syllabus Completion", f"{metrics.get('syllabus_completion', 0)}%")

    st.markdown("<div class='section-title'>Analytics</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")

    subj = pd.DataFrame(overview.get("subject_distribution", []))
    if subj.empty:
        with c1:
            empty_message("Start your first study session")
    else:
        fig = px.pie(subj, names="subject", values="hours", color_discrete_sequence=["#3B82F6", "#60A5FA", "#93C5FD"], hole=0.45)
        fig.update_traces(textinfo="none")
        fig.update_layout(showlegend=True, **chart_template)
        c1.plotly_chart(fig, use_container_width=True)

    completion = pd.DataFrame(overview.get("completion_split", []))
    if completion.empty:
        with c2:
            empty_message("Your progress will appear here")
    else:
        fig = px.pie(completion, names="label", values="value", color="label", color_discrete_map={"Completed": "#3B82F6", "Remaining": "#374151"}, hole=0.52)
        fig.update_traces(textinfo="none")
        fig.update_layout(showlegend=True, **chart_template)
        c2.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2, gap="large")
    daily = pd.DataFrame(overview.get("daily_hours", []))
    if daily.empty:
        with c3:
            empty_message("Start your first study session")
    else:
        fig = px.line(daily, x="day", y="hours", markers=False)
        fig.update_traces(line=dict(width=2, color="#60A5FA"))
        fig.update_layout(xaxis_title="", yaxis_title="", **chart_template)
        c3.plotly_chart(fig, use_container_width=True)

    perf = pd.DataFrame(overview.get("subject_performance", []))
    if perf.empty:
        with c4:
            empty_message("Your progress will appear here")
    else:
        fig = px.bar(perf, x="subject", y="score", color="subject", color_discrete_sequence=["#3B82F6", "#60A5FA", "#93C5FD"])
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="", **chart_template)
        c4.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-title'>Tasks and Weak Topics</div>", unsafe_allow_html=True)
    t1, t2 = st.columns(2, gap="large")
    with t1:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.caption(f"Revision tasks: {metrics.get('revision_tasks', 0)}")
        st.caption(f"Backlog tasks: {metrics.get('backlog_tasks', 0)}")
        st.markdown("</div>", unsafe_allow_html=True)
    with t2:
        weak = pd.DataFrame(safe_get("/weak-topics", []))
        if weak.empty or weak["accuracy"].sum() == 0:
            empty_message("Your progress will appear here")
        else:
            weak["status"] = weak["accuracy"].apply(status_badge)
            st.dataframe(weak[["subject", "chapter", "accuracy", "status"]], use_container_width=True, hide_index=True)

if menu == "Daily System":
    st.markdown("<div class='section-title'>Daily System</div>", unsafe_allow_html=True)
    hours = st.slider("Available study hours", 2.0, 12.0, 6.0)
    if st.button("Generate Today Plan"):
        safe_post("/daily-plan", {"available_hours": hours})
        st.rerun()

    plan = safe_get("/daily-plan", [])
    if not plan:
        empty_message("Start your first study session")
    else:
        total = len(plan)
        done = sum(1 for p in plan if p.get("completed"))
        st.progress(done / max(1, total))
        st.caption(f"Completion {round(done * 100 / max(1, total), 1)}%")
        for task in plan:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{task['task']}**\n\n{task.get('subject','')} {task.get('chapter','')} {task.get('target','')}")
            checked = c2.checkbox("", value=bool(task["completed"]), key=f"task_{task['id']}")
            if checked != bool(task["completed"]):
                safe_post(f"/daily-plan/{task['id']}/toggle", {})
                st.rerun()

    st.markdown("<div class='section-title'>Log Study Session</div>", unsafe_allow_html=True)
    subject = st.selectbox("Subject", ["Physics", "Chemistry", "Mathematics"])
    chapters = safe_get(f"/chapters/{subject}", {"chapters": []}).get("chapters", [])
    chapter = st.selectbox("Chapter", chapters if chapters else ["No chapters"])
    l1, l2, l3 = st.columns(3)
    start = l1.time_input("Start", datetime.now().time())
    end = l2.time_input("End", datetime.now().time())
    qs = l3.number_input("Questions", 0, 500, 20)
    if st.button("Save Session"):
        safe_post("/study-session", {
            "start_time": f"{date.today().isoformat()}T{start}",
            "end_time": f"{date.today().isoformat()}T{end}",
            "subject": subject,
            "chapter": chapter,
            "questions_solved": int(qs),
        })
        st.rerun()

if menu == "Syllabus":
    st.markdown("<div class='section-title'>Syllabus</div>", unsafe_allow_html=True)
    df = pd.DataFrame(safe_get("/syllabus", []))
    if df.empty:
        empty_message("Your progress will appear here")
    else:
        df["completion_%"] = (df["completion_status"] * 100).round(1)
        df["accuracy_%"] = (df["accuracy"] * 100).round(1)
        df["status"] = df["accuracy"].apply(status_badge)
        st.dataframe(df[["subject", "chapter", "completion_%", "accuracy_%", "status"]], use_container_width=True, hide_index=True)

if menu == "Tests":
    st.markdown("<div class='section-title'>Tests</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    test_name = c1.text_input("Test Name", "Mock X")
    test_date = c2.date_input("Date", date.today())
    p = st.slider("Physics", 0, 100, 60)
    c = st.slider("Chemistry", 0, 100, 65)
    m = st.slider("Mathematics", 0, 100, 55)
    if st.button("Save Mock Test"):
        safe_post("/mock-test", {"test_name": test_name, "test_date": test_date.isoformat(), "physics_score": p, "chemistry_score": c, "math_score": m})

    mdf = pd.DataFrame(safe_get("/mock-analytics", {"tests": []}).get("tests", []))
    if mdf.empty:
        empty_message("Your progress will appear here")
    else:
        fig = px.line(mdf, x="test_date", y="total_score")
        fig.update_traces(line=dict(width=2, color="#60A5FA"))
        fig.update_layout(xaxis_title="", yaxis_title="", **chart_template)
        st.plotly_chart(fig, use_container_width=True)

if menu == "Analytics":
    st.markdown("<div class='section-title'>Analytics</div>", unsafe_allow_html=True)
    pred = safe_get("/rank-prediction", {})
    a1, a2 = st.columns(2)
    with a1:
        card_metric("Predicted JEE Main Percentile", str(pred.get("percentile", 0)))
    with a2:
        card_metric("Estimated JEE Advanced Rank", str(pred.get("advanced_rank", 0)))

if menu == "Strategy":
    st.markdown("<div class='section-title'>Strategy</div>", unsafe_allow_html=True)
    strategy = pd.DataFrame(safe_get("/strategy", []))
    if strategy.empty:
        empty_message("Your progress will appear here")
    else:
        fig = px.bar(strategy.head(12), x="chapter", y="marks", color="subject", color_discrete_sequence=["#3B82F6", "#60A5FA", "#93C5FD"])
        fig.update_layout(xaxis_title="", yaxis_title="", **chart_template)
        st.plotly_chart(fig, use_container_width=True)

if menu == "Ask AI":
    st.markdown("<div class='section-title'>Ask AI</div>", unsafe_allow_html=True)
    prompt = st.text_area("Prompt", "Explain concept: Electrostatics in simple language.")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Explain"):
        pyperclip.copy(f"Explain concept for JEE: {prompt}")
        webbrowser.open("https://chat.openai.com/")
    if c2.button("Solve"):
        pyperclip.copy(f"Solve this JEE problem step by step: {prompt}")
        webbrowser.open("https://chat.openai.com/")
    if c3.button("Shortcuts"):
        pyperclip.copy(f"Give quick shortcuts for: {prompt}")
        webbrowser.open("https://chat.openai.com/")
    if c4.button("Open AI"):
        pyperclip.copy(prompt)
        webbrowser.open("https://chat.openai.com/")
