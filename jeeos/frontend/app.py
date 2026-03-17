from datetime import datetime, date
import webbrowser

import pandas as pd
import plotly.express as px
import pyperclip
import streamlit as st

from utils.api_client import get, post

st.set_page_config(page_title="JEEOS", layout="wide")
st.title("JEEOS — JEE Preparation Operating System")

menu = st.sidebar.radio("Sections", ["Dashboard", "Daily System", "Syllabus", "Tests", "Analytics", "Strategy", "Ask AI"])


def safe_get(path: str, fallback):
    try:
        return get(path)
    except Exception as exc:
        st.warning(f"Backend unavailable for {path}: {exc}")
        return fallback


if menu == "Dashboard":
    metrics = safe_get("/dashboard", {})
    stats = safe_get("/study-stats", {"weekly": [], "subject_distribution": []})
    weak = safe_get("/weak-topics", [])

    cols = st.columns(4)
    cols[0].metric("Study hours today", metrics.get("today_hours", 0))
    cols[1].metric("Syllabus completion %", metrics.get("syllabus_completion", 0))
    cols[2].metric("Current streak", metrics.get("streak", 0))
    cols[3].metric("Mock test average", metrics.get("mock_avg", 0))

    c1, c2 = st.columns(2)
    weekly_df = pd.DataFrame(stats.get("weekly", []))
    if not weekly_df.empty:
        c1.plotly_chart(px.bar(weekly_df.sort_values("day"), x="day", y="hours", title="Weekly Study Graph"), use_container_width=True)

    subj_df = pd.DataFrame(stats.get("subject_distribution", []))
    if not subj_df.empty:
        c2.plotly_chart(px.pie(subj_df, names="subject", values="hours", title="Subject Distribution"), use_container_width=True)

    st.subheader("Weakest Chapters")
    st.dataframe(pd.DataFrame(weak))
    st.info(f"Revision tasks: {metrics.get('revision_tasks', 0)} | Backlog tasks: {metrics.get('backlog_tasks', 0)}")

    jee_main_days = (date(2027, 1, 15) - date.today()).days
    jee_adv_days = (date(2027, 5, 20) - date.today()).days
    st.success(f"Days until JEE Main: {jee_main_days} | Days until JEE Advanced: {jee_adv_days}")

if menu == "Daily System":
    st.subheader("Study Session Tracker")
    with st.form("session_form"):
        subject = st.selectbox("Subject", ["Physics", "Chemistry", "Mathematics"])
        chapter = st.text_input("Chapter", "Kinematics")
        start = st.time_input("Start", datetime.now().time())
        end = st.time_input("End", datetime.now().time())
        qs = st.number_input("Questions solved", min_value=0, value=20)
        if st.form_submit_button("Save Session"):
            today = date.today().isoformat()
            payload = {
                "start_time": f"{today}T{start}",
                "end_time": f"{today}T{end}",
                "subject": subject,
                "chapter": chapter,
                "questions_solved": int(qs),
            }
            st.json(post("/study-session", payload))

    st.markdown("### AI Study Planner")
    hours = st.slider("Available study hours", 2.0, 12.0, 6.0)
    if st.button("Generate Daily Plan"):
        post("/daily-plan", {"available_hours": hours})

    plan = safe_get("/daily-plan", [])
    completed = sum(1 for p in plan if p.get("completed"))
    total = max(1, len(plan))
    st.progress(completed / total)
    st.dataframe(pd.DataFrame(plan))

    st.markdown("### Performance Summary")
    metrics = safe_get("/dashboard", {})
    st.write({"total_study_hours": metrics.get("today_hours",0), "tasks_completed": completed, "discipline_score": "check latest habit", "weak_topics_covered": metrics.get("weakest_chapters", [])})

    st.markdown("### Discipline Tracker")
    with st.form("discipline"):
        fields = {}
        for label in ["Woke up on time", "Completed study sessions", "No phone usage", "Did revision", "Solved PYQs", "Exercise", "Sleep on time"]:
            fields[label] = st.checkbox(label)
        if st.form_submit_button("Save Discipline"):
            payload = {
                "habit_date": date.today().isoformat(),
                "woke_on_time": fields["Woke up on time"],
                "completed_sessions": fields["Completed study sessions"],
                "no_phone_usage": fields["No phone usage"],
                "did_revision": fields["Did revision"],
                "solved_pyq": fields["Solved PYQs"],
                "exercise": fields["Exercise"],
                "slept_on_time": fields["Sleep on time"],
            }
            st.success(post("/habit", payload))

if menu == "Syllabus":
    data = safe_get("/syllabus", [])
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

if menu == "Tests":
    with st.form("mock"):
        name = st.text_input("Test name", "Mock X")
        test_date = st.date_input("Date", date.today())
        p = st.number_input("Physics", 0, 100, 60)
        c = st.number_input("Chemistry", 0, 100, 65)
        m = st.number_input("Math", 0, 100, 55)
        if st.form_submit_button("Save Test"):
            payload = {"test_name": name, "test_date": test_date.isoformat(), "physics_score": p, "chemistry_score": c, "math_score": m}
            st.success(post("/mock-test", payload))

    mock = safe_get("/mock-analytics", {"tests": [], "insights": {}})
    mdf = pd.DataFrame(mock["tests"])
    if not mdf.empty:
        st.plotly_chart(px.line(mdf, x="test_date", y="total_score", title="Mock Score Trend", markers=True), use_container_width=True)
        comp = mdf.melt(id_vars=["test_name"], value_vars=["physics_score", "chemistry_score", "math_score"], var_name="subject", value_name="score")
        st.plotly_chart(px.bar(comp, x="test_name", y="score", color="subject", barmode="group", title="Subject Comparison"), use_container_width=True)
    st.json(mock["insights"])

if menu == "Analytics":
    pred = safe_get("/rank-prediction", {})
    weak = pd.DataFrame(safe_get("/weak-topics", []))
    rev = pd.DataFrame(safe_get("/revision-tasks", []))
    st.metric("Predicted JEE Main Percentile", pred.get("percentile", 0))
    st.metric("Estimated JEE Advanced Rank", pred.get("advanced_rank", 0))
    st.subheader("Weak Topic Detection")
    st.dataframe(weak)
    st.subheader("Spaced Revision Engine")
    st.dataframe(rev)

    st.markdown("### PYQ Tracker")
    with st.form("pyq"):
        y = st.number_input("Year", 2002, 2030, 2023)
        subj = st.selectbox("PYQ Subject", ["Physics","Chemistry","Mathematics"])
        ch = st.text_input("PYQ Chapter", "Current Electricity")
        corr = st.checkbox("Correct")
        tt = st.number_input("Time taken (seconds)", 10, 5000, 180)
        if st.form_submit_button("Add PYQ Attempt"):
            post("/pyq-attempt", {"year": int(y), "subject": subj, "chapter": ch, "is_correct": corr, "time_taken_seconds": int(tt)})
    st.dataframe(pd.DataFrame(safe_get("/pyq-analytics", [])))

    st.markdown("### Mistake Notebook")
    with st.form("mistake"):
        m_ch = st.text_input("Mistake Chapter", "Electrostatics")
        m_type = st.selectbox("Mistake Type", ["concept","calculation","careless","time pressure"])
        m_note = st.text_area("Note", "Forgot sign convention")
        if st.form_submit_button("Log Mistake"):
            post("/mistake", {"chapter": m_ch, "mistake_type": m_type, "note": m_note, "question_image_path": ""})
    st.dataframe(pd.DataFrame(safe_get("/mistake-analytics", [])))

    st.markdown("### Weekly Review")
    st.json(safe_get("/weekly-review", {}))

if menu == "Strategy":
    strategy = pd.DataFrame(safe_get("/strategy", []))
    st.subheader("High ROI Chapters")
    st.dataframe(strategy)
    if not strategy.empty:
        st.plotly_chart(px.bar(strategy.head(10), x="chapter", y="marks", color="subject", title="Chapter Frequency / Marks Distribution"), use_container_width=True)

if menu == "Ask AI":
    st.write("Use ChatGPT workflows for concept clarity and speed.")
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
    st.caption("Prompt copied to clipboard and ChatGPT opened in browser.")
