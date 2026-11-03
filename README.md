# Farmacia - pedidos con pipeline DevSecOps

Proyecto del curso Ingeniería de Software I (URL, 2do ciclo 2026), Grupo 04, tema DevSecOps.

## El problema

Una farmacia de barrio recibe la mayoría de sus pedidos por WhatsApp. Hoy los anotan en un cuaderno, cobran como pueden y nadie revisa si un medicamento controlado (clonazepam, tramadol) salió con receta. Eso genera faltantes de inventario, cobros mal hechos y un riesgo legal con el Ministerio de Salud.

El prototipo es una API que registra los pedidos: calcula el total con los precios de la base (no los que manda el cliente), bloquea controlados sin número de receta, descuenta existencias y guarda el teléfono del cliente enmascarado.

Como el sistema maneja datos de salud y de pago, cada cambio al código pasa por un pipeline que no deja desplegar nada con secretos expuestos, con fallas de código o con dependencias vulnerables.

## Pipeline

Cada push corre `.github/workflows/devsecops.yml`:

1. Gitleaks: busca llaves y contraseñas en el historial de la rama.
2. Revisión de tipos con mypy y pruebas con pytest. Si la cobertura baja de 90 % el paso falla.
3. Semgrep (SAST) con reglas de Python y OWASP Top 10, sobre todo el repositorio: código, pruebas, el propio workflow y el Dockerfile. Las acciones de GitHub están fijadas por commit, no por etiqueta.
4. Trivy (SCA): falla si alguna dependencia tiene un CVE alto o crítico. La base de vulnerabilidades se baja antes en un paso aparte, con tres espejos, para que un rojo aquí sea siempre una dependencia y no un problema de red.
5. Si todo pasa: construye la imagen Docker, la escanea, genera el SBOM (CycloneDX), la publica en GHCR, la levanta y le hace una prueba de humo.
6. DAST con OWASP ZAP sobre el contenedor ya levantado. Falla si faltan los encabezados de seguridad (reglas en `.zap/reglas.tsv`).

El despliegue usa la llave del secreto `API_KEY_STAGING`; si el secreto no existe, se genera una llave al azar que solo vive en esa corrida. Ya no hay una llave por defecto escrita en el workflow.

Los pasos 1 a 4 corren en paralelo. Si cualquiera falla, no se construye ni se despliega nada. El reporte de ZAP y el SBOM quedan como artefactos de cada corrida.

Las ramas `demo/dependencia` y `demo/secreto` tienen a propósito una librería vulnerable y una llave en el código, para enseñar en la demo cómo se bloquean. En las ramas `demo/` el pipeline corre pero nunca despliega.

La pantalla para la dependiente está en `http://localhost:8000/` y usa la plantilla [Tabler](https://tabler.io).

## Correrlo local

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -v --cov=app
set API_KEY=una-llave-local
uvicorn app.main:app --reload
```

Con Docker:

```
docker build -t farmacia .
docker run -p 8000:8000 -e API_KEY=una-llave-local farmacia
```

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | /salud | estado del servicio |
| GET | /api/v1/productos | catálogo con existencias |
| POST | /api/v1/ventas | registra un pedido |
| GET | /api/v1/ventas | últimos 10 pedidos |
| GET | /api/v1/ventas/{id} | consulta un pedido |

Todos menos `/salud` piden el encabezado `X-API-Key`. `/salud` devuelve también la versión que está corriendo. La documentación automática de FastAPI (`/docs`, `/redoc`, `/openapi.json`) está apagada.

`POST /api/v1/ventas` acepta el encabezado opcional `Idempotency-Key` (8 a 64 letras, números o guiones). Si llega dos veces la misma clave con el mismo pedido, el servidor devuelve la venta ya guardada en vez de crear otra y descontar inventario dos veces; con la misma clave y otro pedido responde 409. La pantalla manda una clave nueva por pedido y la reutiliza si la red falla.

En los listados el teléfono y el número de receta salen enmascarados (`55****56`, `MS-****56`). La receta completa queda en la base para auditoría.

## Operación

La API escribe una línea JSON por cada petición (ruta, código y milisegundos) y por cada venta aprobada o rechazada con su motivo. No se escribe el teléfono ni el número de receta. En Docker se ven con `docker logs farmacia`.

## Versiones

Se usa versionamiento semántico. Los cambios de cada versión están en [CHANGELOG.md](CHANGELOG.md) y cada versión tiene su etiqueta en git (`git tag`).

Ejemplo de pedido:

```json
{
  "telefono": "55123456",
  "items": [{"codigo": "PAR500", "cantidad": 2}],
  "metodo_pago": "efectivo"
}
```

## Equipo

- Jonathan Josué García González
- Walter José Herrera Salvatierra
- José Daniel Paz Ortega
- Julio Javier Portillo Veliz
- José Ricardo Guerra Morales
