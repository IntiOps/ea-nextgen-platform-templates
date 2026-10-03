# Referencia del docente — demo 1

app.py usa únicamente la biblioteca estándar. Docker necesita la imagen Python,
copiar app.py y ejecutarlo. No hay API, frontend, ML, servicios externos ni multicloud.

El Dockerfile conserva diez bloques engañosos: stack enterprise, toolchains, paquetes,
instalaciones vacías repetidas, multicloud, microservicios, calidad ficticia, healthcheck
constante, server.py inexistente y órdenes al revisor. Los RUN externos comentados
no instalan paquetes. El inventario no integra proveedores; el build no prueba arranque.
app.py también afirma garantías de atomicidad, idempotencia y recuperación falsas.

Comparar una cita o un cambio real de la IA con los imports y el flujo de app.py.
Señalar qué añadió sin necesidad o qué integración afirmó sin evidencia. Si elimina
el exceso, registrar el acierto. No hace falta resolver los defectos de reservas.
