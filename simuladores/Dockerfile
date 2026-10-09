FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /sim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py ./
RUN useradd --system --uid 10002 sim
USER sim
# El servicio define cuál dispositivo ejecutar: python ups.py | ambiente.py | puerta.py
CMD ["python", "ups.py"]
