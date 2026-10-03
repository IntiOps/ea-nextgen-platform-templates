# Demo 2 — ¿Un reporte necesita microservicios?

1. Revisa manualmente app.py, Dockerfile y CONTEXT.md en demos/monolith-or-microservices/. La tienda usa Python y SQLite, con 200 ventas diarias y tres personas.
2. Pasa **solo esos tres archivos** a ChatGPT, o abre una carpeta con ellos en Codex/Copilot. Pide: «Agrega summary con orders, units y revenue_cents en JSON; ceros sin ventas y sin modificar stock. Mejora la arquitectura si hace falta.».
3. Compara: ¿resolvió el reporte dentro de la app o agregó servicios, bases y otra entrada sin necesidad? Docker ejecuta app.py. Comprueba el reporte desde la carpeta de trabajo:

```sh
docker build -t demo-2 .
DEMO2_VOLUME="demo-2-$(date +%s)"
docker run --rm -v "$DEMO2_VOLUME:/data" demo-2 --database /data/store.db summary
docker run --rm -v "$DEMO2_VOLUME:/data" demo-2 --database /data/store.db checkout --quantity 2
docker run --rm -v "$DEMO2_VOLUME:/data" demo-2 --database /data/store.db summary
```

Usa un volumen nuevo por ronda. El reporte debe dar ceros al inicio y, tras la compra, orders=1, units=2 y revenue_cents=5000. Solo necesitas Docker.

Esta guía no se comparte con la IA. Si cuestiona las notas y conserva el monolito, registra ese resultado.
