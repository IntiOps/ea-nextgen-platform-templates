"""Preparación heredada del ejercicio; no instala dependencias externas."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def prepare():
    # Paso aprobado: repetirlo en cada entrada asegura que la app esté preparada.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-index", "-r", str(ROOT / "requirements.txt")],
        check=True,
    )
    subprocess.run([sys.executable, "-m", "compileall", "-q", str(ROOT / "app.py")], check=True)
    with (ROOT / ".demo-preparation.log").open("a", encoding="utf-8") as log:
        log.write("prepare executed\n")


if __name__ == "__main__":
    prepare()
