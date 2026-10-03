# Guías de las demos

Material para estudiantes y docentes, fuera del contexto de la IA.

| Demo | Path que lee el estudiante | Material de trabajo |
| --- | --- | --- |
| 1 — Booking Rescue | [demo-1.md](demo-1.md) | demos/booking-rescue/ |
| 2 — Reporte de ventas | [demo-2.md](demo-2.md) | demos/monolith-or-microservices/ |
| 3 — Arquitectura | [demo-3.md](demo-3.md) | demos/email-architecture-board/ |

Cada guía explica la revisión manual, qué compartir con ChatGPT o cómo abrir la
carpeta aislada en Codex/Copilot, y cómo comprobar el resultado. El docente puede
entregar la guía como documento aparte. El estudiante no la adjunta a la IA.

Las revisiones demo-N-review/ se leen después de guardar el primer resultado.
Para la IA, generar una copia con el comando Docker siguiente (cambia `1` por `2` o `3`) y abrir únicamente
la ruta impresa. Indicar un path dentro del repositorio completo no impide que un
agente explore otras carpetas; la copia aislada evita incluir las guías en su workspace.

Desde la raíz del repo, sin instalar Python:

```sh
docker run --rm -v "$PWD:/repo" -w /repo python:3.12-slim python demos/prepare_demo.py 1 --output /repo/lab-work/demo-1
```

Abre lab-work/demo-1/ en tu editor. Usa una carpeta vacía para cada nueva ronda.
