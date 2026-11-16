"""Make the application importable the way the container runs it (app/ is the working directory, /app)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
