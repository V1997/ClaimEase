from fastapi import FastAPI, HTTPException
import easyocr
import redis.asyncio as redis
import fitz  # PyMuPDF
import json
import os
import logging
from datetime import datetime
from PIL import Image
import io
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OCR Service")

# Initialize EasyOCR
ocr_engine = None
redis_client = None

@app.on_event("startup")
async def startup_event():
    global ocr_engine, redis_client
    
    # Initialize OCR engine
    logger.info("Initializing EasyOCR...")
    ocr_engine = easyocr.Reader(['en'], gpu=False)  # Use CPU for better compatibility
    logger.info("EasyOCR initialized successfully")
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = redis.from_url(redis_url)
    
    logger.info("OCR Service started successfully")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ocr-service"}

@app.post("/extract/{patient_name}")
async def extract_text_from_referral(patient_name: str):
    """Extract text from referral package using OCR"""
    try:
        # Get document analysis from Redis
        analysis_data = await redis_client.get(f"analysis:{patient_name}")
        if not analysis_data:
            raise HTTPException(status_code=404, detail="Document analysis not found")
        
        analysis = json.loads(analysis_data)
        referral_path = analysis["referral_path"]
        
        if not os.path.exists(referral_path):
            raise HTTPException(status_code=404, detail="Referral package not found")
        
        # Extract text using OCR
        ocr_results = extract_text_with_ocr(referral_path)
        
        # Store OCR results
        ocr_data = {
            "patient_name": patient_name,
            "referral_path": referral_path,
            "ocr_results": ocr_results,
            "extracted_at": datetime.utcnow().isoformat(),
            "total_text_length": sum(len(result["text"]) for result in ocr_results),
            "total_confidence": sum(result["confidence"] for result in ocr_results) / len(ocr_results) if ocr_results else 0
        }
        
        # Store in Redis
        await redis_client.set(
            f"ocr:{patient_name}",
            json.dumps(ocr_data),
            ex=3600
        )
        
        logger.info(f"OCR completed for {patient_name}: {len(ocr_results)} text blocks extracted")
        
        return {
            "patient_name": patient_name,
            "status": "completed",
            "results_summary": {
                "total_blocks": len(ocr_results),
                "total_text_length": ocr_data["total_text_length"],
                "average_confidence": ocr_data["total_confidence"]
            },
            "extraction_time": ocr_data["extracted_at"]
        }
        
    except Exception as e:
        logger.error(f"Error extracting text for {patient_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_text_with_ocr(pdf_path: str) -> list:
    """Extract text from PDF using EasyOCR"""
    try:
        doc = fitz.open(pdf_path)
        all_results = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            
            # Convert page to image
            mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Convert to numpy array for EasyOCR
            img_array = np.array(img)
            
            # Run OCR with EasyOCR
            results = ocr_engine.readtext(img_array)
              # Process results
            for result in results:
                bbox = result[0]  # Bounding box coordinates
                text = result[1]  # Extracted text
                confidence = result[2]  # Confidence score
                
                # Filter low confidence results
                if confidence > 0.5:
                    # Convert numpy types to Python native types for JSON serialization
                    bbox_converted = [[float(coord[0]), float(coord[1])] for coord in bbox]
                    all_results.append({
                        "text": text.strip(),
                        "confidence": float(confidence),
                        "bbox": bbox_converted,
                        "page": int(page_num)
                    })
            
            # Clean up
            del pix, img, img_array
        
        doc.close()
        
        # Sort by page and position
        all_results.sort(key=lambda x: (x["page"], x["bbox"][0][1]))  # Sort by page, then by y-coordinate
        
        return all_results
        
    except Exception as e:
        logger.error(f"Error in OCR extraction: {e}")
        raise

@app.get("/results/{patient_name}")
async def get_ocr_results(patient_name: str):
    """Get OCR results for a patient"""
    try:
        ocr_data = await redis_client.get(f"ocr:{patient_name}")
        if not ocr_data:
            raise HTTPException(status_code=404, detail="OCR results not found")
        
        return json.loads(ocr_data)
        
    except Exception as e:
        logger.error(f"Error getting OCR results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)