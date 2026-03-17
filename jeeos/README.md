# JEEOS — JEE Preparation Operating System

A fully local, production-style JEE analytics dashboard built with FastAPI + Streamlit + SQLite + Plotly.

## Features
- Auto-loaded full JEE syllabus (Physics, Chemistry, Mathematics) stored in SQLite on first run.
- Modern dashboard with dynamic charts:
  - Subject study distribution (pie)
  - Syllabus completion vs remaining (pie)
  - Daily study hours (line)
  - Subject performance (bar)
  - Weak topic heatmap (red→green)
- Daily system with task checkboxes and completion progress bar.
- Auto calculations for completion %, accuracy, and discipline score.
- Seeded sample data (study sessions, tests, syllabus progress) for immediate analytics.
- Rank prediction, revision engine, weak-topic detection, and strategy insights.

## Project Structure

```
jeeos/
  main.py
  requirements.txt
  frontend/app.py
  backend/app.py
  database/schema.sql
  database/db.py
  database/seed.py
  modules/syllabus_data.py
  modules/planner.py
  modules/revision.py
  analytics/insights.py
  analytics/strategy.py
  models/schemas.py
  utils/api_client.py
```

## Install

```bash
cd jeeos
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

- FastAPI docs: http://127.0.0.1:8000/docs
- Streamlit app: http://127.0.0.1:8501

Everything runs entirely local and free (no paid APIs, no cloud dependencies).


## Real Mode
- First launch shows Welcome screen with **Start Fresh**.
- **Demo Mode** can be toggled in Settings.
- **Reset All Data** clears sessions/tests/habits and resets syllabus progress to 0%.
