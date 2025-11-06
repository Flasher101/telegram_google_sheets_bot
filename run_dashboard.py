import subprocess
import os

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([
        "streamlit", "run",
        "dashboard/app.py",
        "--server.port=8501",
        "--server.address=0.0.0.0" # Changed to 0.0.0.0 to allow external access if needed
    ])
