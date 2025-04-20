#!/bin/bash
set -e

# Ensure data directories exist with proper permissions
DIRS=("logs" "data" "logs/modules")

for dir in "${DIRS[@]}"; do
    # Create directory if it doesn't exist
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
    fi
    
    # Ensure proper permissions
    chmod -R 777 "$dir"
done

# Check for required configuration files
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Using sample if available."
    if [ -f ".env.sample" ]; then
        cp .env.sample .env
        echo "Copied .env.sample to .env. Please update with your actual credentials."
    else
        echo "Error: No .env or .env.sample file found. Configuration will be incomplete."
    fi
fi

echo "TGAI-Bennet container initialized. Starting application..."

# Execute the provided command (CMD from Dockerfile)
exec "$@"
