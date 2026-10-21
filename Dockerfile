FROM python:3.11-slim

# Evita que o Python gere arquivos .pyc e forca flush imediato nos logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Instala dependencias do sistema necessarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala pacotes Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o codigo fonte da aplicacao
COPY . .

# Expoe a porta padrao para container (Cloud Run define $PORT dinamicamente)
EXPOSE 8080

# Inicia o FastAPI com uvicorn respeitando a variavel de ambiente $PORT
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
