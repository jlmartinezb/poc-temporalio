import os
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError
from typing import Any, Dict
from .shared import EnvioRequest

@activity.defn
async def despachar_envio_activity(request: EnvioRequest) -> dict:
    """
    Actividad para simular una llamada a una API externa de envíos.
    Esta actividad gestiona los errores para permitir reintentos inteligentes.
    """
    activity.logger.info(f"Intentando despachar envío para {request.usuario_id}...")

    # Por defecto usamos host.docker.internal para contenedores.
    api_url = os.environ.get(
        "ENVIO_API_URL",
        "http://host.docker.internal:8000/envio/despachar",
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                api_url,
                json=request.__dict__,
                timeout=5.0
            )
            # Si la API externa devuelve un error (>= 400), esto lanzará una excepción.
            response.raise_for_status()
            activity.logger.info("¡Llamada a la API de envío exitosa!")
            return response.json()
        except httpx.HTTPStatusError as e:
            # Si es un error 4xx (error del cliente), lo marcamos como NO reintentable.
            if 400 <= e.response.status_code < 500:
                activity.logger.error(f"Error de cliente no reintentable {e.response.status_code} desde la API de envío.")
                raise ApplicationError(f"Error de API no reintentable: {e.response.text}", type="NonRetryableAPIError", non_retryable=True)

            # Para errores 5xx (error del servidor), relanzamos para que Temporal reintente.
            activity.logger.warning(f"La API de envío falló con status {e.response.status_code}. Reintentando...")
            raise
        except httpx.RequestError as e:
            # Errores de red son candidatos perfectos para reintentos.
            activity.logger.error(f"Error de red al llamar a la API de envío: {e}. Reintentando...")
            raise
