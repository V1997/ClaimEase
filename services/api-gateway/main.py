from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import asyncio
import uuid
from typing import List, Optional
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ClaimEase API Gateway", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://claimease_user:claimease_pass@postgres:5432/claimease")
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Redis setup
redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = redis.from_url(redis_url, decode_responses=True, encoding='utf-8')
    logger.info("API Gateway started successfully")

# Service discovery
SERVICES = {
    "document": "http://document-service:8000",
    "ocr": "http://ocr-service:8000",
    "nlp": "http://nlp-service:8000",
    "form": "http://form-service:8000"
}

class ServiceDiscovery:
    def __init__(self):
        self.services = SERVICES
        self.current_index = {}
    
    async def get_service_url(self, service_name: str) -> str:
        # In production, this would use service registry
        return self.services.get(service_name)

service_discovery = ServiceDiscovery()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.post("/api/v1/patients/{patient_name}/process")
async def process_patient(patient_name: str):
    """Start processing for a patient"""
    try:
        # Create processing job
        job_id = str(uuid.uuid4())
        
        # Store job in Redis
        await redis_client.hset(
            f"job:{job_id}",
            mapping={
                "patient_name": patient_name,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "progress": "0"
            }
        )
        
        # Submit to processing queue
        await redis_client.lpush("processing_queue", job_id)
        
        logger.info(f"Created processing job {job_id} for patient {patient_name}")
        
        return {
            "job_id": job_id,
            "patient_name": patient_name,
            "status": "submitted",
            "message": "Processing started"
        }
        
    except Exception as e:
        logger.error(f"Error creating processing job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    """Get processing job status"""
    try:
        job_data = await redis_client.hgetall(f"job:{job_id}")
        
        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {
            "job_id": job_id,
            "status": job_data.get("status", "unknown"),
            "progress": int(job_data.get("progress", 0)),
            "patient_name": job_data.get("patient_name"),
            "created_at": job_data.get("created_at"),
            "error": job_data.get("error") if job_data.get("error") else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/jobs")
async def list_jobs():
    """List all processing jobs"""
    try:
        # Get all job keys from Redis
        job_keys = await redis_client.keys("job:*")
        jobs = []
        
        for key in job_keys:
            job_data = await redis_client.hgetall(key)
            job_id = key.split(":")[1]
            
            jobs.append({
                "job_id": job_id,
                "patient_name": job_data.get("patient_name"),
                "status": job_data.get("status"),
                "progress": int(job_data.get("progress", 0)),
                "created_at": job_data.get("created_at")
            })
        
        return {"jobs": jobs}
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/redis")
async def debug_redis():
    """Debug Redis connection"""
    try:
        # Test the global redis_client
        await redis_client.ping()
        
        # Test reading a job
        job_data = await redis_client.hgetall("job:ab55d3ab-9f7c-401e-9aa4-e6ccd8860b57")
        
        return {
            "redis_client_type": str(type(redis_client)),
            "ping": "success",
            "job_data": job_data,
            "job_data_type": str(type(job_data))
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)