from dataclasses import dataclass
from typing import Any, Dict
from enum import Enum

class EstadoCarrito(str, Enum):
    ABIERTO = "ABIERTO"
    PAGADO = "PAGADO"
    ENVIADO = "ENVIADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"
    ABANDONADO = "ABANDONADO"

@dataclass
class Item:
    """Data class for an item in the shopping cart."""
    item_id: str
    nombre: str
    precio: float
    cantidad: int

@dataclass
class EnvioRequest:
    """Data class for a shipping request."""
    usuario_id: str
    items: Dict[str, Any]
    direccion: str = "Dirección por defecto"