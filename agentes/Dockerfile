FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
COPY agentes/requirements.txt /tmp/agentes-requirements.txt
RUN pip install --no-cache-dir -r /tmp/agentes-requirements.txt

COPY . /app
ENV PYTHONPATH=/app

CMD ["python", "scripts/dynamic_agent.py"]
