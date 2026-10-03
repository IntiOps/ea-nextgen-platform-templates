# Booking Rescue — demo abierta de revisión con IA

Una aplicación de reservas pequeña con fallas intencionales. Es una demo independiente
del workshop: sirve para observar qué detecta una IA, qué propone y cómo verificamos
si realmente mejoró la arquitectura. No es un template para desplegar.

Python 3.11+, biblioteca estándar, sin cuentas ni servicios externos. Desde esta carpeta:

## Primer paso de la sesión: Docker y pensamiento crítico

El [Dockerfile](Dockerfile) contiene diez bloques de comentarios engañosos, listas de
paquetes supuestamente obligatorios, requisitos inventados y un fallo de arranque
intencional. Compártelo primero con la IA y pide una revisión antes de mostrarle el
resto del repositorio. Construye y ejecuta la imagen para contrastar la respuesta:

```sh
docker build -t booking-rescue:exercise .
docker run --rm booking-rescue:exercise
```

El segundo comando debe fallar: es parte del ejercicio. Con Docker puedes realizar
toda la sesión sin instalar Python ni dependencias en el host. Después de analizar
el fallo, ejecuta la aplicación con `docker run --rm booking-rescue:exercise python app.py`
y los tests con `docker run --rm booking-rescue:exercise python -m unittest discover -s tests -v`.

Las instalaciones de paquetes externos están comentadas. No las actives para hacer
la demo: observar si la IA las considera necesarias es parte de la evaluación.

Los scripts `scripts/run.py` y `scripts/test.py` repiten pasos de preparación ya hechos
en la imagen. La siguiente tarea es detectar y eliminar esa redundancia. La
[guía del facilitador](review/DOCKER_EXERCISE.md) explica las trampas, cómo puede fallar
un agente y qué guardrails exigir. Consultarla después de la primera revisión.

## Ejecución directa, si ya tienes Python

```sh
python3 app.py
python3 -m unittest discover -s tests -v
```

El ejemplo usa una carpeta temporal. Los tests iniciales muestran **2 casos correctos
y 4 fallas esperadas**. `OK (expected failures=4)` confirma el estado defectuoso de la
demo; no demuestra que cumple los requisitos.

## Contexto para analizar

Vendemos cupos para una clínica de arquitectura. Una reserva confirmada debe mantener
el precio acordado, consumir cupos una sola vez y sobrevivir a una caída del proveedor
de notificaciones. Los clientes pueden reenviar una solicitud por timeout; el mismo
`request_id` y contenido deben devolver la misma reserva. Reutilizar ese identificador
con contenido diferente debe rechazarse. La cantidad de cupos debe ser un entero positivo.
Si dos procesos reservan al mismo tiempo, no pueden exceder la capacidad ni perder datos.

El archivo JSON es el almacenamiento inicial; no hay pagos reales. Para la demo usamos
datos ficticios. Una solución puede seguir siendo un monolito local: cada nueva pieza
debe responder a un problema concreto.

## Cómo usarla con ChatGPT, Codex u otra IA

Abre esta carpeta con tu agente o adjunta `app.py`, `tests/test_booking.py` y este README
al chat. Pega [PROMPT.md](PROMPT.md). Si el chat no ejecuta código, corre tú los comandos
y comparte su salida. Primero pide un diagnóstico; después elige una propuesta y pide
la implementación. No basta con pedir «mejora este código».

Al verificar una corrección, conserva las aserciones y retira `expectedFailure` solamente
de los casos corregidos. Todos deben terminar pasando como tests normales para cerrar
la demo. Agrega cobertura para conflictos de idempotencia, recuperación de notificaciones
y reservas concurrentes; los tests iniciales no cubren todo el contrato.

Compara el resultado con [la guía de revisión](review/EXPECTED_FINDINGS.md) **después**
del análisis independiente. Si adjuntas toda la carpeta, la IA podrá ver esa guía:
el resultado será asistido por la solución y debe presentarse como tal.

La evaluación es humana: evidencia del fallo, relación con una decisión de arquitectura,
cambio justificado y prueba que lo verifica. Contar capas, archivos o patrones no mide calidad.
