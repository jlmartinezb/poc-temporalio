import os
import sys

# Agregar el directorio padre al path para permitir importar 'terminos_y_condiciones'
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio.client import Client, WorkflowUpdateFailedError
from temporalio.exceptions import ApplicationError

# Importa el workflow que quieres iniciar
from terminos_y_condiciones.workflows import TerminosYCondicionesWorkflow
from terminos_y_condiciones.shared import Item

# Modelos para los datos de entrada del API
class IniciarWorkflowRequest(BaseModel):
    usuario_id: str

class AgregarItemRequest(BaseModel):
    usuario_id: str
    item_id: str
    nombre: str
    precio: float
    cantidad: int = 1

class RemoverItemRequest(BaseModel):
    usuario_id: str
    item_id: str

class AceptarTerminosRequest(BaseModel):
    usuario_id: str

class CompletarCompraRequest(BaseModel):
    usuario_id: str

class EnvioRequest(BaseModel):
    usuario_id: str
    items: dict
    direccion: str = "Dirección por defecto"

class ConfirmarRecepcionRequest(BaseModel):
    usuario_id: str

# Estado en memoria para simular fallos en la API de envío
failure_state = {}

app = FastAPI()

async def get_workflow_handle(usuario_id: str):
    """
    Obtiene el handle del workflow para un usuario específico.
    """
    temporal_server = os.environ.get("TEMPORAL_SERVER", "localhost:7233")
    client = await Client.connect(temporal_server)
    
    workflow_id = f"terminos-workflow-{usuario_id}"
    handle = client.get_workflow_handle(workflow_id)
    return handle

@app.post("/iniciar-workflow/terminos")
async def iniciar_workflow_terminos(request: IniciarWorkflowRequest):
    """
    Endpoint para iniciar el workflow de Términos y Condiciones.
    """
    try:
        # Conexión al servicio de Temporal
        temporal_server = os.environ.get("TEMPORAL_SERVER", "localhost:7233")
        client = await Client.connect(temporal_server)

        # Iniciar el workflow
        handle = await client.start_workflow(
            TerminosYCondicionesWorkflow.run,
            request.usuario_id,
            id=f"terminos-workflow-{request.usuario_id}",
            task_queue="terminos-y-condiciones-task-queue",
        )

        return {
            "status": "workflow_iniciado",
            "workflow_id": handle.id,
            "usuario_id": request.usuario_id
        }
    except Exception as e:
        return {"status": "error", "detalle": str(e)}

@app.post("/carrito/agregar-item")
async def agregar_item_carrito(request: AgregarItemRequest):
    """
    Endpoint para agregar un item al carrito de un usuario.
    """
    try:
        handle = await get_workflow_handle(request.usuario_id)
        
        item_worflow = Item(
            item_id=request.item_id,
            nombre=request.nombre,
            precio=request.precio,
            cantidad=request.cantidad
        )
        
        # Usamos execute_update para esperar la validación y el resultado
        resultado = await handle.execute_update(
            TerminosYCondicionesWorkflow.agregar_item_seguro, 
            item_worflow
        )
        
        return {
            "status": "item_agregado",
            "usuario_id": request.usuario_id,
            "item_id": request.item_id,
            "cantidad": request.cantidad,
            "detalles": resultado
        }
    except WorkflowUpdateFailedError as e:
        # Si el workflow lanza ApplicationError (ej: stock insuficiente), lo capturamos aquí
        if isinstance(e.cause, ApplicationError):
            raise HTTPException(status_code=422, detail=str(e.cause.message))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/carrito/remover-item")
async def remover_item_carrito(request: RemoverItemRequest):
    """
    Endpoint para remover un item del carrito.
    """
    try:
        handle = await get_workflow_handle(request.usuario_id)
        
        await handle.signal(
            TerminosYCondicionesWorkflow.remover_item_carrito,
            request.item_id
        )
        
        return {
            "status": "item_removido",
            "usuario_id": request.usuario_id,
            "item_id": request.item_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/terminos/aceptar")
async def aceptar_terminos(request: AceptarTerminosRequest):
    """
    Endpoint para aceptar los términos y condiciones.
    """
    try:
        handle = await get_workflow_handle(request.usuario_id)
        
        await handle.signal(TerminosYCondicionesWorkflow.aceptar_terminos)
        
        return {
            "status": "terminos_aceptados",
            "usuario_id": request.usuario_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/envio/despachar")
async def despachar_envio(request: EnvioRequest):
    """
    Endpoint que simula ser un microservicio externo de envíos.
    - Falla con 503 (reintentable) en el primer intento.
    - Falla con 400 (no reintentable) si la cantidad de un item es > 10.
    - Funciona en el segundo intento (si no hay error 400).
    """
    # Chequeo de lógica de negocio (error no reintentable)
    for item_id, item_details in request.items.items():
        if item_details.get("cantidad", 0) > 10:
            print(f"Simulando fallo 400 (no reintentable) para {request.usuario_id} por cantidad > 10")
            raise HTTPException(status_code=400, detail=f"Pedido inválido: Cantidad para {item_id} excede el límite de 10.")

    # Simulación de fallo transitorio (reintentable)
    user_attempts = failure_state.get(request.usuario_id, 0)
    failure_state[request.usuario_id] = user_attempts + 1

    if user_attempts == 0:
        print(f"Simulando fallo 503 (reintentable) para {request.usuario_id} (intento 1)")
        raise HTTPException(status_code=503, detail="Servicio de envío no disponible temporalmente")

    print(f"Procesando envío exitosamente para {request.usuario_id} (intento {user_attempts + 1})")
    if request.usuario_id in failure_state:
        del failure_state[request.usuario_id]

    return {"status": "envio_programado", "tracking_id": f"TRK-{request.usuario_id}-999", "items_despachados": len(request.items)}

@app.post("/compra/completar")
async def completar_compra(request: CompletarCompraRequest):
    """
    Endpoint para completar la compra.
    Esto ahora solo envía una señal al workflow, que orquestará el envío.
    """
    try:
        handle = await get_workflow_handle(request.usuario_id)
        await handle.signal(TerminosYCondicionesWorkflow.completar_compra)
        return {
            "status": "proceso_de_compra_iniciado",
            "usuario_id": request.usuario_id,
            "mensaje": "El workflow ha recibido la señal y comenzará el proceso de envío."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/envio/confirmar-recepcion")
async def confirmar_recepcion(request: ConfirmarRecepcionRequest):
    """
    Endpoint para confirmar la recepción del producto y finalizar el ciclo de vida.
    """
    try:
        handle = await get_workflow_handle(request.usuario_id)
        await handle.signal(TerminosYCondicionesWorkflow.confirmar_recepcion)
        
        # Ahora sí esperamos el resultado final del workflow
        resultado_final = await handle.result()
        
        return {
            "status": "ciclo_vida_finalizado",
            "mensaje": "El cliente ha recibido el producto y el workflow ha terminado.",
            "resultado_final": resultado_final
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/carrito/{usuario_id}")
async def obtener_carrito(usuario_id: str):
    """
    Endpoint para obtener el estado actual del carrito de un usuario.
    """
    try:
        handle = await get_workflow_handle(usuario_id)
        # Describe el workflow para obtener su estado actual
        descripcion = await handle.describe()
        
        # Query para obtener el estado detallado del negocio (items, estado enum, etc)
        estado_negocio = await handle.query(TerminosYCondicionesWorkflow.obtener_estado)

        return {
            "status": "success",
            "usuario_id": usuario_id,
            "workflow_id": descripcion.id,
            "workflow_status": "running" if not descripcion.close_time else "completed",
            "carrito": estado_negocio
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def read_root():
    return {"mensaje": "API Gateway para iniciar workflows de Temporal"}