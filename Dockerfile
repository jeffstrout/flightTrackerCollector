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

# Set working directory and fix ownership
WORKDIR /app
RUN chown appuser:appuser /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Set build arguments for version info
ARG BUILD_COMMIT=unknown
ARG BUILD_BRANCH=unknown  
ARG BUILD_TIME=unknown
ARG BUILD_CLEAN=true

# Copy requirements first (for better caching)
COPY --chown=appuser:appuser requirements.txt /app/

# Copy application code
COPY --chown=appuser:appuser src /app/src
COPY --chown=appuser:appuser config /app/config
COPY --chown=appuser:appuser run.py /app/

# Verify critical files exist after copy
RUN test -f /app/requirements.txt && echo "✓ requirements.txt found" || exit 1
RUN test -f /app/run.py && echo "✓ run.py found" || exit 1
RUN test -d /app/src && echo "✓ src directory found" || exit 1
RUN test -f /app/src/main.py && echo "✓ main.py found" || exit 1
RUN test -d /app/config && echo "✓ config directory found" || exit 1

# Copy and make download script executable
COPY --chown=appuser:appuser scripts/download_aircraft_db.sh /app/scripts/
COPY --chown=appuser:appuser scripts/download_config.sh /app/scripts/
RUN chmod +x /app/scripts/download_aircraft_db.sh /app/scripts/download_config.sh

# Create logs directory with proper permissions
RUN mkdir -p logs && chown -R appuser:appuser logs

# Create config directory for runtime downloads
RUN mkdir -p /app/config && chown -R appuser:appuser /app/config

# Make sure scripts are executable
RUN chmod +x /home/appuser/.local/bin/*

# Switch to non-root user
USER appuser

# Add local bin to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Set build environment variables
ENV BUILD_COMMIT=$BUILD_COMMIT
ENV BUILD_BRANCH=$BUILD_BRANCH
ENV BUILD_TIME=$BUILD_TIME
ENV BUILD_CLEAN=$BUILD_CLEAN

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Create startup script as root first
RUN cat > /app/start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Flight Tracker Collector..."

# Download aircraft database (continue even if it fails)
if [ -f "/app/scripts/download_aircraft_db.sh" ]; then
    echo "📥 Running aircraft database download script..."
    /app/scripts/download_aircraft_db.sh || echo "⚠️  Aircraft database download failed, continuing without enrichment"
fi

# Download config if needed (continue even if it fails)
if [ -f "/app/scripts/download_config.sh" ]; then
    echo "📥 Running config download script..."
    /app/scripts/download_config.sh || echo "⚠️  Config download failed, using default config"
fi

# Verify critical files exist
echo "🔍 Verifying application files..."
if [ ! -f "/app/src/main.py" ]; then
    echo "❌ Critical error: main.py not found"
    echo "📂 Contents of /app:"
    ls -la /app/
    echo "📂 Contents of /app/src:"
    ls -la /app/src/ || echo "src directory not found"
    exit 1
fi

# Start the application
echo "🌐 Starting FastAPI server..."
cd /app
exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1
EOF

# Make startup script executable and fix ownership
RUN chmod +x /app/start.sh && chown appuser:appuser /app/start.sh

# Default command - run startup script
CMD ["/app/start.sh"]