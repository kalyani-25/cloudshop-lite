# aiops-bot/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system deps (optional, but often useful)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose the port FastAPI/uvicorn listens on
EXPOSE 5100

# Start the FastAPI app
# IMPORTANT: this must point to your file and FastAPI instance: app.py -> app = FastAPI(...)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5100"]
