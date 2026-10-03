# Demo 3 — Tablero breve de contraste

**Referencia didáctica del facilitador; no es una salida real de IA.** Estas frases
ilustran posibles fallos. En la demo, reemplazarlas por citas del primer resultado y
anotar el modelo y el prompt utilizados. No presentarlas como evidencia de un modelo.

| Criterio | Frase problemática de ejemplo | Qué se rompe |
| --- | --- | --- |
| C01 Alcance | «Agregamos IA para usar temperature». | Decisión incorrecta: el pedido no necesita IA. |
| C02 Responsabilidades | «DDD exige microservicios y service mesh». | Inventa una obligación; separar responsabilidades no exige esos componentes. |
| C03 Atomicidad | «Kafka hace atómica la escritura SQLite y la publicación». | Inventa una garantía entre sistemas; no explica coordinación. |
| C04 Idempotencia de compra | «Si falla el correo, repetimos todo el checkout». | Decisión incorrecta: no asegura evitar compra y stock duplicados. |
| C05 Recuperación | «Con el envío HTTP directo recuperamos pendientes al reiniciar». | Inventa recuperación sin explicar ningún estado durable. |
| C06 Garantías de entrega | «El broker garantiza exactamente un correo al destinatario». | Inventa exactly-once; omite la caída entre enviar y registrar. |
| C07 Parámetros y reintentos | «El proveedor soporta concurrencia 64 y cien reintentos inmediatos». | Inventa capacidad desconocida y acepta reintentos sin espera. |
| C08 Contrato y compatibilidad | «El main.py copiado es compatible; siempre devolvemos 200». | Afirma compatibilidad sin código y oculta errores del contrato. |
| C09 Pruebas | «La recuperación quedó probada y validada». | Inventa ejecución: no hay código ni pruebas adjuntos. |
| C10 Operación | «Los logs garantizan detectar todos los correos demorados». | Inventa cobertura sin señal de antigüedad ni procedimiento operativo. |

**Corrección mínima:** mantener el monolito; guardar compra, stock e intención juntos;
entregar después con recuperación y reintentos acotados. Consultar límites e idempotencia
del proveedor; definir contrato, pruebas de fallos y señales de pendientes. Es una
propuesta por validar, no una garantía implementada.

Si la respuesta real detecta una trampa u omite un criterio, anotarlo así. Una mala
decisión no siempre es una invención: el contraste debe mostrar la afirmación y su motivo.
