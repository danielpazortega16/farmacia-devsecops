# Cambios

Versionamiento semántico: MAYOR.MENOR.PARCHE.

## 1.1.0 - 2026-11-03

Correcciones de la revisión de la fase 3.

- `Idempotency-Key` en `POST /api/v1/ventas`: un reintento por red ya no registra el pedido dos veces. Antes el doble clic solo se evitaba en el navegador.
- Arreglo: una llave con ñ o acentos tiraba la API con un 500. Ahora es 401.
- Los errores no controlados salen con los encabezados de seguridad y quedan en la bitácora.
- Arreglo: las claves foráneas de SQLite estaban apagadas.
- Se aceptan teléfonos que empiezan con 8 y 9.
- `/docs`, `/redoc` y `/openapi.json` apagados.
- El número de receta sale enmascarado en la API.
- mypy en el trabajo de pruebas; arreglado `precio`, que era `Decimal` en un bucle y texto en el otro.
- Semgrep revisa todo el repositorio y las acciones de GitHub quedan fijadas por commit.
- El despliegue ya no usa una llave escrita en el workflow: toma el secreto `API_KEY_STAGING` o, si no existe, genera una al azar para esa corrida.
- Pruebas nuevas: los dos 404, pedido rechazado a medias sin descontar inventario, y concurrencia por HTTP con llave.

## 1.0.0 - 2026-11-02

Versión para la presentación final.

- DAST con OWASP ZAP sobre el contenedor desplegado.
- SBOM de la imagen en formato CycloneDX.
- Cobertura mínima de 90 % en las pruebas.
- Encabezados de seguridad (CSP, X-Frame-Options, X-Content-Type-Options) y el servidor ya no dice qué versión usa.
- Bitácora en JSON de peticiones y ventas, sin datos del cliente.
- `/salud` devuelve la versión.
- Arreglo: las conexiones a la base no se cerraban.
- Arreglo: Trivy fallaba cuando no podía bajar su base de datos, aunque las dependencias estuvieran bien.

## 0.2.0 - 2026-10-23

Hito 2.

- Pantalla para la dependiente con Tabler.
- Ramas `demo/dependencia` y `demo/secreto` para la demo.
- Arreglo: el mismo producto en dos líneas pasaba la revisión de existencias.
- Arreglo: ventas al mismo tiempo dejaban el inventario en negativo.
- Arreglo: doble clic creaba dos pedidos.

## 0.1.0 - 2026-10-23

- API de pedidos con receta, existencias y total calculado en el servidor.
- Pipeline con Gitleaks, pytest, Semgrep, Trivy y despliegue de la imagen.
