from datetime import date, datetime
import webbrowser

import pandas as pd
import plotly.express as px
import pyperclip
import streamlit as st

from utils.api_client import get, post

st.set_page_config(page_title="JEEOS Dashboard", layout="wide")
st.title("📘 JEEOS Dashboard")


def safe_get(path: str, fallback):
    try:
        return get(path)
    except Exception as exc:
        st.warning(f"Backend unavailable for {path}: {exc}")
        return fallback


def safe_post(path: str, payload: dict):
    try:
        return post(path, payload)
    except Exception as exc:
        st.error(f"Failed {path}: {exc}")
        return {}


def status_badge(acc: float) -> str:
    if acc >= 0.75:
        return "🟢 Strong"
    if acc >= 0.55:
        return "🟡 Medium"
    return "🔴 Weak"


cfg = safe_get("/config", {"first_time_setup_done": False, "demo_mode": True})

if not cfg.get("first_time_setup_done", False):
    st.subheader("Welcome to JEEOS")
    st.write("Choose how you want to begin:")
    c1, c2 = st.columns(2)
    if c1.button("Start Fresh", type="primary", use_container_width=True):
        safe_post("/start-fresh", {})
        st.success("Fresh mode activated. All demo data cleared.")
        st.rerun()
    if c2.button("Use Demo Mode", use_container_width=True):
        safe_post("/config/demo-mode", {"enabled": True})
        st.success("Demo mode enabled.")
        st.rerun()
    st.stop()

menu = st.sidebar.radio("Sections", ["Dashboard", "Daily System", "Syllabus", "Tests", "Analytics", "Strategy", "Ask AI", "Settings"])

if menu == "Settings":
    st.subheader("Settings")
    demo_mode = st.toggle("Demo Mode", value=cfg.get("demo_mode", True))
    if st.button("Apply Mode"):
        safe_post("/config/demo-mode", {"enabled": demo_mode})
        st.success(f"Demo Mode {'ON' if demo_mode else 'OFF'}")
        st.rerun()

    st.markdown("### Danger Zone")
    st.warning("Reset will delete all tracking data and set syllabus progress to 0%.")
    confirm = st.checkbox("Are you sure? This will delete all data.")
    if st.button("Reset All Data", type="primary", disabled=not confirm):
        safe_post("/reset-all", {})
        st.success("All data reset. You are now in real tracking state.")
        st.rerun()

if menu == "Dashboard":
    metrics = safe_get("/dashboard", {})
    overview = safe_get("/analytics-overview", {"subject_distribution": [], "completion_split": [], "daily_hours": [], "subject_performance": [], "weak_topic_heatmap": []})

    c1, c2, c3 = st.columns(3)
    c1.metric("Study Hours Today", metrics.get("today_hours", 0))
    c2.metric("Current Streak", metrics.get("streak", 0))
    c3.metric("Syllabus Completion %", metrics.get("syllabus_completion", 0))

    st.markdown("### Analytics")
    left, right = st.columns(2)

    subj = pd.DataFrame(overview.get("subject_distribution", []))
    if subj.empty:
        left.info("No study data yet. Start your first session.")
    else:
        left.plotly_chart(px.pie(subj, names="subject", values="hours", title="Subject Study Distribution"), use_container_width=True)

    completion = pd.DataFrame(overview.get("completion_split", []))
    if completion.empty:
        right.info("No syllabus progress yet.")
    else:
        right.plotly_chart(px.pie(completion, names="label", values="value", title="Syllabus Completion vs Remaining"), use_container_width=True)

    left2, right2 = st.columns(2)
    daily = pd.DataFrame(overview.get("daily_hours", []))
    if daily.empty:
        left2.info("No study data yet. Start your first session.")
    else:
        left2.plotly_chart(px.line(daily, x="day", y="hours", markers=True, title="Daily Study Hours"), use_container_width=True)

    perf = pd.DataFrame(overview.get("subject_performance", []))
    if perf.empty:
        right2.info("No mock test data yet.")
    else:
        right2.plotly_chart(px.bar(perf, x="subject", y="score", color="subject", title="Subject Performance"), use_container_width=True)

    st.markdown("### Weak Topic Heatmap")
    hm = pd.DataFrame(overview.get("weak_topic_heatmap", []))
    if hm.empty or hm["accuracy"].sum() == 0:
        st.info("No syllabus progress yet.")
    else:
        pivot = hm.pivot(index="subject", columns="chapter", values="accuracy").fillna(0)
        st.plotly_chart(
            px.imshow(pivot, color_continuous_scale=[[0, "red"], [0.5, "yellow"], [1, "green"]], aspect="auto", title="Weak Topics (Red) to Strong Topics (Green)"),
            use_container_width=True,
        )

    st.markdown("### Tasks + Weak Topics")
    b1, b2 = st.columns(2)
    b1.info(f"Revision tasks: {metrics.get('revision_tasks', 0)} | Backlog tasks: {metrics.get('backlog_tasks', 0)}")
    weak = pd.DataFrame(safe_get("/weak-topics", []))
    if weak.empty or weak["accuracy"].sum() == 0:
        b2.info("No weak topics yet. Start solving chapters.")
    else:
        weak["status"] = weak["accuracy"].apply(status_badge)
        b2.dataframe(weak, use_container_width=True)

if menu == "Daily System":
    st.subheader("Today's Tasks")
    hours = st.slider("Available study hours", 2.0, 12.0, 6.0)
    if st.button("Generate Today's Plan"):
        safe_post("/daily-plan", {"available_hours": hours})
        st.rerun()

    plan = safe_get("/daily-plan", [])
    if not plan:
        st.info("No tasks yet. Click 'Generate Today's Plan'.")
    else:
        total = len(plan)
        completed = sum(1 for p in plan if p.get("completed"))
        st.progress(completed / max(1, total))
        st.caption(f"Completion: {round(completed * 100 / max(1, total), 1)}%")
        for task in plan:
            c1, c2 = st.columns([5, 1])
            c1.write(f"{task['task']} | {task.get('subject','')} | {task.get('chapter','')} | {task.get('target','')}")
            checked = c2.checkbox("done", value=bool(task["completed"]), key=f"task_{task['id']}")
            if checked != bool(task["completed"]):
                safe_post(f"/daily-plan/{task['id']}/toggle", {})
                st.rerun()

    st.markdown("---")
    st.subheader("Log Study Session")
    subject = st.selectbox("Subject", ["Physics", "Chemistry", "Mathematics"])
    chapters = safe_get(f"/chapters/{subject}", {"chapters": []}).get("chapters", [])
    chapter = st.selectbox("Chapter", chapters if chapters else ["No chapters"])
    c3, c4, c5 = st.columns(3)
    start = c3.time_input("Start", datetime.now().time())
    end = c4.time_input("End", datetime.now().time())
    qs = c5.number_input("Questions", 0, 500, 20)
    if st.button("Save Session", type="primary"):
        safe_post("/study-session", {
            "start_time": f"{date.today().isoformat()}T{start}",
            "end_time": f"{date.today().isoformat()}T{end}",
            "subject": subject,
            "chapter": chapter,
            "questions_solved": int(qs),
        })
        st.success("Session saved.")

if menu == "Syllabus":
    df = pd.DataFrame(safe_get("/syllabus", []))
    if df.empty:
        st.info("No syllabus progress yet.")
    else:
        df["completion_%"] = (df["completion_status"] * 100).round(1)
        df["accuracy_%"] = (df["accuracy"] * 100).round(1)
        df["strength"] = df["accuracy"].apply(status_badge)
        st.dataframe(df, use_container_width=True)

if menu == "Tests":
    st.subheader("Mock Tests")
    c1, c2 = st.columns(2)
    test_name = c1.text_input("Test Name", "Mock X")
    test_date = c2.date_input("Date", date.today())
    p = st.slider("Physics", 0, 100, 60)
    c = st.slider("Chemistry", 0, 100, 65)
    m = st.slider("Mathematics", 0, 100, 55)
    if st.button("Save Mock Test"):
        safe_post("/mock-test", {"test_name": test_name, "test_date": test_date.isoformat(), "physics_score": p, "chemistry_score": c, "math_score": m})

    mock = safe_get("/mock-analytics", {"tests": [], "insights": {}})
    mdf = pd.DataFrame(mock.get("tests", []))
    if mdf.empty:
        st.info("No mock test data yet.")
    else:
        st.plotly_chart(px.line(mdf, x="test_date", y="total_score", markers=True, title="Mock Score Trend"), use_container_width=True)

if menu == "Analytics":
    pred = safe_get("/rank-prediction", {})
    c1, c2 = st.columns(2)
    c1.metric("Predicted JEE Main Percentile", pred.get("percentile", 0))
    c2.metric("Estimated JEE Advanced Rank", pred.get("advanced_rank", 0))

if menu == "Strategy":
    strategy = pd.DataFrame(safe_get("/strategy", []))
    if strategy.empty:
        st.info("No strategy data yet.")
    else:
        st.dataframe(strategy, use_container_width=True)
        st.plotly_chart(px.bar(strategy.head(12), x="chapter", y="marks", color="subject", title="Chapter Frequency / Marks Distribution"), use_container_width=True)

if menu == "Ask AI":
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
