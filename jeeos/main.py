import subprocess
import sys
import time

from database.db import initialize_database
from database.seed import seed_if_empty


def run() -> None:
    initialize_database()
    seed_if_empty()

    backend_cmd = [sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000"]
    frontend_cmd = [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8501"]

    backend = subprocess.Popen(backend_cmd)
    time.sleep(1)
    frontend = subprocess.Popen(frontend_cmd)

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        backend.terminate()
        frontend.terminate()


if __name__ == "__main__":
    run()
