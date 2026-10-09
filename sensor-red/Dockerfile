FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /sensor
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY capturador.py .
# Corre como root dentro del contenedor, pero docker-compose le quita todas las
# capacidades excepto CAP_NET_RAW, la mínima para leer paquetes de eth2.
CMD ["python", "capturador.py"]
