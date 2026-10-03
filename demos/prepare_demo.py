"""Exporta únicamente el material de entrada; las guías quedan en el repositorio."""
import argparse
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
INPUTS = {
    "1": ("booking-rescue", ["Dockerfile", "app.py"]),
    "2": ("monolith-or-microservices", ["app.py", "Dockerfile", "CONTEXT.md"]),
    "3": ("email-architecture-board", ["PROMPT.md", "REQUEST.md"]),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("demo", choices=INPUTS)
    parser.add_argument("--output", type=Path, help="Carpeta vacía de destino, también usable desde Docker")
    args = parser.parse_args()
    name, files = INPUTS[args.demo]
    destination = args.output or Path(tempfile.mkdtemp(prefix=f"demo-{args.demo}-"))
    if args.output:
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            parser.error("La carpeta de destino debe estar vacía")
    for filename in files:
        target = destination / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name / filename, target)
    print(destination)


if __name__ == "__main__":
    main()
