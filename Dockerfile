# Multi-stage build for smaller final image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies including AWS CLI
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf awscliv2.zip aws \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Copy and make download script executable
COPY --chown=appuser:appuser scripts/download_aircraft_db.sh /app/scripts/
COPY --chown=appuser:appuser scripts/download_config.sh /app/scripts/
RUN chmod +x /app/scripts/download_aircraft_db.sh /app/scripts/download_config.sh

# Create logs directory with proper permissions
RUN mkdir -p logs && chown -R appuser:appuser logs

# Verify aircraft database file exists and is readable
RUN if [ -f config/aircraftDatabase.csv ]; then \
        echo "Aircraft database found: $(wc -l < config/aircraftDatabase.csv) lines"; \
        ls -la config/aircraftDatabase.csv; \
    else \
        echo "WARNING: Aircraft database not found at config/aircraftDatabase.csv"; \
        ls -la config/; \
    fi

# Make sure scripts are executable
RUN chmod +x /home/appuser/.local/bin/*

# Switch to non-root user
USER appuser

# Add local bin to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

# Default command - can be overridden in docker-compose
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]