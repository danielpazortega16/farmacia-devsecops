#!/usr/bin/env bash
# Baja la base de vulnerabilidades de Trivy antes de escanear.
# Si un espejo falla se prueba el siguiente; asi un rojo en Trivy
# significa una dependencia vulnerable y no un problema de red.
set -u
for repo in mirror.gcr.io/aquasec/trivy-db:2 public.ecr.aws/aquasecurity/trivy-db:2 ghcr.io/aquasecurity/trivy-db:2; do
  for intento in 1 2; do
    echo "Descargando base desde $repo (intento $intento)"
    if docker run --rm -v trivy-cache:/root/.cache aquasec/trivy:0.58.1 \
         image --download-db-only --db-repository "$repo"; then
      exit 0
    fi
    sleep 10
  done
done
echo "No se pudo descargar la base de vulnerabilidades"
exit 1
