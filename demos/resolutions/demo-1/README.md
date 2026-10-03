# Resolución 1 — Persistir la decisión y entregar después

**Elegimos:** monolito local, SQLite, centavos enteros y outbox. No hacen falta paquetes
HTTP, ML, brokers ni cloud para el contrato de esta demo.

| Problema original | Resolución | Evidencia |
| --- | --- | --- |
| server.py no existe; build confundido con arranque | Docker ejecuta app.py, sin preparación repetida | Construir y ejecutar la imagen |
| Reintento duplica reservas | request_id único, contenido comparado en transacción | Identidad repetida y conflicto; procesos independientes |
| Cupos calculados sin exclusión | BEGIN IMMEDIATE serializa comprobación e inserción | Cuatro procesos compiten por dos cupos |
| Precio recalculado y cantidades inválidas | Precio acordado en centavos; entero positivo sin aceptar bool | Cambio de precio y cantidades negativas/cero/fraccionarias |
| Correo falla después de guardar | Reserva e intención se guardan juntas; process_one entrega después | Caída del proveedor, rollback y reinicio |
| Reintentos sin recuperación visible | Estado, intentos, backoff y lease para recuperar trabajo | Recuperación de lease y límite de fallos |

`book` ya no envía automáticamente: confirma una reserva y deja trabajo durable.
El consumidor llama a `process_one`. Las aserciones de identidad/cupos/precio se
mantienen; las de notificación se verifican después del paso de entrega. El almacenamiento
cambia de JSON a una base **nueva**: esta referencia no migra archivos de usuarios.

```sh
python3 -m unittest discover -s tests -v
python3 app.py
docker build -t booking-rescue:resolved .
docker run --rm booking-rescue:resolved
```

Ejecutar desde esta carpeta. La app usa un directorio temporal; los tests usan bases aisladas.

**Límites:** catálogo/precios/capacidad están en memoria y se suponen iguales entre
procesos. SQLite serializa escrituras; no es una solución multirregión. El adaptador
de notificación debe tener timeout menor al lease de 30 segundos. Después de cinco
excepciones registradas, el trabajo queda failed para revisión manual; un crash no es
una excepción registrada. No hay scheduler ni consola de operación implementados.

Una caída después de enviar y antes de registrar puede repetir la notificación:
un test demuestra esa ventana. El token evita que un worker vencido marque el estado
de otro, pero no deshace un envío externo. Sin idempotencia del proveedor no prometemos
exactly-once. Los valores de lease/reintentos son didácticos, no calibrados con un proveedor.

**Otra resolución válida:** otro almacenamiento transaccional y mecanismo durable,
si demuestra las mismas invariantes y explica sus costos.
