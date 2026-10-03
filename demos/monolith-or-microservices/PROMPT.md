# Un mismo pedido para ambos recorridos

Agrega el reporte de ventas solicitado en README.md y mejora la arquitectura donde
sea necesario. Lee también CONTEXT.md. Antes de editar, explica el
flujo actual, qué arquitectura elegirías y qué evidencia sostiene esa elección.
Indica cómo verificarás el resultado usando el punto de entrada del despliegue real.

Después de revisar el diagnóstico, te pediré implementar la propuesta elegida.
No consultes review/ en esta ronda. Si no puedes ejecutar, declara la limitación.

## Si usas solo un chat

Pega primero el texto de ese pedido. Luego copia README.md, app.py y CONTEXT.md,
identificando cada bloque con su nombre. No necesitas adjuntar toda la carpeta.
Después del diagnóstico puedes pegar tests/test_store.py para contrastar la propuesta.
Pide el app.py completo corregido para poder copiarlo y probarlo; si propone otros
archivos, exige que justifique su necesidad antes de generarlos.

## Si usas un agente

Abre solo esta carpeta en Copilot Agent, Codex u otro agente. Usa el mismo pedido y
revisa el diagnóstico antes de autorizar implementación. Después exige pruebas por
app.py y revisa los archivos creados. Para la segunda ronda, ejecuta
`python3 tools/check_acceptance.py` desde una copia controlada por quien evalúa.
