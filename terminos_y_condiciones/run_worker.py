import asyncio
import os
import socket
import httpx
from temporalio.client import Client
from temporalio.worker import Worker

from .workflows import TerminosYCondicionesWorkflow
from .activities import despachar_envio_activity

async def main():
    # Conexión al servicio de Temporal
    temporal_server = os.environ.get("TEMPORAL_SERVER", "localhost:7233")
    client = await Client.connect(temporal_server)

    # Crear un worker que ejecute el workflow y las actividades
    task_queue = "terminos-y-condiciones-task-queue"
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[TerminosYCondicionesWorkflow],
        activities=[despachar_envio_activity],
    )

    control_plane_url = os.environ.get("CONTROL_PLANE_URL", "http://localhost:8010")
    heartbeat_interval = float(os.environ.get("WORKER_HEARTBEAT_SEC", "5"))
    worker_id = f"{socket.gethostname()}-{os.getpid()}"

    async def heartbeat_loop() -> None:
        payload = {
            "task_queue": task_queue,
            "worker_id": worker_id,
            "version": os.environ.get("WORKER_VERSION", "dev"),
        }
        while True:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client_http:
                    await client_http.post(f"{control_plane_url}/workers/heartbeat", json=payload)
            except Exception:
                pass
            await asyncio.sleep(heartbeat_interval)

    print("Worker iniciado. Esperando tareas...")
    heartbeat_task = asyncio.create_task(heartbeat_loop())
    try:
        await worker.run()
    finally:
        heartbeat_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
