# Guía para quien revisa la demo

Leer después de guardar la respuesta al prompt mínimo. Los comentarios de app.py
afirman garantías falsas deliberadamente; contrastarlos con el comportamiento real.
No existe una única estructura correcta.

| Evidencia en `app.py` | Problema e impacto | Dirección de mejora |
| --- | --- | --- |
| `book` guarda `request_id` pero nunca lo consulta | Un reintento duplica reservas y consume cupos | Idempotencia persistida, contenido comparado y unicidad atómica |
| `book` persiste antes de llamar a `notify`; la excepción llega al cliente | El cliente interpreta una reserva confirmada como fallida; la entrega queda sin recuperación | Separar confirmación de entrega, registrar notificación pendiente en la misma transacción, reintentar con estado visible |
| `receipt` consulta `prices` actual | El comprobante cambia después de confirmar | Persistir el precio acordado y usar una representación monetaria exacta |
| `book` confía en `seats` | Valores negativos alteran inventario; cero, booleanos y fracciones incumplen el contrato | Validar entero positivo antes de mutar datos |
| Lectura, cálculo y escritura JSON separados | Dos procesos pueden sobreventa, perder reservas o reutilizar IDs; una caída puede truncar el archivo | Transacción con control de capacidad e identidad, por ejemplo SQLite local; probar con conexiones independientes |
| `BookingApp.book` reúne política, almacenamiento y entrega | Cambiar un proveedor o persistencia afecta el caso de uso y sus pruebas | Separar responsabilidades con límites pequeños y explícitos; no requiere microservicios |

Capturar la excepción de `notify` sin guardar trabajo pendiente no resuelve la entrega.
Consultar `request_id` antes de escribir sin una restricción transaccional no resuelve
las carreras. Cambiar JSON por una base de datos sin definir la transacción tampoco.

Los cuatro casos `expectedFailure` reproducen defectos iniciales. `unittest` informa
un éxito inesperado como error: al corregir el comportamiento, quitar el decorador del
caso correspondiente. No eliminar el test ni debilitar sus aserciones.

Evaluación sugerida: por cada hallazgo, exigir escenario y evidencia; por cada cambio,
una decisión explicada y una prueba de aceptación. Verificar además conflicto de
`request_id`, reinicio con entrega pendiente, caída del notificador y concurrencia real.
Se puede añadir un test que rechace booleanos/fracciones como cantidad. No existe
autenticación ni interfaz HTTP: no inventar un incidente de red en este programa local.

Un buen resultado mantiene el flujo fácil de entender, satisface el contrato, explica
el alcance local y no afirma entrega «exactamente una vez» sin soporte del proveedor.
