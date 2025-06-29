# apps/echo_agent/Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY ../../requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../../apps/echo_agent /app/apps/echo_agent
COPY ../../libs /app/libs

ENV PYTHONPATH=/app
CMD ["uvicorn", "apps.echo_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
