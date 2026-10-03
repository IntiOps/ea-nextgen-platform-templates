from pathlib import Path
import runpy
from prepare import prepare

prepare()
runpy.run_path(str(Path(__file__).resolve().parents[1] / "app.py"), run_name="__main__")
