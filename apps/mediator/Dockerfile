FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/mediator /app/apps/mediator
COPY libs /app/libs

ENV PYTHONPATH=/app
CMD ["uvicorn", "apps.mediator.main:app", "--host", "0.0.0.0", "--port", "8080"]
