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

# Set build arguments for version info
ARG BUILD_COMMIT=unknown
ARG BUILD_BRANCH=unknown  
ARG BUILD_TIME=unknown
ARG BUILD_CLEAN=true

# Copy application code (excluding aircraft database - downloaded at runtime)
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser config/*.yaml /app/config/
COPY --chown=appuser:appuser requirements.txt /app/
COPY --chown=appuser:appuser run.py /app/

# Verify files were copied
RUN ls -la /app/ && ls -la /app/src/ && echo "main.py exists:" && ls -la /app/src/main.py

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

# Create startup script that downloads dependencies then starts the app
RUN echo '#!/bin/bash\n\
echo "🚀 Starting Flight Tracker Collector..."\n\
\n\
# Download aircraft database (continue even if it fails)\n\
if [ -f "/app/scripts/download_aircraft_db.sh" ]; then\n\
    echo "📥 Running aircraft database download script..."\n\
    /app/scripts/download_aircraft_db.sh || echo "⚠️  Aircraft database download failed, continuing without enrichment"\n\
fi\n\
\n\
# Download config if needed (continue even if it fails)\n\
if [ -f "/app/scripts/download_config.sh" ]; then\n\
    echo "📥 Running config download script..."\n\
    /app/scripts/download_config.sh || echo "⚠️  Config download failed, using default config"\n\
fi\n\
\n\
# Verify critical files exist\n\
echo "🔍 Verifying application files..."\n\
if [ ! -f "/app/src/main.py" ]; then\n\
    echo "❌ Critical error: main.py not found"\n\
    echo "📂 Contents of /app:"\n\
    ls -la /app/\n\
    echo "📂 Contents of /app/src:"\n\
    ls -la /app/src/ || echo "src directory not found"\n\
    exit 1\n\
fi\n\
\n\
# Start the application\n\
echo "🌐 Starting FastAPI server..."\n\
cd /app\n\
exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1\n\
' > /app/start.sh && chmod +x /app/start.sh

# Default command - run startup script
CMD ["/app/start.sh"]