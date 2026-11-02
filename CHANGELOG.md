# Cambios

Versionamiento semántico: MAYOR.MENOR.PARCHE.

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
