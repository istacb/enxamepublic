FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
ENV PYTHONPATH=/app

EXPOSE 7700
CMD ["uvicorn", "juiz.app:app", "--host", "0.0.0.0", "--port", "7700"]
