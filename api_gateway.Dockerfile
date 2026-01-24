# Usar una imagen base de Python
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el archivo de requerimientos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El código se montará a través de un volumen en docker-compose.yml

# Exponer el puerto que usará la API
EXPOSE 8000

# Comando para ejecutar la API con Uvicorn
CMD ["uvicorn", "api_gateway.service:app", "--host", "0.0.0.0", "--port", "8000"]