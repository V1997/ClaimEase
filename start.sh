#!/bin/bash

echo "🚀 Starting ClaimEase High-Scale Application..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

# Create output directories
mkdir -p data/output data/models

# Pull base images first (to show progress)
echo "📦 Pulling required Docker images..."
docker-compose pull postgres redis minio nginx prometheus grafana

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check service health
echo "🏥 Checking service health..."
services=("postgres" "redis" "minio" "api-gateway")

for service in "${services[@]}"; do
    if docker-compose ps $service | grep -q "Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service failed to start"
        docker-compose logs $service
    fi
done

echo ""
echo "🎉 ClaimEase High-Scale Application Started!"
echo ""
echo "📊 Access Points:"
echo "• API Gateway: http://localhost:8000"
echo "• MinIO Console: http://localhost:9001 (admin/minioadmin123)"
echo "• Celery Flower: http://localhost:5555"
echo "• Prometheus: http://localhost:9090"
echo "• Grafana: http://localhost:3001 (admin/admin)"
echo "• Load Balancer: http://localhost"
echo ""
echo "🔧 Management Commands:"
echo "• View logs: docker-compose logs -f [service-name]"
echo "• Scale service: docker-compose up --scale ocr-service=3 -d"
echo "• Stop all: docker-compose down"
echo ""
echo "🧪 Test the system:"
echo "curl -X POST http://localhost:8000/api/v1/patients/Patient_A/process"
echo ""