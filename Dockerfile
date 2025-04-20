FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies, Rust, and Cargo
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    python3-dev \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Rust and Cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies with the correct version of OpenAI
RUN pip install --no-cache-dir -r requirements.txt

# Ensure we have the right version - failsafe
RUN pip install --no-cache-dir "openai==0.28.1"

# Copy project files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p logs data && \
    chmod -R 777 logs data

# Set up an entrypoint script to ensure volumes are properly initialized
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Command to run the application
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]
