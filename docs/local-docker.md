# Ejecutar local con Docker

Esta guia es solo para ejecucion local con Docker/Docker Compose. La configuracion de OpenShift esta en `docs/openshift-s2i.md`.

## Requisitos

- Docker y Docker Compose

## Pasos

1) Construir y levantar todo:

```bash
docker-compose up --build
```

2) Probar el API Gateway:

```bash
curl -X POST \
  "http://localhost:8000/iniciar-workflow/terminos" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id":"mi-usuario-123"}'
```

3) Verificar el control plane:

```bash
curl -sS http://localhost:8010/health
curl -sS http://localhost:8010/dashboard
```

4) UI de Temporal (modo dev):

- http://localhost:8233

## Parar y limpiar

```bash
docker-compose down
```

## Variables de entorno relevantes

- `TEMPORAL_SERVER` (default: `temporal:7233` en Docker Compose)
- `ENVIO_API_URL` (default: `http://host.docker.internal:8000/envio/despachar`)
- `CONTROL_PLANE_URL` (default: `http://control_plane:8010`)
