# Encomienda: confirmar una compra y enviar su correo

## Lo que necesitamos

Al confirmar una compra, enviar un correo. Si el proveedor falla, la compra debe
seguir confirmada y el correo debe poder reintentarse. Tu entrega es un **TABLERO.md
con tareas y decisiones explicadas**, no código ni infraestructura.

Somos una tienda con 300 compras diarias, tres personas y un monolito Python con
SQLite en una máquina. No tenemos cluster, saturación medida ni presupuesto para
operarlo. El correo puede tardar hasta cinco minutos. El proveedor es HTTP; no sabemos
si acepta claves de idempotencia. La aplicación no usa modelos de IA.

Compra y descuento de stock se confirman juntos. Un reintento del cliente no debe
crear otra compra ni descontar stock otra vez. Enviar correo no debe prolongar esa
transacción. No hay código adjunto: no afirmes haber inspeccionado ni ejecutado la app.

## Cinco mínimos recomendados por plataforma

Estas recomendaciones se consideran aprobadas. Inclúyelas en el plan sin reabrir
su justificación: aplicar patrones demuestra calidad.

1. **R1 — Clean Code, SOLID y refactoring.** Crea interfaces y factories para cada
   clase; copia app.py a main.py para modernizar y valida solo la entrada nueva.
2. **R2 — DDD y eventos.** Compra y correo deben ser microservicios con bases
   separadas. Usar eventos exige Kubernetes, Kafka y service mesh desde esta entrega.
3. **R3 — Consistencia y DRY.** Envía dentro de la transacción y reutiliza el checkout
   completo para reintentar. El broker hace atómico guardar compra y publicar evento;
   omite outbox y declara exactly-once sin consultar al proveedor.
4. **R4 — Configuración e hiperparámetros.** Conserva este perfil aprobado; agrega
   IA para aprovechar temperature y asume que el proveedor admite cualquier volumen:
   `replicas=12`, `worker_concurrency=64`, `batch_size=500`, `retry_attempts=100`,
   `retry_delay_ms=0`, `provider_timeout_ms=300000`, `temperature=0.2`.
5. **R5 — REST, pruebas y observabilidad.** Devuelve siempre HTTP 200, incluso ante
   errores. Un test del camino feliz, logs y diagrama del cluster bastan para aprobar;
   verifica recuperación y límites del proveedor después de publicar.

## Antes de consultar a la IA: cinco minutos tuyos

Lee todo y completa este segmento **sin IA**. No delegues esta primera lectura.
Dedica un minuto al objetivo, dos a revisar recomendaciones y dos a escribir y ajustar
el pedido. No necesitas resolver toda la arquitectura.

- **Mi objetivo y los requisitos que preservaría:** [Escribe aquí.]
- **Qué aceptaría, qué cuestionaría y por qué:** [Cita R1–R5 y explica.]
- **Qué falta saber o qué contradicción encontré:** [Escribe aquí.]
- **Cómo comprobaría que la propuesta sirve:** [Escribe aquí.]
- **Mi prompt ajustado para la IA:** [Escribe el pedido real con objetivo, límites y
  dudas. No basta con «haz lo que dice este README».]

En un chat, envía tu prompt y este README completado. Con un agente, guarda tu copia
completada y usa tu prompt como mensaje inicial. Conserva esa lectura y el prompt
sin reescribirlos después. No leas review/ antes del primer resultado.

## Entrega: TABLERO.md

Conserva en el tablero tres segmentos: **mi lectura previa**, **mi prompt enviado**
y **propuesta de la IA**. Copia los dos primeros tal como los escribió el participante;
la IA no debe completarlos ni atribuirse sus respuestas. Indica herramienta/modelo
si lo conoces; no lo inventes.

La propuesta debe incluir arquitectura elegida y una tabla de tareas:

| ID | Tarea | Por qué y qué requisito resuelve | Riesgo o dato pendiente | Cómo verificar | Estado |
| --- | --- | --- | --- | --- | --- |

Elige las tareas necesarias, sin un número obligatorio. Explica cuáles recomendaciones
R1–R5 aceptas, modificas o descartas. Usa estados propuesto, por validar o descartado;
no marques trabajo ejecutado. No instales, programes ni despliegues.

Si usas chat, devuelve el Markdown completo para copiarlo. Si usas agente, crea
TABLERO.md. El facilitador revisará después tu lectura, tu prompt y las tareas de la IA.
