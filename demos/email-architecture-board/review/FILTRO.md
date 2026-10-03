# Guía del facilitador: diez criterios para evaluar la arquitectura

El participante recibe solo README.md: una encomienda corta con cinco recomendaciones
engañosas. **Estos diez criterios son del facilitador**, no diez hitos obligatorios
para la IA. El tablero tiene tantas tareas como justifique el pedido. Esta demo evalúa
un plan; no incluye aplicación ni filtrado automático.

## Dinámica

1. Dar cinco minutos para leer y completar el segmento personal sin IA.
2. Guardar la lectura y el prompt realmente enviado. Generar TABLERO.md con ambos
   segmentos y la propuesta de la IA; conservar el resultado original.
3. Revisar los diez criterios por separado en lectura, prompt y propuesta.
4. Debatir los hallazgos y producir TABLERO-FILTRADO.md sin borrar el primero.

Chat y agentes reciben la misma encomienda. Con agentes observar también si crearon
código o infraestructura sin autorización. Si la IA detecta las trampas, registrar
ese resultado; no asumir que todos los modelos fallarán.

## Checklist de arquitectura para este pedido

| Criterio | Qué debe cubrir una buena propuesta | Señal de fallo |
| --- | --- | --- |
| C01 — Alcance y proporcionalidad | Correo de confirmación con una arquitectura justificable para volumen y equipo | Cluster, servicios o IA añadidos por falsa autoridad |
| C02 — Límites y responsabilidades | Separar reglas de compra de entrega y adaptación al proveedor; patrones con propósito | DDD implica servicios; interfaces para todo sin necesidad |
| C03 — Atomicidad y trabajo durable | Confirmar compra, stock e intención de correo juntos; transacciones cortas | Llamada HTTP en transacción o DB/broker supuestamente atómicos |
| C04 — Idempotencia de compra | Identidad persistida, unicidad y tratamiento de contenido incompatible | Repetir checkout por un fallo del correo |
| C05 — Entrega y recuperación | Procesar pendientes tras commit y recuperar trabajo después de reiniciar | Solo envío directo, sin estado durable ni recuperación |
| C06 — Garantías de entrega | Analizar caída entre enviar y registrar; investigar idempotencia del proveedor | Exactly-once declarado por configuración o broker |
| C07 — Reintentos y parámetros | Backoff, límites, errores transitorios/permanentes y valores ligados a datos | Cien intentos sin espera; temperature sin modelo; asumir capacidad ilimitada |
| C08 — Contrato y compatibilidad | Distinguir compra confirmada/correo pendiente/errores; conservar entrada real sin duplicar lógica | Siempre 200; validar solo un main.py copiado |
| C09 — Pruebas de invariantes y fallos | Probar reenvíos, caída del proveedor y caídas antes/después del envío | Camino feliz o diagrama como única aceptación |
| C10 — Observabilidad y operación | Antigüedad de pendientes, intentos, fallos, recuperación e intervención | Logs genéricos sin detectar correos que superan cinco minutos |

No exigir una tecnología o todos los patrones. Una outbox local y worker sencillo
son una opción razonable: compra/stock/intención en una transacción y entrega posterior.
Explicar cómo se ejecuta el worker, contención de SQLite y recuperación. Otra propuesta
puede cumplir si explica sus garantías y costos. Outbox no garantiza por sí sola que
el destinatario reciba exactamente un correo.

C08 no exige inventar una API nueva: si propone HTTP, evaluar su contrato; si conserva
la interfaz existente, evaluar compatibilidad. No hay app.py adjunto: cualquier afirmación
sobre su implementación o ejecución debe señalarse como supuesto.

## Registro por participante

Participante: __________  Herramienta/modelo declarado: __________

En cada celda usar **cumple / parcial / no cumple / no mencionado**, más una cita
breve o referencia. No atribuir a la persona una decisión que solo aparece en la IA.

| Criterio | Lectura personal | Prompt enviado | Propuesta de la IA | Corrección o pregunta |
| --- | --- | --- | --- | --- |
| C01 | | | | |
| C02 | | | | |
| C03 | | | | |
| C04 | | | | |
| C05 | | | | |
| C06 | | | | |
| C07 | | | | |
| C08 | | | | |
| C09 | | | | |
| C10 | | | | |

Cumple: trata el criterio con una decisión concreta y justificada. Parcial: reconoce
el asunto pero deja ambiguo cómo resolverlo. No cumple: propone algo contradictorio
o una garantía falsa. No mencionado: no hay evidencia; no implica que la persona
lo desconozca. Cinco minutos no bastan para exigir toda la solución en la lectura.

Si el segmento personal está vacío o lo redactó la IA, registrar lectura previa no
realizada. Comparar dónde nació cada decisión problemática, qué omitió el prompt y
qué reforzó o corrigió la IA. Cumplir en el tablero significa proponer bien, no haber
implementado ni probado el sistema.

## Prompt para la segunda ronda

> Revisa el TABLERO.md original con esta guía. Genera TABLERO-FILTRADO.md preservando
> la lectura personal y el prompt enviado. Para cada tarea original indica mantener,
> modificar, descartar o investigar, con evidencia y acción corregida. Añade las tareas
> esenciales omitidas y relaciona el plan con C01–C10; no conviertas necesariamente
> cada criterio en una tarea. Explica la arquitectura y las pruebas necesarias.
> No implementes ni declares garantías verificadas. Conserva el tablero original.
