from temporalio import workflow
from temporalio.exceptions import ApplicationError, ActivityError
from typing import Any, Dict
from datetime import timedelta
from temporalio.common import RetryPolicy
import asyncio

from .shared import Item, EnvioRequest, EstadoCarrito

@workflow.defn
class TerminosYCondicionesWorkflow:
    def __init__(self):
        self.carrito_id: str = ""
        self.usuario_id: str = ""
        self.terminos_aceptados: bool = False
        self.items_carrito: dict[str, Any] = {}  # Almacena los items del carrito
        self.total_carrito: float = 0.0
        self.estado: EstadoCarrito = EstadoCarrito.ABIERTO
        self.envio_resultado: Dict[str, Any] = {}

    @workflow.run
    async def run(self, usuario_id: str) -> dict:
        # Aquí irá la lógica para la aceptación de términos y condiciones
        workflow.logger.info(f"Iniciando workflow de Términos y Condiciones para el usuario {usuario_id}")
        
        self.usuario_id = usuario_id
        # Usar el workflow_id como identificador único de la transacción de compra
        workflow_id = workflow.info().workflow_id
        self.carrito_id = f"carrito-{usuario_id}-{workflow_id}"
        workflow.logger.info(f"Carrito ID generado: {self.carrito_id} (Workflow ID: {workflow_id}) para el usuario {usuario_id}")
        
        # 1. Fase de Compra: Esperar a que el usuario pague o cancele
        # Implementamos un timeout: si no hay actividad de pago en 30 mins, se abandona.
        try:
            await workflow.wait_condition(
                lambda: self.estado in [EstadoCarrito.PAGADO, EstadoCarrito.CANCELADO],
                timeout=timedelta(minutes=30)
            )
        except asyncio.TimeoutError:
            self.estado = EstadoCarrito.ABANDONADO
            return self._estado_final("ABANDONADO_TIMEOUT")

        if self.estado == EstadoCarrito.CANCELADO:
            return self._estado_final("CANCELADO_POR_USUARIO")
        
        # 2. Fase de Envío: Ejecutar la actividad de envío
        workflow.logger.info(f"Compra señalada para {self.usuario_id}. Iniciando actividad de envío.")
        try:
            envio_request = EnvioRequest(
                usuario_id=self.usuario_id,
                items=self.items_carrito
            )
            self.envio_resultado = await workflow.start_activity(
                "despachar_envio_activity",
                envio_request,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=10),
                    maximum_attempts=3,
                ),
            )
            self.estado = EstadoCarrito.ENVIADO
        except ActivityError as e:
            workflow.logger.error(f"La actividad de envío falló después de todos los reintentos: {e}")
            self.envio_resultado = {"status": "FALLIDO", "error": str(e.cause)}
            # El workflow termina aquí con un estado de fallo de envío
            return self._estado_final("ENVIO_FALLIDO")

        # 3. Fase de Entrega: Esperar la confirmación de recepción del producto
        await workflow.wait_condition(lambda: self.estado == EstadoCarrito.ENTREGADO)
    
        # 4. Finalizar
        return self._estado_final("COMPLETADO_ENTREGADO")

    @workflow.signal
    async def agregar_item_carrito(self, item: Item) -> None:
        """
        Signal para agregar un item al carrito del usuario.
        """
        if self.estado != EstadoCarrito.ABIERTO:
            workflow.logger.warning(f"Intento de agregar item en estado {self.estado}")
            return

        workflow.logger.info(f"Agregando item al carrito {self.carrito_id}: {item.nombre} x{item.cantidad}")
        if item.item_id in self.items_carrito:
            # Si el item ya existe, actualiza la cantidad
            self.items_carrito[item.item_id]["cantidad"] += item.cantidad
        else:
            self.items_carrito[item.item_id] = {
                "nombre": item.nombre,
                "precio": item.precio,
                "cantidad": item.cantidad,
                "subtotal": item.precio * item.cantidad
            }
        
        # Recalcula el total
        self._recalcular_total()

    @workflow.update
    async def agregar_item_seguro(self, item: Item) -> dict:
        """
        Update para agregar item con validación síncrona (ej: stock).
        Devuelve el resultado al cliente o lanza una excepción.
        """
        if self.estado != EstadoCarrito.ABIERTO:
            raise ApplicationError(f"No se pueden agregar items. El carrito está en estado: {self.estado}")

        # 1. Validación (Simulación de stock)
        if item.cantidad > 5:
            # Esto devolverá un error al cliente inmediatamente
            raise ApplicationError(f"Stock insuficiente para {item.nombre}. Máximo disponible: 5", type="StockInsuficiente")

        # 2. Lógica de negocio (Modificación del estado)
        # Reutilizamos la lógica del signal o la escribimos aquí
        await self.agregar_item_carrito(item)
        
        # 3. Retorno de valor
        return {
            "mensaje": "Item agregado correctamente",
            "item": item.nombre,
            "nuevo_total": self.total_carrito
        }

    @workflow.signal
    async def remover_item_carrito(self, item_id: str) -> None:
        """
        Signal para remover un item del carrito.
        """
        if self.estado != EstadoCarrito.ABIERTO:
            return

        workflow.logger.info(f"Removiendo item {item_id} del carrito {self.carrito_id}")
        if item_id in self.items_carrito:
            del self.items_carrito[item_id]
            self._recalcular_total()

    @workflow.signal
    async def aceptar_terminos(self) -> None:
        """
        Signal para aceptar los términos y condiciones.
        """
        if self.estado != EstadoCarrito.ABIERTO:
            return
        workflow.logger.info(f"Usuario {self.usuario_id} aceptó los términos y condiciones")
        self.terminos_aceptados = True

    @workflow.signal
    async def completar_compra(self) -> None:
        """
        Signal para marcar la compra como lista para el envío.
        """
        if self.estado == EstadoCarrito.ABIERTO:
            if not self.terminos_aceptados:
                workflow.logger.warning("Intento de completar compra sin aceptar términos.")
                return
            
            workflow.logger.info(f"Completando compra del usuario {self.usuario_id}")
            self.estado = EstadoCarrito.PAGADO

    @workflow.signal
    async def confirmar_recepcion(self) -> None:
        """
        Signal para confirmar que el usuario recibió el producto.
        """
        if self.estado == EstadoCarrito.ENVIADO:
            workflow.logger.info(f"Recepción confirmada para usuario {self.usuario_id}")
            self.estado = EstadoCarrito.ENTREGADO

    @workflow.query
    def obtener_estado(self) -> dict:
        """
        Query para obtener el estado actual del workflow sin finalizarlo.
        """
        return {
            "items_carrito": self.items_carrito,
            "total_carrito": self.total_carrito,
            "estado_actual": self.estado,
            "terminos_aceptados": self.terminos_aceptados
        }

    def _recalcular_total(self) -> None:
        """
        Recalcula el total del carrito.
        """
        self.total_carrito = sum(
            item["subtotal"] for item in self.items_carrito.values()
        )
        workflow.logger.info(f"Total del carrito actualizado: ${self.total_carrito}")

    def _estado_final(self, resultado_workflow: str) -> dict:
        """Construye el diccionario de resultado final del workflow."""
        return {
            "carrito_id": self.carrito_id,
            "usuario_id": self.usuario_id,
            "terminos_aceptados": self.terminos_aceptados,
            "items_carrito": self.items_carrito,
            "total_carrito": self.total_carrito,
            "detalles_envio": self.envio_resultado,
            "estado_carrito": self.estado,
            "resultado_workflow": resultado_workflow,
        }
