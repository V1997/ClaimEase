from fastapi import FastAPI, HTTPException
import fitz  # PyMuPDF
from minio import Minio
import redis.asyncio as redis
import os
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Document Service")

# MinIO client
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
    secure=False
)

# Redis client
redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = redis.from_url(redis_url)
    
    # Create MinIO bucket if it doesn't exist
    if not minio_client.bucket_exists("documents"):
        minio_client.make_bucket("documents")
    
    logger.info("Document Service started successfully")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "document-service"}

@app.post("/analyze/{patient_name}")
async def analyze_patient_documents(patient_name: str):
    """Analyze documents for a patient"""
    try:        # Find documents in local data directory
        patient_folder = f"/app/data/input/Input Data/{patient_name}"
        
        if not os.path.exists(patient_folder):
            raise HTTPException(status_code=404, detail=f"Patient folder not found: {patient_name}")
        
        # Find PA form and referral package
        pa_form_path = None
        referral_path = None
        
        for file in os.listdir(patient_folder):
            if file.lower().startswith('pa') and file.lower().endswith('.pdf'):
                pa_form_path = os.path.join(patient_folder, file)
            elif 'referral' in file.lower() and file.lower().endswith('.pdf'):
                referral_path = os.path.join(patient_folder, file)
        
        if not pa_form_path or not referral_path:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required documents for {patient_name}. Need PA form and referral package."
            )
        
        # Analyze PA form structure
        form_analysis = analyze_form_structure(pa_form_path)
        
        # Analyze referral package
        referral_analysis = analyze_referral_package(referral_path)
        
        # Store analysis results
        analysis_result = {
            "patient_name": patient_name,
            "pa_form_path": pa_form_path,
            "referral_path": referral_path,
            "form_analysis": form_analysis,
            "referral_analysis": referral_analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        # Store in Redis for other services
        await redis_client.set(
            f"analysis:{patient_name}",
            json.dumps(analysis_result),
            ex=3600  # Expire in 1 hour
        )
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Error analyzing documents for {patient_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def analyze_form_structure(pdf_path: str) -> dict:
    """Analyze PA form structure"""
    try:
        doc = fitz.open(pdf_path)
        form_fields = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            widgets = page.widgets()
            
            for widget in widgets:
                field_info = {
                    "field_name": widget.field_name,
                    "field_type": get_field_type_name(widget.field_type),
                    "page": page_num,
                    "rect": list(widget.rect),
                    "required": bool(widget.field_flags & 2),
                    "max_length": widget.text_maxlen if hasattr(widget, 'text_maxlen') else None
                }
                form_fields.append(field_info)
        
        doc.close()
        
        return {
            "total_pages": doc.page_count,
            "total_fields": len(form_fields),
            "fields": form_fields,
            "field_types": list(set([f["field_type"] for f in form_fields]))
        }
        
    except Exception as e:
        logger.error(f"Error analyzing form structure: {e}")
        return {"error": str(e)}

def analyze_referral_package(pdf_path: str) -> dict:
    """Analyze referral package"""
    try:
        doc = fitz.open(pdf_path)
        
        analysis = {
            "total_pages": doc.page_count,
            "pages_info": []
        }
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            
            # Basic page analysis
            page_info = {
                "page_number": page_num,
                "has_text": bool(page.get_text().strip()),
                "has_images": len(page.get_images()) > 0,
                "text_length": len(page.get_text()),
                "is_scanned": len(page.get_text().strip()) < 100  # Heuristic for scanned pages
            }
            
            analysis["pages_info"].append(page_info)
        
        doc.close()
        
        # Summary statistics
        analysis["summary"] = {
            "scanned_pages": sum(1 for p in analysis["pages_info"] if p["is_scanned"]),
            "text_pages": sum(1 for p in analysis["pages_info"] if not p["is_scanned"]),
            "total_text_length": sum(p["text_length"] for p in analysis["pages_info"]),
            "requires_ocr": any(p["is_scanned"] for p in analysis["pages_info"])
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing referral package: {e}")
        return {"error": str(e)}

def get_field_type_name(field_type: int) -> str:
    """Convert field type number to name"""
    type_map = {
        0: "unknown",
        1: "pushbutton", 
        2: "checkbox",
        3: "radiobutton",
        4: "text",
        5: "choice",
        6: "signature"
    }
    return type_map.get(field_type, "unknown")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)