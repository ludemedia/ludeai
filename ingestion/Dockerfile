FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run Job passes args via CLOUD_RUN_TASK_* env vars,
# but we also support direct CLI args for local testing.
ENTRYPOINT ["python", "main.py"]
