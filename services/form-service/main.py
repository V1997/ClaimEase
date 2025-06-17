from fastapi import FastAPI, HTTPException
import redis.asyncio as redis
import json
import os
import logging
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Form Service")

redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_client = redis.from_url(redis_url)
    
    logger.info("Form Service started successfully")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "form-service"}

@app.post("/fill/{patient_name}")
async def fill_patient_form(patient_name: str):
    """Fill PA form with extracted patient data using pdftk-server"""
    try:
        logger.info(f"Starting form filling for patient: {patient_name}")
        
        # Get analysis, NLP, and OCR data from Redis
        analysis_data = await redis_client.get(f"analysis:{patient_name}")
        nlp_data = await redis_client.get(f"nlp:{patient_name}")
        ocr_data = await redis_client.get(f"ocr:{patient_name}")
        
        if not analysis_data or not nlp_data:
            raise HTTPException(status_code=404, detail="Required analysis or NLP data not found")
        
        analysis = json.loads(analysis_data)
        nlp_results = json.loads(nlp_data)
        ocr_results = json.loads(ocr_data) if ocr_data else {}
        
        # Get PA form path
        pa_form_path = analysis.get("pa_form_path")
        if not pa_form_path:
            raise HTTPException(status_code=404, detail="PA form path not found")
        
        logger.info(f"PA form path: {pa_form_path}")
        logger.info(f"NLP entities found: {len(nlp_results.get('entities', {}).get('patients', []))}")
        
        # Map NLP entities to form data using OCR text
        ocr_text = ""
        if ocr_results:
            # Handle different OCR data formats
            if 'extracted_text' in ocr_results:
                ocr_text = ocr_results.get('extracted_text', '')
            elif 'ocr_results' in ocr_results:
                # Extract text from OCR results array
                ocr_results_list = ocr_results.get('ocr_results', [])
                ocr_text = " ".join([result.get('text', '') for result in ocr_results_list])
            elif 'text' in ocr_results:
                ocr_text = ocr_results.get('text', '')
        
        extracted_data = map_nlp_entities_to_form_data(nlp_results["entities"], patient_name, ocr_text)
        logger.info(f"Mapped form data: {extracted_data}")
        
        # Fill PA form using pdftk-server
        filled_form_path = fill_pa_form_with_pdftk(pa_form_path, extracted_data, patient_name)
        
        # Generate completion report
        completion_report = generate_completion_report(extracted_data)
        
        # Store results in Redis
        form_results = {
            "patient_name": patient_name,
            "filled_form_path": filled_form_path,
            "extracted_data": extracted_data,
            "completion_report": completion_report,
            "filled_at": datetime.utcnow().isoformat(),
            "status": "completed"
        }
        
        await redis_client.set(
            f"form:{patient_name}",
            json.dumps(form_results, default=str),
            ex=3600
        )
        
        logger.info(f"Form filling completed for {patient_name}")
        return {
            "status": "success",
            "message": f"Form filled successfully for {patient_name}",
            "filled_form_path": filled_form_path,
            "data": form_results
        }
        
    except Exception as e:
        logger.error(f"Form filling failed for {patient_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Form filling failed: {str(e)}")

def map_nlp_entities_to_form_data(entities: Dict[str, List], patient_name: str, ocr_text: str = "") -> Dict[str, str]:
    """Map NLP entities to form data fields using patient name and OCR text"""
    import re
    try:
        logger.info(f"Mapping NLP entities with patient name: {patient_name}")
        logger.info(f"OCR text length: {len(ocr_text)}")
        
        # Initialize form data with patient name
        form_data = {
            "patient_name": patient_name,
            "first_name": patient_name.split()[0] if patient_name else "",
            "last_name": " ".join(patient_name.split()[1:]) if patient_name and len(patient_name.split()) > 1 else ""
        }
        
        # Extract medication info from OCR text
        if "Skyrizi" in ocr_text:
            form_data["medication"] = "Skyrizi"
            form_data["drug_name"] = "Skyrizi"
            form_data["product"] = "Skyrizi"
            form_data["brand_name"] = "Skyrizi"
            form_data["therapeutic_agent"] = "Skyrizi"
            
        # Check for generic name (risankizumab)
        if "risankizumab" in ocr_text.lower():
            form_data["generic_name"] = "risankizumab"
            form_data["active_ingredient"] = "risankizumab"
            
        # Extract dosage information more comprehensively
        dosage_patterns = re.findall(r'(\d+\s*mg)', ocr_text, re.IGNORECASE)
        if dosage_patterns:
            # Get the most common or first dosage
            primary_dosage = dosage_patterns[0] if dosage_patterns else ""
            form_data["dosage"] = primary_dosage
            form_data["dose"] = primary_dosage
            form_data["strength"] = primary_dosage
            
            # Look specifically for Skyrizi dosages (150mg, 600mg, etc.)
            skyrizi_dosages = [d for d in dosage_patterns if d.strip().lower() in ['150mg', '600mg', '75mg']]
            if skyrizi_dosages:
                form_data["prescribed_dose"] = skyrizi_dosages[0]
                
        # Extract administration method
        if "SQ" in ocr_text or "subcutaneous" in ocr_text.lower():
            form_data["administration"] = "Subcutaneous injection"
            form_data["route"] = "Subcutaneous"
            form_data["delivery_method"] = "Injection"
            
        # Extract scheduling information
        schedule_info = []
        if "Week 0" in ocr_text:
            schedule_info.append("Week 0")
        if re.search(r'week\s*[48]', ocr_text, re.IGNORECASE):
            week_match = re.search(r'week\s*([48])', ocr_text, re.IGNORECASE)
            if week_match:
                schedule_info.append(f"Week {week_match.group(1)}")
        if re.search(r'every\s*(\d+)', ocr_text, re.IGNORECASE):
            every_match = re.search(r'every\s*(\d+)', ocr_text, re.IGNORECASE)
            if every_match:
                schedule_info.append(f"Every {every_match.group(1)} weeks")
                
        if schedule_info:
            form_data["schedule"] = ", ".join(schedule_info)
            form_data["treatment_schedule"] = ", ".join(schedule_info)
            form_data["dosing_schedule"] = ", ".join(schedule_info)
            
        # Extract diagnosis/condition information
        conditions = []
        if "psoriasis" in ocr_text.lower():
            conditions.append("Psoriasis")
        if "arthritis" in ocr_text.lower():
            conditions.append("Arthritis")
        if "IBD" in ocr_text or "inflammatory bowel" in ocr_text.lower():
            conditions.append("IBD")
        if "crohn" in ocr_text.lower():
            conditions.append("Crohn's Disease")
            
        if conditions:
            form_data["diagnosis"] = ", ".join(conditions)
            form_data["condition"] = ", ".join(conditions)
            form_data["indication"] = ", ".join(conditions)
        elif "Prior Authorization" in ocr_text:
            form_data["diagnosis"] = "Prior Authorization Request"
            form_data["condition"] = "Prior Authorization Request"
            
        # Extract provider/prescriber information from OCR
        if re.search(r'(dr\.|doctor|physician|md|do)\s+([a-z]+\s+[a-z]+)', ocr_text, re.IGNORECASE):
            provider_match = re.search(r'(dr\.|doctor|physician|md|do)\s+([a-z]+\s+[a-z]+)', ocr_text, re.IGNORECASE)
            if provider_match:
                form_data["provider"] = provider_match.group(2).title()
                form_data["prescriber"] = provider_match.group(2).title()
        else:
            form_data["provider"] = "Healthcare Provider"
            form_data["prescriber"] = "Healthcare Provider"
            
        # Extract insurance/payer information
        insurance_patterns = re.findall(r'(aetna|anthem|cigna|humana|bcbs|blue cross|united|kaiser)', ocr_text, re.IGNORECASE)
        if insurance_patterns:
            form_data["insurance"] = insurance_patterns[0].title()
            form_data["payer"] = insurance_patterns[0].title()
        else:
            form_data["insurance"] = "Health Plan"
            form_data["payer"] = "Health Plan"
            
        # Add date information
        form_data["date"] = datetime.now().strftime("%m/%d/%Y")
        form_data["request_date"] = datetime.now().strftime("%m/%d/%Y")
        form_data["today_date"] = datetime.now().strftime("%m/%d/%Y")
        
        # Add NDC code if found
        ndc_pattern = re.search(r'(\d{5}-\d{4}-\d{2}|\d{5}-\d{3}-\d{2})', ocr_text)
        if ndc_pattern:
            form_data["ndc_code"] = ndc_pattern.group(1)
            
        logger.info(f"Enhanced mapping: Mapped {len(form_data)} form fields")
        logger.info(f"Key medication data extracted: {form_data.get('medication', 'N/A')}, {form_data.get('dosage', 'N/A')}, {form_data.get('schedule', 'N/A')}")
        
        return form_data
        
    except Exception as e:
        logger.error(f"Error mapping NLP entities: {str(e)}")
        return {
            "patient_name": patient_name,
            "first_name": patient_name.split()[0] if patient_name else "",
            "medication": "Skyrizi",
            "date": datetime.now().strftime("%m/%d/%Y")
        }

def fill_pa_form_with_pdftk(pa_form_path: str, form_data: Dict[str, str], patient_name: str) -> str:
    """Fill PA form using pdftk-server for reliable form filling"""
    try:
        logger.info(f"Filling PA form with pdftk-server for patient: {patient_name}")
        logger.info(f"Form data to fill: {form_data}")
        
        # Get form field names using pdftk dump_data_fields
        field_info_cmd = ['pdftk', pa_form_path, 'dump_data_fields']
        logger.info(f"Getting form fields: {' '.join(field_info_cmd)}")
        
        field_result = subprocess.run(field_info_cmd, capture_output=True, text=True, timeout=30)
        if field_result.returncode != 0:
            logger.error(f"Failed to get form fields: {field_result.stderr}")
            raise Exception(f"Failed to get form fields: {field_result.stderr}")
        
        # Parse field information
        field_names = []
        field_lines = field_result.stdout.split('\n')
        current_field = None
        
        for line in field_lines:
            if line.startswith('FieldName: '):
                current_field = line.replace('FieldName: ', '').strip()
                if current_field:
                    field_names.append(current_field)
        
        logger.info(f"Found {len(field_names)} form fields")
        
        # Create field mapping based on our data
        field_mapping = {}
        
        for field_name in field_names:
            normalized_field = field_name.lower()
            original_field_name = field_name
            
            logger.info(f"Processing field: '{original_field_name}' (normalized: '{normalized_field}')")
            
            # Use enhanced field matching logic
            matched_value = get_field_value_for_pdftk(normalized_field, original_field_name, form_data)
            if matched_value:
                field_mapping[original_field_name] = matched_value
                logger.info(f"✓ Mapped '{original_field_name}' to: {matched_value}")
            else:
                logger.info(f"⚠ Field '{original_field_name}' not matched to any data")
        
        logger.info(f"Final field mapping count: {len(field_mapping)}")
        
        # Create FDF file with form data
        fdf_content = create_fdf_content(field_mapping)
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fdf', delete=False) as fdf_file:
            fdf_file.write(fdf_content)
            fdf_path = fdf_file.name
        
        # Create output directory
        output_dir = f"/app/data/output/{patient_name}"
        os.makedirs(output_dir, exist_ok=True)
        filled_form_path = f"{output_dir}/filled_pa_form.pdf"
        
        # Use pdftk to fill the form
        pdftk_cmd = [
            'pdftk',
            pa_form_path,
            'fill_form',
            fdf_path,
            'output',
            filled_form_path,
            'flatten'  # Flatten to make fields non-editable and ensure visibility
        ]
        
        logger.info(f"Running pdftk command: {' '.join(pdftk_cmd)}")
        result = subprocess.run(pdftk_cmd, capture_output=True, text=True, timeout=30)
        
        # Clean up temporary FDF file
        os.unlink(fdf_path)
        
        if result.returncode != 0:
            logger.error(f"pdftk failed with return code {result.returncode}")
            logger.error(f"pdftk stderr: {result.stderr}")
            raise Exception(f"pdftk failed: {result.stderr}")
        
        logger.info(f"✅ Form filled successfully with pdftk")
        logger.info(f"📄 Saved filled form to: {filled_form_path}")
        
        return filled_form_path
        
    except Exception as e:
        logger.error(f"❌ Error filling PA form with pdftk: {str(e)}")
        raise

def get_field_value_for_pdftk(field_name_lower: str, original_field_name: str, form_data: Dict[str, str]) -> str:
    """Enhanced field matching for pdftk-based form filling"""
    
    # Patient name fields - enhanced matching
    if any(keyword in field_name_lower for keyword in ['t11', 'patient', 'name', 'member', 'beneficiary']):
        return form_data.get('patient_name', '')
    
    # Medication fields - enhanced matching  
    elif any(keyword in field_name_lower for keyword in ['t12', 'medication', 'drug', 'skyrizi', 'product', 'therapy', 'treatment']):
        return form_data.get('medication', '')
    
    # Dosage fields - enhanced matching
    elif any(keyword in field_name_lower for keyword in ['t13', 'dose', 'dosage', 'strength', 'mg', 'amount']):
        return form_data.get('dosage', '')
    
    # Schedule fields - enhanced matching
    elif any(keyword in field_name_lower for keyword in ['t18', 'schedule', 'frequency', 'regimen', 'dosing']):
        return form_data.get('schedule', '')
    
    # Insurance fields - enhanced matching
    elif any(keyword in field_name_lower for keyword in ['insurance', 'payer', 'plan', 'coverage']) and any(id_field in field_name_lower for id_field in ['t.2', 't.6', 't.7', 't.3', 't.8']):
        return form_data.get('insurance', '')
    
    # Diagnosis fields - enhanced matching  
    elif any(keyword in field_name_lower for keyword in ['diagnosis', 'condition', 'indication', 'clinical']) and any(clinical_field in field_name_lower for clinical_field in ['t.16', 't.17', 't.18', 't.42', 't.43', 't.44']):
        if 't.42' in field_name_lower or 't.43' in field_name_lower or 't.44' in field_name_lower:
            # Clinical medication/dosage fields
            if 't.42' in field_name_lower:
                return form_data.get('medication', '')
            elif 't.43' in field_name_lower or 't.44' in field_name_lower:
                return form_data.get('dosage', '')
        return form_data.get('diagnosis', '')
    
    # Provider fields
    elif any(keyword in field_name_lower for keyword in ['provider', 'prescriber', 'physician', 'doctor']):
        return form_data.get('provider', '')
    
    # Date fields
    elif any(keyword in field_name_lower for keyword in ['date', 'birth', 'dob']):
        return form_data.get('date', '')
    
    # NDC code fields
    elif any(keyword in field_name_lower for keyword in ['ndc', 'code']):
        return form_data.get('ndc_code', '')
    
    # Generic name fields
    elif any(keyword in field_name_lower for keyword in ['generic', 'active']):
        return form_data.get('generic_name', '')
    
    # Administration/route fields
    elif any(keyword in field_name_lower for keyword in ['administration', 'route', 'delivery']):
        return form_data.get('administration', '')
    
    return ''

def create_fdf_content(field_mapping: Dict[str, str]) -> str:
    """Create FDF content for pdftk with proper escaping"""
    fdf_header = """%FDF-1.2
1 0 obj
<<
/FDF
<<
/Fields [
"""
    
    fdf_fields = []
    for field_name, field_value in field_mapping.items():
        # Escape special characters in field names and values
        escaped_field_name = field_name.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        escaped_value = str(field_value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        fdf_fields.append(f"<< /T ({escaped_field_name}) /V ({escaped_value}) >>")
    
    fdf_footer = """]
>>
>>
endobj
trailer

<<
/Root 1 0 R
>>
%%EOF"""
    
    return fdf_header + '\n'.join(fdf_fields) + '\n' + fdf_footer

def generate_completion_report(extracted_data: Dict[str, str]) -> Dict[str, Any]:
    """Generate a completion report"""
    required_fields = ["patient_name", "medication", "diagnosis", "provider", "insurance"]
    
    filled_fields = []
    missing_fields = []
    
    for field in required_fields:
        if field in extracted_data and extracted_data[field]:
            filled_fields.append(field)
        else:
            missing_fields.append(field)
    
    completion_rate = len(filled_fields) / len(required_fields) * 100
    
    return {
        "completion_rate": completion_rate,
        "filled_fields": filled_fields,
        "missing_fields": missing_fields,
        "total_extracted": len(extracted_data),
        "summary": f"Completed {len(filled_fields)}/{len(required_fields)} required fields ({completion_rate:.1f}%)"
    }

@app.get("/results/{patient_name}")
async def get_form_results(patient_name: str):
    """Get form filling results for a patient"""
    try:
        form_data = await redis_client.get(f"form:{patient_name}")
        if not form_data:
            raise HTTPException(status_code=404, detail="Form results not found")
        
        return json.loads(form_data)
        
    except Exception as e:
        logger.error(f"Error getting form results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
