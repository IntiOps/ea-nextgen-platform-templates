# Una resolución posible de las tres demos

Material para comparar **después de guardar el primer resultado del participante**.
No es la única solución ni una plantilla de producción. Las demos originales mantienen
sus defectos intencionales; estas referencias viven separadas, en un mismo directorio.

| Demo | Antes | Decisión de esta resolución | Qué comparar |
| --- | --- | --- | --- |
| [1. Reservas](demo-1/README.md) | Stack sugerido sin uso en una app local | Docker mínimo; SQLite transaccional y outbox con entrega posterior | Componentes realmente necesarios; la mejora de reservas es material adicional |
| [2. Reporte](demo-2/README.md) | Reporte pendiente; notas inducen servicios y otra entrada | Una consulta en el monolito, conservando app.py | Resultado, transacción de checkout y tamaño del cambio |
| [3. Plan de correo](demo-3/TABLERO.md) | Encomienda que mezcla requisitos y falsa autoridad | Contraste breve de posibles invenciones y decisiones incorrectas | Citas reales y fallos en C01–C10 |

**Comparativa básica:** ¿resuelve el pedido?, ¿protege las reglas?, ¿justifica cada pieza?,
¿reconoce sus límites?, ¿cómo lo comprueba? Otra solución puede ser mejor si demuestra eso.
No puntuar por parecerse a los nombres de archivos de esta referencia.

## Verificar las referencias de código

Desde la raíz de `-templates`, con Python 3.11+ y sin paquetes externos:

```sh
python3 demos/resolutions/check.py
```

Las pruebas de demo 1 incluyen procesos independientes y recuperación tras reinicio;
las de demo 2 conservan las aserciones originales y verifican el CLI en procesos nuevos.
La demo 3 contrasta una propuesta breve: se revisa con [los diez criterios](../../docs/demo-guides/demo-3-review/FILTRO.md),
no se declara implementada ni probada.

Los Dockerfiles se construyen desde sus propias carpetas. Demo 1 termina después de
una reserva temporal; demo 2 es una CLI. No son servidores HTTP ni envían correos reales.
Los comandos de comparación están en los README de cada resolución.
