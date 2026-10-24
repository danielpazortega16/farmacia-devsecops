# Farmacia - pedidos con pipeline DevSecOps

Proyecto del curso Ingeniería de Software I (URL, 2do ciclo 2026), Grupo 04, tema DevSecOps.

## El problema

Una farmacia de barrio recibe la mayoría de sus pedidos por WhatsApp. Hoy los anotan en un cuaderno, cobran como pueden y nadie revisa si un medicamento controlado (clonazepam, tramadol) salió con receta. Eso genera faltantes de inventario, cobros mal hechos y un riesgo legal con el Ministerio de Salud.

El prototipo es una API que registra los pedidos: calcula el total con los precios de la base (no los que manda el cliente), bloquea controlados sin número de receta, descuenta existencias y guarda el teléfono del cliente enmascarado.

Como el sistema maneja datos de salud y de pago, cada cambio al código pasa por un pipeline que no deja desplegar nada con secretos expuestos, con fallas de código o con dependencias vulnerables.

## Pipeline

Cada push corre `.github/workflows/devsecops.yml`:

1. Gitleaks: busca llaves y contraseñas en todo el historial.
2. Pruebas unitarias con pytest.
3. Semgrep (SAST) con reglas de Python y OWASP Top 10.
4. Trivy (SCA): falla si alguna dependencia tiene un CVE alto o crítico.
5. Si todo pasa: construye la imagen Docker, la escanea, la publica en GHCR, la levanta y le hace una prueba de humo.

Si cualquiera de los primeros cuatro falla, no se construye ni se despliega nada.

Las ramas `demo/dependencia` y `demo/secreto` tienen a propósito una librería vulnerable y una llave en el código, para enseñar en la demo cómo se bloquean. En las ramas `demo/` el pipeline corre pero nunca despliega.

La pantalla para la dependiente está en `http://localhost:8000/` y usa la plantilla [Tabler](https://tabler.io).

## Correrlo local

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -v
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

Todos menos `/salud` piden el encabezado `X-API-Key`.

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
