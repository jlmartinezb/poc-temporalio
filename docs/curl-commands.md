# Comandos CURL para la API de Temporal Workflow

Esta guía contiene todos los comandos `curl` para probar los endpoints de la API Gateway del workflow de Términos y Condiciones con carrito de compra.

## Requisitos previos

Asegúrate de que el servicio esté ejecutándose:
```bash
docker-compose up --build
```

## Endpoints disponibles

### 1. Iniciar Workflow para un Usuario

**Descripción:** Inicia un nuevo workflow para un usuario, generando un carrito de compra único asociado a ese usuario.

**Endpoint:** `POST /iniciar-workflow/terminos`

**Body esperado:** 
- `usuario_id` (string): ID único del usuario

```bash
curl -X POST "http://localhost:8000/iniciar-workflow/terminos" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "mi-usuario-123"}'
```

**Respuesta esperada:**
```json
{
  "status": "workflow_iniciado",
  "workflow_id": "terminos-workflow-mi-usuario-123",
  "usuario_id": "mi-usuario-123"
}
```


### 2. Agregar Item al Carrito

**Descripción:** Agrega un producto al carrito de compra del usuario. Si el producto ya existe, aumenta la cantidad.

**Endpoint:** `POST /carrito/agregar-item`

**Body esperado:**
- `usuario_id` (string): ID del usuario propietario del carrito
- `item_id` (string): ID único del producto
- `nombre` (string): Nombre del producto
- `precio` (float): Precio unitario del producto
- `cantidad` (integer, opcional): Cantidad a agregar (default: 1)

```bash
curl -X POST "http://localhost:8000/carrito/agregar-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-1",
    "nombre": "Laptop",
    "precio": 999.99,
    "cantidad": 1
  }'
```

**Respuesta esperada:**
```json
{
  "status": "item_agregado",
  "usuario_id": "mi-usuario-123",
  "item_id": "producto-1",
  "cantidad": 1
}
```

---

### 3. Agregar Segundo Item al Carrito

**Descripción:** Agrega otro producto al carrito del usuario.

**Endpoint:** `POST /carrito/agregar-item`

```bash
curl -X POST "http://localhost:8000/carrito/agregar-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-2",
    "nombre": "Mouse inalámbrico",
    "precio": 29.99,
    "cantidad": 2
  }'
```

**Respuesta esperada:**
```json
{
  "status": "item_agregado",
  "usuario_id": "mi-usuario-123",
  "item_id": "producto-2",
  "cantidad": 2
}
```

---

### 4. Agregar Tercer Item al Carrito

**Descripción:** Agrega un tercer producto al carrito del usuario.

**Endpoint:** `POST /carrito/agregar-item`

```bash
curl -X POST "http://localhost:8000/carrito/agregar-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-3",
    "nombre": "Teclado mecánico",
    "precio": 149.99,
    "cantidad": 1
  }'
```

**Respuesta esperada:**
```json
{
  "status": "item_agregado",
  "usuario_id": "mi-usuario-123",
  "item_id": "producto-3",
  "cantidad": 1
}
```

---

### 5. Obtener Estado del Carrito

**Descripción:** Recupera el estado actual del carrito y el workflow del usuario.

**Endpoint:** `GET /carrito/{usuario_id}`

**Parámetros URL:**
- `usuario_id` (string): ID del usuario

```bash
curl -X GET "http://localhost:8000/carrito/mi-usuario-123"
```

**Respuesta esperada:**
```json
{
  "status": "success",
  "usuario_id": "mi-usuario-123",
  "workflow_id": "terminos-workflow-mi-usuario-123",
  "workflow_status": "running"
}
```

---

### 6. Remover Item del Carrito

**Descripción:** Elimina un producto del carrito de compra del usuario.

**Endpoint:** `POST /carrito/remover-item`

**Body esperado:**
- `usuario_id` (string): ID del usuario
- `item_id` (string): ID del producto a remover

```bash
curl -X POST "http://localhost:8000/carrito/remover-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-2"
  }'
```

**Respuesta esperada:**
```json
{
  "status": "item_removido",
  "usuario_id": "mi-usuario-123",
  "item_id": "producto-2"
}
```

---

### 7. Aceptar Términos y Condiciones

**Descripción:** Marca que el usuario ha aceptado los términos y condiciones.

**Endpoint:** `POST /terminos/aceptar`

**Body esperado:**
- `usuario_id` (string): ID del usuario

```bash
curl -X POST "http://localhost:8000/terminos/aceptar" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "mi-usuario-123"}'
```

**Respuesta esperada:**
```json
{
  "status": "terminos_aceptados",
  "usuario_id": "mi-usuario-123"
}
```

---

### 8. Completar Compra
### 8. Realizar Pago y Completar Compra

**Descripción:** Marca la compra como pagada. Esto dispara el proceso de envío dentro del workflow. El workflow continuará ejecutándose hasta que se confirme la recepción.
**Descripción:** Procesa el pago y marca la compra como completada. **Esta acción requiere que los términos y condiciones hayan sido aceptados previamente.** Si la condición no se cumple, la API devolverá un error (ver sección "Casos de Fallo"). Una vez completada, se dispara el proceso de envío dentro del workflow. El workflow continuará ejecutándose hasta que se confirme la recepción.

**Endpoint:** `POST /compra/completar`

**Body esperado:**
- `usuario_id` (string): ID del usuario

```bash
curl -X POST "http://localhost:8000/compra/completar" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "mi-usuario-123"}'
```

**Respuesta esperada:**
```json
{
  "status": "compra_completada",
  "usuario_id": "mi-usuario-123",
  "resultado": {
    "carrito_id": "carrito-mi-usuario-123-...",
    "usuario_id": "mi-usuario-123",
    "terminos_aceptados": true,
    "items_carrito": {
      "producto-1": {
        "nombre": "Laptop",
        "precio": 999.99,
        "cantidad": 1,
        "subtotal": 999.99
      },
      "producto-3": {
        "nombre": "Teclado mecánico",
        "precio": 149.99,
        "cantidad": 1,
        "subtotal": 149.99
      }
    },
    "total_carrito": 1149.98
  }
}
```

---

## Flujo de Prueba Recomendado

Ejecuta los comandos en este orden para una prueba completa del flujo:
Ejecuta los comandos en este orden para una prueba completa del flujo exitoso:

```bash
# Paso 1: Iniciar el workflow
# Iniciar el workflow para un nuevo usuario
curl -X POST "http://localhost:8000/iniciar-workflow/terminos" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "mi-usuario-123"}'

# Paso 2: Agregar múltiples items al carrito
# Agregar múltiples items al carrito
curl -X POST "http://localhost:8000/carrito/agregar-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-1",
    "nombre": "Laptop",
    "precio": 999.99,
    "cantidad": 1
  }'

curl -X POST "http://localhost:8000/carrito/agregar-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-2",
    "nombre": "Mouse inalámbrico",
    "precio": 29.99,
    "cantidad": 2
  }'

curl -X POST "http://localhost:8000/carrito/agregar-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-3",
    "nombre": "Teclado mecánico",
    "precio": 149.99,
    "cantidad": 1
  }'

# Paso 3: Ver el estado del carrito
# Ver el estado del carrito
curl -X GET "http://localhost:8000/carrito/mi-usuario-123"

# Paso 4: (Opcional) Remover un item
# (Opcional) Remover un item
curl -X POST "http://localhost:8000/carrito/remover-item" \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_id": "mi-usuario-123",
    "item_id": "producto-2"
  }'

# Paso 5: Aceptar términos y condiciones
# Aceptar términos y condiciones
curl -X POST "http://localhost:8000/terminos/aceptar" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "mi-usuario-123"}'

# Paso 6: Completar la compra
# Realizar el pago y completar la compra
curl -X POST "http://localhost:8000/compra/completar" \
  -H "Content-Type: application/json" \
  -d '{"usuario_id": "mi-usuario-123"}'
```

---

## Notas Importantes

- El `usuario_id` es la clave para relacionar el carrito con el usuario
- El workflow mantiene el estado del carrito en memoria durante toda la sesión
- El workflow ahora utiliza `Updates` para validaciones síncronas (stock) y persiste hasta la confirmación de entrega.
