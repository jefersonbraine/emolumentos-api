# API de emolumentos — imagem enxuta, no mesmo padrão de container do Inito

FROM python:3.12-slim

WORKDIR /app

# Instala as dependências primeiro (aproveita o cache do Docker entre builds).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia só o código da aplicação.
COPY app ./app/

EXPOSE 8000

# 0.0.0.0 para aceitar conexões de fora do container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]