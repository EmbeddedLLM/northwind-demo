import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = os.getenv("BASE_URL", "")
API_KEY = os.getenv("API_KEY", "")
MODEL = os.getenv("MODEL", "")

DEMO_DIR = Path(__file__).parent.parent
DB_PATH = DEMO_DIR / "northwind.db"
WORKSPACE_DIR = DEMO_DIR / "workspace"
REPORTS_DIR = Path(__file__).parent / "reports"

ALLOWED_SHELL = {"ls", "find", "mkdir", "mv", "cp", "zip", "cat", "pwd", "echo", "which", "for"}

WORKSPACE_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
