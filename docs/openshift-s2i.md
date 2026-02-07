# OpenShift con S2I (sin registry externo)

Esta guia usa S2I con el registry interno de OpenShift (ImageStream). No requiere Quay u otro registry externo.

## Requisitos

- Acceso a un cluster OpenShift
- CLI `oc`
- Proyecto/namespace creado

## Archivos

- Manifiestos base: `openshift/poc-s2i.yaml`
- Local Docker: `docs/local-docker.md`

## Flujo general

1) Crear proyecto:

```bash
oc new-project poc-temporal
```

2) Aplicar manifiestos (crea ImageStream, BuildConfig, Deployments, Services, Routes):

```bash
oc apply -f openshift/poc-s2i.yaml
```

3) Lanzar build desde el repo Git (build remoto):

```bash
oc start-build poc-temporal --follow
```

4) Verificar rutas:

```bash
oc get routes
```

## Pruebas rapidas

- API Gateway (Route):

```bash
curl -X POST \
  "http://<ROUTE_API_GATEWAY>/iniciar-workflow/terminos" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id":"mi-usuario-123"}'
```

- Control plane:

```bash
curl -sS http://<ROUTE_CONTROL_PLANE>/health
curl -sS http://<ROUTE_CONTROL_PLANE>/dashboard
```

- UI Temporal (opcional):

```text
http://<ROUTE_TEMPORAL_UI>
```

## Notas

- El build S2I genera una unica imagen con todo el repo y dependencias.
  Los Deployments usan la misma imagen y solo cambian el comando de arranque.
- Si quieres actualizar codigo, vuelve a ejecutar el `oc start-build`.
- La URL interna para la actividad de envio se resuelve con el Service:
  `http://api-gateway:8000/envio/despachar`.
