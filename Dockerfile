# ---- Base Python image ----
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ /app/backend
COPY frontend/ /app/frontend

# Expose Flask port
EXPOSE 5000

# Use Gunicorn in production
CMD ["python",  "/app/backend/app.py"]