# Usar una imagen base de Python
FROM python:3.10-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el archivo de requerimientos e instalar dependencias
# Esto se hace en un paso separado para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# El código se montará a través de un volumen en docker-compose.yml

# Comando para ejecutar el worker
CMD ["python", "-m", "terminos_y_condiciones.run_worker"]
