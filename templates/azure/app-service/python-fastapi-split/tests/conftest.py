"""Make the application package importable the way App Service runs it (app/ is the working directory)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
