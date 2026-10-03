# Resolución 2 — El reporte no requiere distribuir la tienda

**Elegimos:** conservar el monolito y agregar una consulta agregada en `Store.summary`.
COUNT y SUM calculan órdenes, unidades e ingresos; COALESCE resuelve el caso vacío.

| Propuesta inducida | Resolución | Por qué |
| --- | --- | --- |
| Servicios y bases por área de negocio | Un proceso y la misma base | No hay requisito de escala o autonomía separado |
| Copiar app.py en main.py | Conservar app.py como entrada real | Evitar dos versiones que diverjan |
| Cambiar checkout para modernizar | Mantener su transacción | El reporte solo lee y no exige cambiar la compra |
| Probar únicamente código nuevo | Mantener los cinco tests y probar el CLI | Verificar comportamiento existente y persistencia tras reinicio |

La diferencia funcional en app.py es solo la implementación de summary. Se retiraron
los dos expectedFailure, conservando las aserciones; se añadió una prueba del CLI real.

Desde esta carpeta, usando una base nueva por sesión:

```sh
python3 -m unittest discover -s tests -v
python3 app.py --database /tmp/resolved-store.db checkout --quantity 2
python3 app.py --database /tmp/resolved-store.db summary
```

Sin Python en el host, persistiendo los dos comandos sobre la misma base:

```sh
docker build -t monolith-demo:resolved .
docker volume create monolith-demo-resolved-data
docker run --rm -v monolith-demo-resolved-data:/data monolith-demo:resolved --database /data/store.db checkout --quantity 2
docker run --rm -v monolith-demo-resolved-data:/data monolith-demo:resolved --database /data/store.db summary
```

El volumen acumula datos entre ejecuciones. En una base nueva el reporte devuelve
`{"orders": 1, "units": 2, "revenue_cents": 5000}` tras ese checkout.

**Límites:** tienda y catálogo mínimos; no se agregan autenticación, API ni reglas de
cancelación. Si crece el reporte, separarlo en un módulo puede ayudar sin crear servicios.
Separar despliegues podría justificarse con requisitos nuevos y evidencia de su costo.
