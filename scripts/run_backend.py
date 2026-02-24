"""
run_backend.py — Start FastAPI + Streamlit
===========================================
Run this script to start the full system.
Opens FastAPI on port 8000 and Streamlit on port 8501.

Usage:
    python scripts/run_backend.py

Stop with Ctrl+C
"""

import subprocess
import sys
import os
import time
import webbrowser

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

print("=" * 55)
print("FSAM Query System — Starting...")
print("=" * 55)

# ── Check database exists ────────────────────────────────────
if not os.path.exists("data/processed/fsam_data.db"):
    print("\n⚠️  Database not found!")
    print("    Run this first: python scripts/run_etl.py")
    sys.exit(1)

print("\n[Step 1] Starting FastAPI server on port 8000...")
api_process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn",
     "backend.api.main:app",
     "--reload",
     "--port", "8000"],
    stdout = subprocess.PIPE,
    stderr = subprocess.PIPE
)

# Wait for FastAPI to start
time.sleep(3)
print("✅ FastAPI running at http://localhost:8000")
print("   API docs at http://localhost:8000/docs")

print("\n[Step 2] Starting Streamlit UI on port 8501...")
ui_process = subprocess.Popen(
    [sys.executable, "-m", "streamlit",
     "run", "frontend/app.py",
     "--server.port", "8501"],
)

# Wait for Streamlit to start
time.sleep(3)
print("✅ Streamlit running at http://localhost:8501")

# Open browser automatically
print("\n[Step 3] Opening browser...")
webbrowser.open("http://localhost:8501")

print("\n" + "=" * 55)
print("✅ System is running!")
print("")
print("   UI:      http://localhost:8501")
print("   API:     http://localhost:8000")
print("   API Docs:http://localhost:8000/docs")
print("")
print("   Press Ctrl+C to stop everything")
print("=" * 55)

# Keep running until Ctrl+C
try:
    api_process.wait()
except KeyboardInterrupt:
    print("\n\nShutting down...")
    api_process.terminate()
    ui_process.terminate()
    print("✅ All processes stopped.")