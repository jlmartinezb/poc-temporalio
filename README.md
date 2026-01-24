# PoC Temporal: Terminos y Condiciones

PoC de Temporal que modela el ciclo de compra con carrito, aceptacion de terminos, envio y confirmacion de entrega.

## Documentacion

- Local con Docker: `docs/local-docker.md`
- OpenShift (S2I): `docs/openshift-s2i.md`
- Comandos curl: `docs/curl-commands.md`

## Componentes

- Workflow: `terminos_y_condiciones/workflows.py`
- Actividad de envio: `terminos_y_condiciones/activities.py`
- Worker: `terminos_y_condiciones/run_worker.py`
- API Gateway: `api_gateway/service.py`
- Control plane: `control_plane/service.py`

## Variables de entorno (resumen)

- `TEMPORAL_SERVER` (default: `localhost:7233`)
- `ENVIO_API_URL` (default: `http://host.docker.internal:8000/envio/despachar`)
