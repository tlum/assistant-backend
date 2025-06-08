# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 1) Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 2) Copy all your application code in one shot
COPY . .

# 3) Expose & run
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

