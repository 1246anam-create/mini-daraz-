import sys
import os

# ====== PythonAnywhere WSGI config ======
# This file goes in the "WSGI configuration file" box on the
# Web tab of your PythonAnywhere dashboard.

PROJECT_DIR = "/home/minidaraz12/mini-daraz"
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Load .env from the project directory (file-relative, works under WSGI)
from db import _load_env
_load_env(os.path.join(PROJECT_DIR, ".env"))

# Import the Flask app instance
from app import app as application
