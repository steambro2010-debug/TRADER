from datetime import date, datetime
import webbrowser

import pandas as pd
import plotly.express as px
import pyperclip
import streamlit as st

from utils.api_client import get, post

st.set_page_config(page_title="JEEOS Dashboard", layout="wide")
st.title("📘 JEEOS Dashboard")
st.caption("Professional local-first JEE preparation analytics system")

menu = st.sidebar.radio("Sections", ["Dashboard", "Daily System", "Syllabus", "Tests", "Analytics", "Strategy", "Ask AI"])


def safe_get(path: str, fallback):
    try:
        return get(path)
    except Exception as exc:
        st.warning(f"Backend unavailable for {path}: {exc}")
        return fallback


def status_badge(acc: float) -> str:
    if acc >= 0.75:
        return "🟢 Strong"
    if acc >= 0.55:
        return "🟡 Medium"
    return "🔴 Weak"


if menu == "Dashboard":
    metrics = safe_get("/dashboard", {})
    overview = safe_get(
        "/analytics-overview",
        {"subject_distribution": [], "completion_split": [], "daily_hours": [], "subject_performance": [], "weak_topic_heatmap": []},
    )
    weak = pd.DataFrame(safe_get("/weak-topics", []))

    top = st.container()
    with top:
        c1, c2, c3 = st.columns(3)
        c1.metric("Study Hours Today", metrics.get("today_hours", 0))
        c2.metric("Current Streak", metrics.get("streak", 0))
        c3.metric("Syllabus Completion %", metrics.get("syllabus_completion", 0))

    st.markdown("### Analytics")
    c1, c2 = st.columns(2)
    subj = pd.DataFrame(overview.get("subject_distribution", []))
    if not subj.empty:
        c1.plotly_chart(px.pie(subj, names="subject", values="hours", title="Subject Study Distribution"), use_container_width=True)

    completion = pd.DataFrame(overview.get("completion_split", []))
    if not completion.empty:
        c2.plotly_chart(px.pie(completion, names="label", values="value", title="Syllabus Completion vs Remaining"), use_container_width=True)

    c3, c4 = st.columns(2)
    daily = pd.DataFrame(overview.get("daily_hours", []))
    if not daily.empty:
        c3.plotly_chart(px.line(daily, x="day", y="hours", markers=True, title="Daily Study Hours"), use_container_width=True)

    perf = pd.DataFrame(overview.get("subject_performance", []))
    if not perf.empty:
        c4.plotly_chart(px.bar(perf, x="subject", y="score", color="subject", title="Subject Performance"), use_container_width=True)

    st.markdown("### Weak Topic Heatmap")
    hm = pd.DataFrame(overview.get("weak_topic_heatmap", []))
    if not hm.empty:
        pivot = hm.pivot(index="subject", columns="chapter", values="accuracy").fillna(0)
        fig = px.imshow(
            pivot,
            color_continuous_scale=[[0, "red"], [0.5, "yellow"], [1, "green"]],
            aspect="auto",
            title="Weak Topics (Red) to Strong Topics (Green)",
        )
        st.plotly_chart(fig, use_container_width=True)

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("### Tasks")
        st.info(f"Revision tasks: {metrics.get('revision_tasks', 0)}  |  Backlog tasks: {metrics.get('backlog_tasks', 0)}")
    with b2:
        st.markdown("### Weak Topics")
        if not weak.empty:
            weak["status"] = weak["accuracy"].apply(status_badge)
        st.dataframe(weak, use_container_width=True)

if menu == "Daily System":
    st.subheader("Today's Daily System")
    c1, c2 = st.columns([2, 1])
    with c1:
        if st.button("Generate Today Plan", use_container_width=True):
            post("/daily-plan", {"available_hours": 6.0})
    with c2:
        available_hours = st.slider("Available hours", 2.0, 12.0, 6.0)
        if st.button("Regenerate with hours", use_container_width=True):
            post("/daily-plan", {"available_hours": available_hours})

    plan = safe_get("/daily-plan", [])
    total = max(1, len(plan))
    completed = sum(1 for task in plan if task.get("completed"))
    st.progress(completed / total)
    st.caption(f"Completion: {round((completed / total) * 100, 1)}%")

    for task in plan:
        col_task, col_chk = st.columns([5, 1])
        label = f"{task['task']} — {task.get('subject','')} {task.get('chapter','')} {task.get('target','')}"
        col_task.write(label)
        checked = col_chk.checkbox("done", value=bool(task["completed"]), key=f"task_{task['id']}")
        if checked != bool(task["completed"]):
            post(f"/daily-plan/{task['id']}/toggle", {})
            st.rerun()

    st.markdown("---")
    st.subheader("Quick Study Session Log")
    subject = st.selectbox("Subject", ["Physics", "Chemistry", "Mathematics"], key="daily_subject")
    chapters = safe_get(f"/chapters/{subject}", {"chapters": []}).get("chapters", [])
    chapter = st.selectbox("Chapter", chapters if chapters else ["Select chapter"], key="daily_chapter")
    c3, c4, c5 = st.columns(3)
    start = c3.time_input("Start", datetime.now().time())
    end = c4.time_input("End", datetime.now().time())
    questions = c5.number_input("Questions", 0, 500, 25)
    if st.button("Save Session", type="primary"):
        payload = {
            "start_time": f"{date.today().isoformat()}T{start}",
            "end_time": f"{date.today().isoformat()}T{end}",
            "subject": subject,
            "chapter": chapter,
            "questions_solved": int(questions),
        }
        post("/study-session", payload)
        st.success("Session saved and analytics updated.")

if menu == "Syllabus":
    st.subheader("Full JEE Syllabus Progress")
    df = pd.DataFrame(safe_get("/syllabus", []))
    if not df.empty:
        df["completion_%"] = (df["completion_status"] * 100).round(1)
        df["accuracy_%"] = (df["accuracy"] * 100).round(1)
        df["strength"] = df["accuracy"].apply(status_badge)
    st.dataframe(df, use_container_width=True)

if menu == "Tests":
    st.subheader("Mock Tests")
    c1, c2, c3 = st.columns(3)
    test_name = c1.text_input("Test Name", "Mock X")
    test_date = c2.date_input("Test Date", date.today())
    subject = c3.selectbox("Quick Subject Preset", ["Balanced", "Physics Focus", "Math Focus"])
    p = st.slider("Physics", 0, 100, 60)
    c = st.slider("Chemistry", 0, 100, 65)
    m = st.slider("Math", 0, 100, 55)
    if st.button("Save Mock Test", type="primary"):
        post("/mock-test", {"test_name": test_name, "test_date": test_date.isoformat(), "physics_score": p, "chemistry_score": c, "math_score": m})

    mock = safe_get("/mock-analytics", {"tests": [], "insights": {}})
    mdf = pd.DataFrame(mock.get("tests", []))
    if not mdf.empty:
        st.plotly_chart(px.line(mdf, x="test_date", y="total_score", markers=True, title="Mock Score Trend"), use_container_width=True)
        melted = mdf.melt(id_vars=["test_name"], value_vars=["physics_score", "chemistry_score", "math_score"], var_name="subject", value_name="score")
        st.plotly_chart(px.bar(melted, x="test_name", y="score", color="subject", barmode="group", title="Subject Comparison"), use_container_width=True)
    st.info(str(mock.get("insights", {})))

if menu == "Analytics":
    pred = safe_get("/rank-prediction", {})
    c1, c2 = st.columns(2)
    c1.metric("Predicted JEE Main Percentile", pred.get("percentile", 0))
    c2.metric("Estimated JEE Advanced Rank", pred.get("advanced_rank", 0))
    st.dataframe(pd.DataFrame(safe_get("/revision-tasks", [])), use_container_width=True)

if menu == "Strategy":
    strategy = pd.DataFrame(safe_get("/strategy", []))
    st.subheader("High ROI Chapters")
    st.dataframe(strategy, use_container_width=True)
    if not strategy.empty:
        st.plotly_chart(px.bar(strategy.head(12), x="chapter", y="marks", color="subject", title="Chapter Frequency / Marks Distribution"), use_container_width=True)

if menu == "Ask AI":
    st.subheader("Ask AI")
    prompt = st.text_area("Prompt", "Explain concept: Electrostatics in simple language.")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Explain concept"):
        pyperclip.copy(f"Explain concept for JEE: {prompt}")
        webbrowser.open("https://chat.openai.com/")
    if c2.button("Solve problem"):
        pyperclip.copy(f"Solve this JEE problem step by step: {prompt}")
        webbrowser.open("https://chat.openai.com/")
    if c3.button("Give shortcuts"):
        pyperclip.copy(f"Give quick shortcuts for: {prompt}")
        webbrowser.open("https://chat.openai.com/")
    if c4.button("Ask AI"):
        pyperclip.copy(prompt)
        webbrowser.open("https://chat.openai.com/")
    st.success("Prompt copied + ChatGPT opened.")
