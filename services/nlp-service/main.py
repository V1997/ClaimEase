from fastapi import FastAPI, HTTPException
import spacy
import redis.asyncio as redis
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NLP Service")

# Load spaCy models
nlp = None
redis_client = None

@app.on_event("startup")
async def startup_event():
    global nlp, redis_client
      # Load spaCy models
    logger.info("Loading spaCy models...")
    try:
        nlp = spacy.load("en_core_web_sm")
        logger.info("spaCy English model loaded successfully")
    except OSError:
        logger.error("spaCy English model not found. Please install it.")
        raise
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = redis.from_url(redis_url)
    
    logger.info("NLP Service started successfully")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "nlp-service"}

@app.post("/analyze/{patient_name}")
async def analyze_patient_text(patient_name: str):
    """Analyze extracted text for medical entities"""
    try:
        # Get OCR results from Redis
        ocr_data = await redis_client.get(f"ocr:{patient_name}")
        if not ocr_data:
            raise HTTPException(status_code=404, detail="OCR results not found")
        
        ocr_results = json.loads(ocr_data)
        
        # Extract all text from OCR results
        all_text = " ".join([result["text"] for result in ocr_results["ocr_results"]])
        
        # Analyze with spaCy
        entities = extract_medical_entities(all_text)
        
        # Store NLP results
        nlp_data = {
            "patient_name": patient_name,
            "entities": entities,
            "analyzed_at": datetime.utcnow().isoformat(),
            "total_entities": sum(len(entity_list) for entity_list in entities.values()),
            "confidence_score": calculate_confidence(entities)
        }
        
        # Store in Redis
        await redis_client.set(
            f"nlp:{patient_name}",
            json.dumps(nlp_data),
            ex=3600
        )
        
        logger.info(f"NLP analysis completed for {patient_name}: {nlp_data['total_entities']} entities found")
        
        return {
            "patient_name": patient_name,
            "status": "completed",
            "entities_summary": {
                "total_entities": nlp_data["total_entities"],
                "confidence_score": nlp_data["confidence_score"],
                "entity_types": list(entities.keys())
            },
            "analysis_time": nlp_data["analyzed_at"]
        }
        
    except Exception as e:
        logger.error(f"Error analyzing text for {patient_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_medical_entities(text: str) -> Dict[str, List[Dict[str, Any]]]:
    """Extract medical entities from text using spaCy"""
    try:
        doc = nlp(text)
        
        entities = {
            'patients': [],
            'medications': [],
            'conditions': [],
            'procedures': [],
            'dates': [],
            'organizations': [],
            'insurance': [],
            'phone_numbers': [],
            'addresses': []
        }
        
        for ent in doc.ents:
            entity_data = {
                'text': ent.text.strip(),
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char,
                'confidence': 0.8  # Default confidence for spaCy entities
            }
            
            # Categorize entities based on labels
            if ent.label_ in ["PERSON"]:
                entities['patients'].append(entity_data)
            elif ent.label_ in ["DATE", "TIME"]:
                entities['dates'].append(entity_data)
            elif ent.label_ in ["ORG"]:
                entities['organizations'].append(entity_data)
            elif ent.label_ in ["GPE"]:  # Geopolitical entities (locations)
                entities['addresses'].append(entity_data)
            else:
                # For medical entities, we'll use keyword matching
                text_lower = ent.text.lower()
                if any(keyword in text_lower for keyword in ['mg', 'ml', 'tablet', 'capsule', 'injection']):
                    entities['medications'].append(entity_data)
                elif any(keyword in text_lower for keyword in ['diagnosis', 'condition', 'disease', 'syndrome']):
                    entities['conditions'].append(entity_data)
                elif any(keyword in text_lower for keyword in ['procedure', 'surgery', 'treatment']):
                    entities['procedures'].append(entity_data)
                elif any(keyword in text_lower for keyword in ['insurance', 'medicare', 'medicaid', 'policy']):
                    entities['insurance'].append(entity_data)
        
        # Extract additional patterns using regex-like matching
        entities = extract_additional_patterns(text, entities)
        
        return entities
        
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        return {}

def extract_additional_patterns(text: str, entities: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Extract additional patterns like phone numbers, IDs, etc."""
    import re
    
    # Phone numbers
    phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    phone_matches = re.finditer(phone_pattern, text)
    for match in phone_matches:
        entities['phone_numbers'].append({
            'text': match.group(),
            'label': 'PHONE',
            'start': match.start(),
            'end': match.end(),
            'confidence': 0.9
        })
    
    # Insurance ID patterns
    insurance_pattern = r'\b[A-Z]{2,3}\d{6,12}\b'
    insurance_matches = re.finditer(insurance_pattern, text)
    for match in insurance_matches:
        entities['insurance'].append({
            'text': match.group(),
            'label': 'INSURANCE_ID',
            'start': match.start(),
            'end': match.end(),
            'confidence': 0.8
        })
    
    return entities

def calculate_confidence(entities: Dict[str, List[Dict[str, Any]]]) -> float:
    """Calculate overall confidence score for extracted entities"""
    total_confidence = 0
    total_entities = 0
    
    for entity_list in entities.values():
        for entity in entity_list:
            total_confidence += entity.get('confidence', 0)
            total_entities += 1
    
    return total_confidence / total_entities if total_entities > 0 else 0.0

@app.get("/results/{patient_name}")
async def get_nlp_results(patient_name: str):
    """Get NLP results for a patient"""
    try:
        nlp_data = await redis_client.get(f"nlp:{patient_name}")
        if not nlp_data:
            raise HTTPException(status_code=404, detail="NLP results not found")
        
        return json.loads(nlp_data)
        
    except Exception as e:
        logger.error(f"Error getting NLP results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
