FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY bibliotecario/requirements.txt /app/bibliotecario/requirements.txt
RUN pip install --no-cache-dir -r /app/bibliotecario/requirements.txt

COPY . /app

ENV PYTHONPATH=/app

EXPOSE 7710

CMD ["uvicorn", "bibliotecario.app:app", "--host", "0.0.0.0", "--port", "7710"]
