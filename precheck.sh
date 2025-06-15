#!/bin/bash

echo "🔍 Pre-flight Check for ClaimEase..."

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found"
    exit 1
else
    echo "✅ docker-compose.yml found"
fi

# Check required directories
required_dirs=("services/api-gateway" "services/document-service" "services/ocr-service" "services/nlp-service" "services/form-service" "services/worker" "data/input" "data/output" "monitoring")

for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir exists"
    else
        echo "❌ $dir missing"
        exit 1
    fi
done

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
else
    echo "✅ Docker is running"
fi

# Check if patient data exists
patient_folders=("data/input/Input Data/Adbulla" "data/input/Input Data/Akshay" "data/input/Input Data/Amy")

for folder in "${patient_folders[@]}"; do
    if [ -d "$folder" ]; then
        echo "✅ Patient data found: $folder"
    else
        echo "❌ Patient data missing: $folder"
    fi
done

echo ""
echo "🎯 All checks passed! Ready to start the application."
echo "Run: ./start.sh"
