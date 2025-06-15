#!/bin/bash

echo "🧪 Testing ClaimEase High-Scale Application..."

API_BASE="http://localhost:8000/api/v1"

# Test 1: Health Check
echo "1. Testing health check..."
response=$(curl -s -o /dev/null -w "%{http_code}" $API_BASE/../health)
if [ $response -eq 200 ]; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed (HTTP $response)"
fi

# Test 2: Process Patient A
echo "2. Processing Patient A..."
job_response=$(curl -s -X POST $API_BASE/patients/Patient_A/process)
job_id=$(echo $job_response | python3 -c "import sys, json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)

if [ ! -z "$job_id" ]; then
    echo "✅ Job created: $job_id"
    
    # Monitor job progress
    echo "3. Monitoring job progress..."
    for i in {1..20}; do
        status_response=$(curl -s $API_BASE/jobs/$job_id/status)
        status=$(echo $status_response | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
        progress=$(echo $status_response | python3 -c "import sys, json; print(json.load(sys.stdin)['progress'])" 2>/dev/null)
        
        echo "   Status: $status, Progress: $progress%"
        
        if [ "$status" = "completed" ]; then
            echo "✅ Processing completed successfully!"
            break
        elif [ "$status" = "failed" ]; then
            echo "❌ Processing failed"
            break
        fi
        
        sleep 10
    done
else
    echo "❌ Failed to create job"
fi

echo ""
echo "📊 View detailed logs:"
echo "docker-compose logs -f api-gateway"
echo "docker-compose logs -f celery-worker"