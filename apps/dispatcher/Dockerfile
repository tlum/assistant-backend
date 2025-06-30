FROM python:3.11-slim

WORKDIR /app
# 1. dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. service code + shared libs
COPY apps/dispatcher /app/apps/dispatcher
COPY libs /app/libs

ENV PYTHONPATH=/app
CMD ["uvicorn", "apps.dispatcher.main:app", "--host", "0.0.0.0", "--port", "8080"]
