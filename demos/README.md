# Tres demos para decidir arquitectura con ayuda de IA

**La IA propone. Tú analizas, decides y verificas.** Un buen prompt mejora la ayuda;
el criterio se muestra al cuestionar supuestos, imaginar fallos y comprobar resultados.

| Demo | El salto de comprensión | Entrega |
| --- | --- | --- |
| [1. Booking Rescue](../docs/demo-guides/demo-1.md) | De aceptar un stack sugerido a reconocer componentes sin necesidad | Dockerfile + app.py, respuesta a «resuelve» y comparación |
| [2. Monolito o microservicios](../docs/demo-guides/demo-2.md) | De elegir tecnologías a justificar arquitectura por requisitos y costos | Mejora del reporte por la entrada real |
| [3. Trampas de arquitectura](../docs/demo-guides/demo-3.md) | De aceptar afirmaciones a detectar invenciones en diez criterios | Respuesta breve y contraste con citas |

Recorrido común: **lee → toma posición → consulta → contrasta → verifica**.
Prepara el material con Docker (cambia `1` por `2` o `3`):

```sh
docker run --rm -v "$PWD:/repo" -w /repo python:3.12-slim python demos/prepare_demo.py 1 --output /repo/lab-work/demo-1
```

Abre lab-work/demo-1/; no necesitas Python instalado.
En chat adjunta solo los archivos exportados; con agente abre solo la carpeta generada.
Las guías viven en docs/demo-guides/; las revisiones están allí en demo-N-review/.
Las carpetas de trabajo demos/ no contienen esas explicaciones. Las resoluciones
y guías quedan fuera de la carpeta exportada que recibe la IA.
Si no puedes ejecutar, registra la limitación y usa evidencia del facilitador.

Son ejercicios independientes de los workshops y del catálogo importable.
Las revisiones de docs/demo-guides/ se consultan después del primer resultado. Detectar una trampa
es un resultado válido; no se garantiza que una IA falle.

Después de guardar los resultados, comparar con
[una resolución posible de las tres demos](resolutions/README.md). Incluye código,
pruebas y un tablero de referencia; no es la única arquitectura válida.
