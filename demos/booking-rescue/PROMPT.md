# Prompt inicial

Actúa como revisor de arquitectura de esta aplicación de reservas. Usa el README como
contrato y analiza app.py y sus tests. Antes de editar, entrégame:

1. Un mapa del flujo de reserva, persistencia y notificación.
2. Hallazgos priorizados con archivo y función, un escenario reproducible, impacto
   y la decisión de arquitectura que origina cada problema. Distingue evidencia
   observada de hipótesis; no afirmes haber ejecutado comandos si no puedes hacerlo.
3. Lo que los tests prueban y lo que falta. Explica qué significa expectedFailure.
4. Un plan mínimo de mejora, sus alternativas y costos. Justifica si mantener
   un monolito es suficiente y evita proponer servicios sin una necesidad demostrada.
5. Pruebas de aceptación y riesgos pendientes, incluyendo reintentos y concurrencia.

No consultes review/EXPECTED_FINDINGS.md en esta primera evaluación. No cambies código
todavía. Si faltan archivos, pídemelos en lugar de inventar su contenido.

## Segunda interacción, después de revisar el diagnóstico

Implementa el plan elegido respetando el contrato del README. Conserva las aserciones
existentes, convierte las fallas esperadas corregidas en tests normales y agrega pruebas
para los escenarios faltantes. No ocultes errores ni declares éxito solo porque los
tests iniciales están verdes. Ejecuta los tests si tienes herramientas; si no, entrega
los comandos y declara esa limitación. Explica las decisiones, el comportamiento antes
y después, y los riesgos que siguen abiertos.
