# Usar una imagen base de Python
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el archivo de requerimientos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El código se montará a través de un volumen en docker-compose.yml

# Exponer el puerto del control plane
EXPOSE 8010

# Comando por defecto (puede ser sobrescrito en docker-compose.yml)
CMD ["uvicorn", "control_plane.service:app", "--host", "0.0.0.0", "--port", "8010"]
