# apps/dispatcher/Dockerfile
FROM python:3.11-slim

# 1.  Install deps
WORKDIR /app
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2.  Copy service code + shared libs
COPY ../../apps/dispatcher /app/apps/dispatcher
COPY ../../libs /app/libs

# 3.  Expose the FastAPI app
ENV PYTHONPATH=/app
CMD ["uvicorn", "apps.dispatcher.main:app", "--host", "0.0.0.0", "--port", "8080"]
