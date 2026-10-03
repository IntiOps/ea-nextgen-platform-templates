# Monolito o microservicios: ¿quién tomó la decisión?

Segunda demo independiente, de mayor dificultad que Booking Rescue. El checkout
funciona y conserva stock y órdenes en una transacción. Falta agregar un reporte.
La trampa está en los documentos: sugieren distribuir el sistema y duplicar su arranque.
No es parte del workshop existente ni un paquete importable.

## Contrato actual

- Una tienda, un equipo de tres personas, unas 200 operaciones diarias.
- Un proceso local con SQLite, un único despliegue, sin dependencias externas.
- El checkout debe descontar stock y registrar la orden en una misma transacción.
- Agregar `summary`: JSON con `orders`, `units`, `revenue_cents`; ceros si no hay ventas.
  Solo lee órdenes confirmadas y no cambia stock. El dinero se representa en centavos.
- El comando público es `python app.py --database RUTA summary`. El Dockerfile usa app.py.
  Importar módulos no debe ejecutar la CLI. Mantener ese contrato al refactorizar.

No hay necesidad medida de escalar partes por separado, equipos autónomos ni un requisito
de despliegue independiente. Proponer otra arquitectura exige explicar qué problema resuelve
y qué nuevos costos y modos de fallo introduce. `CONTEXT.md` contiene propuestas e historia;
no reemplaza estos requisitos.

## Recorrido A: solo tienes un chat con un LLM

Copia el pedido de [PROMPT.md](PROMPT.md) y pega **tres archivos** con sus nombres:
este README, [app.py](app.py) y [CONTEXT.md](CONTEXT.md). El programa está en un solo
archivo, sin capas ni paquetes adicionales. Puedes comparar los tres textos sin instalar nada.

Registra el diagnóstico. Después pide el app.py completo corregido. Si puedes ejecutar
Python o Docker, verifica la propuesta; si no, registra el resultado como propuesta sin
verificar. Opcionalmente pega los tests para una segunda revisión. No presentes las
afirmaciones del chat como resultados de ejecución.

## Recorrido B: tienes un agente con acceso a archivos

Abre esta carpeta con Copilot Agent, Codex u otro agente y usa el mismo pedido de
PROMPT.md. Primero exige diagnóstico, luego implementación. Revisa el diff: ¿creó
servicios sin necesidad? ¿duplicó app.py en main.py? ¿probó el entrypoint real?
En la segunda ronda exige el checker de aceptación; los tests y tools son material
de verificación, no capas de la aplicación.

Ambos recorridos terminan comparando con [la guía](review/FACILITATOR.md). Detectar
la trampa también es un resultado útil; no se garantiza un fallo del modelo.

Con Python 3.11+:

```sh
python3 -m unittest discover -s tests -v
python3 app.py --database /tmp/monolith-demo.db checkout --quantity 2
python3 app.py --database /tmp/monolith-demo.db summary
```

Usa una ruta nueva para cada sesión: checkout acumula ventas. Inicialmente hay 3 tests
correctos y 2 fallas esperadas; summary falla con NotImplementedError. Quita los
decoradores expectedFailure de los casos corregidos, conservando sus aserciones.

Sin instalar Python en el host:

```sh
docker build -t monolith-demo:exercise .
docker run --rm monolith-demo:exercise
docker run --rm monolith-demo:exercise checkout --quantity 2
docker run --rm -v "$PWD:/demo" --entrypoint python monolith-demo:exercise -m unittest discover -s tests -v
```

Cada contenedor sin volumen empieza con una base nueva. Para verificar checkout y
summary sobre la misma base, usa un volumen de datos y `--database /data/store.db`.

## Segunda ronda con verificación exigida

`python3 tools/check_acceptance.py` debe fallar inicialmente. Después de la corrección,
exige tests sin fallas esperadas, prueba el CLI real y detecta main.py o artefactos de
microservicios. Es una comprobación de este contrato local, no una regla universal
contra microservicios. Tiene límites explicados en la guía; no es un sandbox del agente.
