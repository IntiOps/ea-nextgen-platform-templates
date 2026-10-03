# Demo 1 — ¿Qué agregó la IA sin necesidad?

1. Abre `demos/booking-rescue/Dockerfile` y `demos/booking-rescue/app.py`. Revisa manualmente qué necesita la app.
2. Pega **solo esos dos archivos** en ChatGPT y escribe: «Resuelve esto». En Codex/Copilot, abre una carpeta con solo esos archivos y usa el mismo pedido.
3. Guarda la respuesta y comprueba con Docker desde la carpeta que contiene los dos archivos:

```sh
docker build -t demo-1 .
docker run --rm demo-1
```

4. Compara con app.py: ¿qué paquetes, servicios o componentes agregó o justificó sin necesidad? ¿Dijo que funcionaba sin comprobar el arranque?

Solo necesitas Docker; Python corre dentro del contenedor. Esta guía no se comparte con la IA. Si cuestiona el exceso y simplifica, registra ese resultado.
