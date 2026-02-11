FROM python:3.11-slim

# Install git (sometimes needed for git-based versioning or tools)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Create a non-root user matching the host user (ubuntu:1000)
# This ensures that files created in mounted volumes are owned by the host user.
RUN groupadd -g 1000 ubuntu && \
    useradd -u 1000 -g ubuntu -m ubuntu

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY scripts/ scripts/

# Set ownership
RUN chown -R ubuntu:ubuntu /app

# Switch to non-root user
USER ubuntu

# Expose port
EXPOSE 8280

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8280"]
