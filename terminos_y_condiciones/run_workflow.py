import asyncio
from temporalio.client import Client

from .workflows import TerminosYCondicionesWorkflow

async def main():
    # Conexión al servicio de Temporal
    client = await Client.connect("localhost:7233")

    # Iniciar el workflow
    usuario_id = "usuario-123"
    result = await client.execute_workflow(
        TerminosYCondicionesWorkflow.run,
        usuario_id,
        id=f"terminos-workflow-{usuario_id}",
        task_queue="terminos-y-condiciones-task-queue",
    )

    print(f"Workflow completado. Resultado: {result}")

if __name__ == "__main__":
    asyncio.run(main())
