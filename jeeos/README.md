# JEEOS — JEE Preparation Operating System

Local-first JEE prep app with FastAPI backend, Streamlit frontend, SQLite storage, Plotly analytics, and basic ML rank prediction.

## Folder structure

```
jeeos/
  main.py
  requirements.txt
  README.md
  database/
  backend/
  frontend/
  modules/
  analytics/
  models/
  utils/
  data/
```

## Install

```bash
cd jeeos
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Services:
- API: http://127.0.0.1:8000/docs
- UI: http://127.0.0.1:8501

## Included modules

1. Master Dashboard
2. JEE Syllabus Engine
3. Study Session Tracker (manual start/end + Pomodoro-compatible flow)
4. AI Study Planner
5. Daily Execution System
6. Discipline Tracker
7. Streak System
8. Mock Test Analytics
9. Rank Prediction (scikit-learn linear model)
10. Weak Topic Detection
11. Revision Engine (1/3/7/21/60)
12. PYQ Tracker schema
13. Mistake Notebook schema
14. Strategy Engine with sample past-question dataset
15. Performance Summary through dashboard metrics
16. Weekly Review through 7-day aggregates
17. ChatGPT integration buttons using pyperclip + webbrowser
18. Streamlit UI sections

All data is stored locally in `database/jeeos.db`.
