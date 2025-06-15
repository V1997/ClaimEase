from celery import Celery
import httpx
import asyncio
import json
import redis as sync_redis
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery app
celery_app = Celery(
    'worker',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0'
)

# Redis client for job updates
redis_client = sync_redis.from_url('redis://redis:6379')

# Service URLs
SERVICES = {
    "document": "http://document-service:8000",
    "ocr": "http://ocr-service:8000", 
    "nlp": "http://nlp-service:8000",
    "form": "http://form-service:8000"
}

@celery_app.task(bind=True)
def process_patient_pipeline(self, job_id: str, patient_name: str):
    """Process complete patient pipeline"""
    try:
        # Update job status
        update_job_status(job_id, "processing", 10)
        
        # Step 1: Document Analysis
        logger.info(f"Starting document analysis for {patient_name}")
        doc_response = call_service("document", f"/analyze/{patient_name}")
        if not doc_response:
            raise Exception("Document analysis failed")
        
        update_job_status(job_id, "processing", 25)
        
        # Step 2: OCR Processing
        logger.info(f"Starting OCR processing for {patient_name}")
        ocr_response = call_service("ocr", f"/extract/{patient_name}")
        if not ocr_response:
            raise Exception("OCR processing failed")
        
        update_job_status(job_id, "processing", 50)
        
        # Step 3: NLP Processing
        logger.info(f"Starting NLP processing for {patient_name}")
        nlp_response = call_service("nlp", f"/analyze/{patient_name}")
        if not nlp_response:
            raise Exception("NLP processing failed")
        
        update_job_status(job_id, "processing", 75)
        
        # Step 4: Form Filling
        logger.info(f"Starting form filling for {patient_name}")
        form_response = call_service("form", f"/fill/{patient_name}")
        if not form_response:
            raise Exception("Form filling failed")
        
        # Mark as completed
        update_job_status(job_id, "completed", 100)
        
        logger.info(f"Pipeline completed successfully for {patient_name}")
        
        return {
            "job_id": job_id,
            "patient_name": patient_name,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Pipeline failed for {patient_name}: {error_msg}")
        
        # Update job with error
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": "failed",
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        
        raise

def call_service(service_name: str, endpoint: str) -> dict:
    """Call a microservice endpoint"""
    try:
        url = SERVICES[service_name] + endpoint
        
        with httpx.Client(timeout=300.0) as client:  # 5 minute timeout
            response = client.post(url)
            response.raise_for_status()
            return response.json()
            
    except Exception as e:
        logger.error(f"Error calling {service_name}{endpoint}: {e}")
        return None

def update_job_status(job_id: str, status: str, progress: int):
    """Update job status in Redis"""
    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": status,
            "progress": str(progress),
            "updated_at": datetime.utcnow().isoformat()
        }
    )

# Queue consumer
@celery_app.task
def consume_processing_queue():
    """Consume jobs from processing queue"""
    while True:
        try:
            # Pop job from queue (blocking)
            result = redis_client.brpop("processing_queue", timeout=10)
            
            if result:
                queue_name, job_id = result
                job_id = job_id.decode()
                
                # Get job details
                job_data = redis_client.hgetall(f"job:{job_id}")
                if job_data:
                    patient_name = job_data[b'patient_name'].decode()
                    
                    # Start processing
                    process_patient_pipeline.delay(job_id, patient_name)
                    
        except Exception as e:
            logger.error(f"Error consuming queue: {e}")
            time.sleep(5)

# Auto-start queue consumer
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup the queue consumer when Celery starts"""
    consume_processing_queue.delay()

if __name__ == "__main__":
    # Start queue consumer  
    consume_processing_queue.delay()