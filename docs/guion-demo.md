# Guion de la demo (7-8 min)

Antes de empezar: tener abierto el repo en GitHub (pestaña Actions), una terminal en la carpeta del proyecto y la pantalla en http://localhost:8000 con la API corriendo.

Para levantarla:

```
.venv\Scripts\activate
set API_KEY=demo-local
uvicorn app.main:app
```

## 1. La pantalla (1.5 min)

- Poner la llave y darle Entrar.
- Pedido normal: 2 de acetaminofén, teléfono 55123456, efectivo. Sale el número de pedido y Q17.00.
- Pedido con clonazepam sin receta: sale el aviso de que solo se vende con receta.
- El mismo pedido con receta MS-123456: sí pasa y baja la existencia.
- Enseñar abajo los últimos pedidos: el teléfono sale como 55****56.

## 2. Cambio limpio, pipeline en verde (2 min)

- Cambio pequeño en main (por ejemplo, agregar un producto en app/catalogo.py), commit y push.
- En Actions se ven los 4 controles en paralelo y luego imagen, despliegue y prueba de humo.

## 3. Librería vulnerable (1.5 min)

- Abrir la corrida de la rama `demo/dependencia`. Ahí se agregó `urllib3==1.24.1` a requirements.txt.
- Trivy falla con los CVE altos de esa versión y el paso de imagen y despliegue se salta.
- Si da tiempo, hacerlo en vivo: en otra rama `demo/...` agregar la misma línea y hacer push.

## 4. Llave en el código (1.5 min)

- Abrir la corrida de la rama `demo/secreto`. Ahí se pegó una llave falsa de una pasarela de pagos en app/main.py.
- Gitleaks la detecta y el pipeline queda en rojo.
- Explicar que aunque se borre después sigue en el historial y hay que cambiarla.

## 5. Cierre (30 s)

- Volver a la corrida en verde de main: nada llega a la farmacia sin pasar los cuatro controles. Las ramas `demo/` corren el pipeline pero nunca despliegan.

## Quién presenta qué

| Parte | Integrante |
|---|---|
| Problema de la farmacia, requisitos y C4 | Jonathan García |
| Calidad (ISO 25010) y pruebas | Walter Herrera |
| Pantalla, pipeline y demo en vivo | José Daniel Paz |
| Seguridad: CIA, OWASP y ejemplos que fallan | Julio Portillo |
