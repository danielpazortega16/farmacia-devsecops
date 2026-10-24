# Guion de la demo (7-8 min)

Antes de empezar: tener abierto el repo en GitHub (pestaña Actions), una terminal en la carpeta del proyecto y la pantalla en http://localhost:8000 con la API corriendo.

## 1. La app funcionando (1.5 min)

- Poner la llave y cargar productos.
- POST /api/v1/ventas con acetaminofén: 201, total 17.00.
- Mismo POST con `"total": "0.01"`: el total sigue en 17.00 porque lo calcula el servidor.
- POST con CLZ2 (clonazepam) sin receta: 400. Con `"numero_receta": "MS-123456"`: 201.
- GET de la venta: el teléfono sale como 55****56.

## 2. Commit limpio, pipeline en verde (2 min)

- Cambio pequeño (por ejemplo, agregar un producto al catálogo), commit y push.
- En Actions se ven los 4 controles en paralelo y luego la imagen, el despliegue y la prueba de humo.

## 3. Dependencia vulnerable (1.5 min)

- En una rama `demo/dependencia`: agregar `requests==2.19.0` a requirements.txt, push y abrir un PR.
- Trivy falla con los CVE de esa versión y el job de imagen nunca corre.

## 4. Secreto en el código (1.5 min)

- En una rama `demo/secreto`: pegar en app/main.py una llave con forma de llave de Stripe en vivo (`sk_live_` + 24 caracteres al azar).
- Gitleaks la detecta y el pipeline queda en rojo.
- Explicar que, aunque se borre después, sigue en el historial y hay que rotarla.

## 5. Cierre (30 s)

- Volver al run en verde: ningún artefacto llega a la imagen sin pasar por los cuatro controles.

## Quién presenta qué

| Parte | Integrante |
|---|---|
| Problema de la farmacia y requisitos | Jonathan García |
| Arquitectura C4 y trade-offs | José Ricardo Guerra |
| Calidad (ISO 25010) y pruebas | Walter Herrera |
| Pipeline y demo en vivo | José Daniel Paz |
| Seguridad: CIA y OWASP | Julio Portillo |
