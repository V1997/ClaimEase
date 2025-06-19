# ClaimEase Technical Architecture Documentation

**Version:** 1.0  
**Date:** June 18, 2025  
**Status:** Technical Specification

---

## 📋 Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Detailed Processing Flow](#detailed-processing-flow)
4. [Microservices Architecture](#microservices-architecture)
5. [Data Models & Storage](#data-models--storage)
6. [API Specifications](#api-specifications)
7. [Security & Compliance](#security--compliance)
8. [Performance & Scalability](#performance--scalability)
9. [Monitoring & Observability](#monitoring--observability)
10. [Error Handling & Recovery](#error-handling--recovery)
11. [Deployment Architecture](#deployment-architecture)
12. [Development Guidelines](#development-guidelines)

---

## Executive Summary

ClaimEase is an intelligent healthcare automation platform designed to streamline Prior Authorization (PA) form processing through advanced AI/ML technologies. The system employs a microservices architecture with event-driven processing to automatically extract information from referral packages and populate PA forms with high accuracy and efficiency.

### Key Technical Highlights
- **Architecture**: Event-driven microservices with Redis-based communication
- **AI/ML Stack**: EasyOCR for text extraction, spaCy for medical entity recognition
- **Processing Capacity**: 95%+ OCR accuracy, 45-second average processing time
- **Scalability**: Horizontal scaling with Docker containers and load balancing
- **Data Security**: HIPAA-compliant data handling with encryption at rest and in transit

---

## System Architecture Overview

### High-Level Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        Client[Web Client/API Consumer]
        Monitor[Monitoring Dashboard]
    end
    
    subgraph "API Gateway Layer"
        Gateway[API Gateway<br/>Port 8000]
        Auth[Authentication<br/>& Authorization]
        RateLimit[Rate Limiting]
    end
    
    subgraph "Processing Layer"
        Worker[Worker Service<br/>Celery Queue]
        Queue[Redis Queue<br/>Background Jobs]
    end
    
    subgraph "Microservices Layer"
        DocService[Document Service<br/>Port 8001]
        OCRService[OCR Service<br/>Port 8002]
        NLPService[NLP Service<br/>Port 8003]
        FormService[Form Service<br/>Port 8004]
    end
    
    subgraph "Data Layer"
        PostgreSQL[(PostgreSQL<br/>Primary DB)]
        Redis[(Redis<br/>Cache & Queue)]
        MinIO[(MinIO<br/>Object Storage)]
        FileSystem[File System<br/>Document Storage]
    end
    
    subgraph "Infrastructure Layer"
        Docker[Docker Containers]
        Nginx[Nginx Load Balancer]
        Prometheus[Prometheus Metrics]
        Grafana[Grafana Dashboards]
    end
    
    Client --> Gateway
    Monitor --> Grafana
    Gateway --> Auth
    Gateway --> RateLimit
    Gateway --> Worker
    Worker --> Queue
    Worker --> DocService
    Worker --> OCRService
    Worker --> NLPService
    Worker --> FormService
    
    DocService --> FileSystem
    OCRService --> Redis
    NLPService --> Redis
    FormService --> FileSystem
    
    Worker --> PostgreSQL
    Worker --> Redis
    Worker --> MinIO
    
    Prometheus --> Gateway
    Prometheus --> Worker
    Grafana --> Prometheus
    
    Docker --> Nginx
```

### Architecture Principles

1. **Microservices Pattern**: Loosely coupled services with single responsibilities
2. **Event-Driven Architecture**: Asynchronous processing with message queues
3. **Separation of Concerns**: Clear boundaries between data, business logic, and presentation
4. **Scalability First**: Horizontal scaling capabilities built-in
5. **Fault Tolerance**: Circuit breakers and graceful degradation
6. **Security by Design**: Authentication, authorization, and data encryption

---

## Detailed Processing Flow

### Phase 1: Request Initiation & Job Creation

```mermaid
sequenceDiagram
    participant Client
    participant Gateway as API Gateway<br/>(Port 8000)
    participant Auth as Authentication
    participant Redis as Redis Cache
    participant Queue as Processing Queue
    participant Worker as Worker Service
    
    Client->>Gateway: POST /api/v1/patients/{name}/process
    Gateway->>Auth: Validate API Key/Token
    Auth-->>Gateway: Authentication Success
    Gateway->>Gateway: Generate UUID job_id
    Gateway->>Redis: Store job metadata
    Note over Redis: job:{job_id} = {<br/>patient_name,<br/>status: "pending",<br/>created_at,<br/>progress: 0<br/>}
    Gateway->>Queue: Enqueue job_id
    Gateway->>Client: Return job_id & status
    
    Queue->>Worker: Job available
    Worker->>Redis: Update status to "processing"
```

**Request Payload:**
```json
{
  "patient_name": "Amy",
  "priority": "normal",
  "callback_url": "https://client.example.com/webhook",
  "metadata": {
    "source": "web_portal",
    "user_id": "user123"
  }
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_name": "Amy",
  "status": "submitted",
  "estimated_completion": "2025-06-18T14:32:00Z",
  "tracking_url": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/status"
}
```

### Phase 2: Document Discovery & Analysis

```mermaid
flowchart TB
    A[Worker Service] --> B[Document Service<br/>Port 8001]
    B --> C{Patient Folder<br/>Exists?}
    C -->|Yes| D[Scan Directory]
    C -->|No| E[Return 404 Error]
    
    D --> F{PA Form<br/>Found?}
    F -->|Yes| G[Analyze PA Form]
    F -->|No| H[Log Missing PA Form]
    
    D --> I{Referral Package<br/>Found?}
    I -->|Yes| J[Analyze Referral Package]
    I -->|No| K[Log Missing Referral]
    
    G --> L[Extract Form Fields]
    L --> M[Identify Field Types]
    J --> N[Analyze PDF Structure]
    N --> O[Detect Scanned Pages]
    
    M --> P[Store Analysis Results]
    O --> P
    P --> Q[Update Job Progress: 25%]
    Q --> R[Trigger OCR Phase]
```

**Document Analysis Process:**

1. **File Discovery Algorithm:**
   ```python
   def discover_patient_documents(patient_name):
       base_path = f"/app/data/input/Input Data/{patient_name}"
       documents = {
           "pa_form": None,
           "referral_package": None
       }
       
       for filename in os.listdir(base_path):
           if filename.lower().startswith('pa'):
               documents["pa_form"] = os.path.join(base_path, filename)
           elif filename.lower().startswith('referral'):
               documents["referral_package"] = os.path.join(base_path, filename)
       
       return documents
   ```

2. **Form Field Extraction:**
   - Uses PyMuPDF to identify AcroForm widgets
   - Extracts field names, types, and validation rules
   - Maps field positions and dependencies

3. **Referral Package Analysis:**
   - Determines if pages are scanned images or searchable text
   - Calculates page count and image quality metrics
   - Identifies potential OCR challenges

**Analysis Output Structure:**
```json
{
  "patient_name": "Amy",
  "analysis_timestamp": "2025-06-18T14:30:25Z",
  "pa_form_analysis": {
    "path": "/app/data/input/Input Data/Amy/PA.pdf",
    "total_pages": 3,
    "form_fields": [
      {
        "name": "patient_first_name",
        "type": "text",
        "required": true,
        "max_length": 50,
        "page": 1,
        "coordinates": [100, 200, 300, 220]
      }
    ],
    "field_count": 27,
    "has_widgets": true
  },
  "referral_analysis": {
    "path": "/app/data/input/Input Data/Amy/referral_package.pdf",
    "total_pages": 9,
    "file_size_mb": 12.5,
    "pages_info": [
      {
        "page_number": 0,
        "is_scanned": true,
        "has_text": false,
        "image_quality": "high",
        "estimated_ocr_difficulty": "medium"
      }
    ],
    "ocr_required": true
  }
}
```

### Phase 3: OCR Text Extraction

```mermaid
flowchart LR
    A[OCR Service<br/>Port 8002] --> B[Load Referral PDF]
    B --> C[Page Processing Loop]
    C --> D[Convert to Image<br/>300 DPI]
    D --> E[EasyOCR Processing]
    E --> F[Text Extraction]
    F --> G[Confidence Scoring]
    G --> H{More Pages?}
    H -->|Yes| C
    H -->|No| I[Aggregate Results]
    I --> J[Quality Assessment]
    J --> K[Store OCR Data]
    K --> L[Update Progress: 50%]
```

**OCR Processing Algorithm:**

1. **Image Preprocessing:**
   ```python
   def preprocess_page_for_ocr(page):
       # Convert PDF page to high-resolution image
       mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
       pix = page.get_pixmap(matrix=mat)
       img_data = pix.tobytes("png")
       
       # Load with PIL for preprocessing
       img = Image.open(io.BytesIO(img_data))
       
       # Enhance contrast and brightness if needed
       if is_low_contrast(img):
           img = enhance_contrast(img)
       
       return np.array(img)
   ```

2. **OCR Execution:**
   ```python
   def extract_text_with_easyocr(image_array):
       results = ocr_engine.readtext(
           image_array,
           detail=1,  # Include bounding boxes
           paragraph=True,  # Group text into paragraphs
           width_ths=0.7,  # Adjust text grouping
           height_ths=0.7
       )
       return results
   ```

3. **Text Processing:**
   - Removes noise and artifacts
   - Normalizes whitespace and line breaks
   - Groups related text blocks
   - Calculates confidence scores

**OCR Output Structure:**
```json
{
  "patient_name": "Amy",
  "extraction_timestamp": "2025-06-18T14:30:45Z",
  "referral_path": "/app/data/input/Input Data/Amy/referral_package.pdf",
  "processing_stats": {
    "total_pages": 9,
    "processing_time_seconds": 23.4,
    "average_confidence": 0.923,
    "total_text_length": 5430
  },
  "ocr_results": [
    {
      "page": 0,
      "text_blocks": [
        {
          "text": "Patient: Amy Johnson",
          "confidence": 0.94,
          "bbox": [120, 45, 280, 65],
          "block_type": "header"
        },
        {
          "text": "Date of Birth: 03/15/1985",
          "confidence": 0.91,
          "bbox": [120, 70, 260, 90],
          "block_type": "demographic"
        }
      ]
    }
  ],
  "extracted_text": "Patient: Amy Johnson\nDate of Birth: 03/15/1985\n...",
  "quality_metrics": {
    "low_confidence_blocks": 2,
    "unreadable_sections": 0,
    "overall_quality": "high"
  }
}
```

### Phase 4: NLP Entity Recognition & Extraction

```mermaid
flowchart TB
    A[NLP Service<br/>Port 8003] --> B[Load OCR Text]
    B --> C[Text Preprocessing]
    C --> D[spaCy NLP Pipeline]
    D --> E[Medical Entity Recognition]
    E --> F[Pattern Matching]
    F --> G[Data Validation]
    G --> H[Entity Structuring]
    H --> I[Confidence Scoring]
    I --> J[Store NLP Results]
    J --> K[Update Progress: 75%]
    
    subgraph "Entity Types"
        L[Patient Demographics]
        M[Insurance Information]
        N[Medical Information]
        O[Provider Information]
        P[Dates & Numbers]
    end
    
    E --> L
    E --> M
    E --> N
    E --> O
    E --> P
```

**NLP Processing Pipeline:**

1. **Text Preprocessing:**
   ```python
   def preprocess_medical_text(text):
       # Remove OCR artifacts
       text = remove_ocr_noise(text)
       
       # Normalize medical abbreviations
       text = expand_medical_abbreviations(text)
       
       # Fix common OCR errors in medical text
       text = fix_medical_ocr_errors(text)
       
       return text
   ```

2. **Medical Entity Recognition:**
   ```python
   # Custom medical entity patterns
   medical_patterns = [
       {
           "label": "PATIENT_NAME",
           "pattern": [
               {"LOWER": {"IN": ["patient", "name"]}},
               {"IS_PUNCT": True, "OP": "?"},
               {"IS_ALPHA": True, "OP": "+"}
           ]
       },
       {
           "label": "DATE_OF_BIRTH",
           "pattern": [
               {"LOWER": {"IN": ["dob", "date", "birth"]}},
               {"IS_PUNCT": True, "OP": "*"},
               {"SHAPE": "dd/dd/dddd"}
           ]
       }
   ]
   ```

3. **Medical Information Extraction:**
   - **Diagnosis Recognition**: ICD-10 code mapping
   - **Medication Extraction**: Drug name identification
   - **Date Processing**: Appointment and treatment dates
   - **Insurance Details**: Member ID, group numbers, plan types

**NLP Output Structure:**
```json
{
  "patient_name": "Amy",
  "extraction_timestamp": "2025-06-18T14:31:00Z",
  "processing_stats": {
    "total_entities": 23,
    "processing_time_seconds": 8.2,
    "confidence_threshold": 0.85
  },
  "entities": {
    "patients": [
      {
        "name": "Amy Johnson",
        "first_name": "Amy",
        "last_name": "Johnson",
        "dob": "1985-03-15",
        "gender": "Female",
        "age": 40,
        "confidence": 0.94
      }
    ],
    "insurance_info": {
      "member_id": "INS123456789",
      "group_number": "GRP001",
      "plan_name": "Blue Cross Blue Shield",
      "effective_date": "2025-01-01",
      "confidence": 0.89
    },
    "medical_info": {
      "primary_diagnosis": "Rheumatoid Arthritis",
      "icd10_code": "M79.3",
      "medications": [
        {
          "name": "Methotrexate",
          "dosage": "15mg",
          "frequency": "weekly",
          "confidence": 0.92
        },
        {
          "name": "Humira",
          "dosage": "40mg",
          "frequency": "bi-weekly",
          "confidence": 0.88
        }
      ],
      "allergies": ["Penicillin"],
      "confidence": 0.91
    },
    "provider_info": {
      "physician_name": "Dr. Sarah Wilson",
      "npi": "1234567890",
      "practice_name": "Rheumatology Associates",
      "phone": "(555) 123-4567",
      "confidence": 0.87
    },
    "dates": [
      {
        "date": "2025-01-15",
        "type": "appointment",
        "context": "Initial consultation"
      },
      {
        "date": "2025-02-20",
        "type": "follow_up",
        "context": "Treatment response evaluation"
      }
    ]
  },
  "extraction_quality": {
    "completeness_score": 0.89,
    "accuracy_estimate": 0.91,
    "missing_critical_info": ["prior_authorization_number"]
  }
}
```

### Phase 5: Form Field Mapping & Filling

```mermaid
flowchart TB
    A[Form Service<br/>Port 8004] --> B[Load Analysis & NLP Data]
    B --> C[Intelligent Field Mapping]
    C --> D[Data Validation & Formatting]
    D --> E{Form Technology?}
    E -->|AcroForm| F[PyMuPDF Processing]
    E -->|Legacy| G[PDFtk Fallback]
    
    F --> H[Widget-Based Filling]
    G --> I[Field Coordinate Filling]
    H --> J[Form Generation]
    I --> J
    J --> K[Missing Fields Analysis]
    K --> L[Generate Report]
    L --> M[Store Results]
    M --> N[Update Progress: 90%]
    
    subgraph "Field Mapping Logic"
        O[Semantic Matching]
        P[Pattern Recognition]
        Q[Fuzzy String Matching]
        R[Medical Terminology]
    end
    
    C --> O
    C --> P
    C --> Q
    C --> R
```

**Form Filling Process:**

1. **Intelligent Field Mapping:**
   ```python
   def map_entities_to_form_fields(form_fields, extracted_entities):
       mappings = {}
       
       for field in form_fields:
           field_name = field['name'].lower()
           
           # Direct name matching
           if 'first_name' in field_name:
               mappings[field['name']] = extracted_entities['patients'][0]['first_name']
           
           # Semantic matching
           elif semantic_similarity(field_name, 'patient_name') > 0.8:
               mappings[field['name']] = extracted_entities['patients'][0]['name']
           
           # Pattern-based matching
           elif 'member' in field_name and 'id' in field_name:
               mappings[field['name']] = extracted_entities['insurance_info']['member_id']
       
       return mappings
   ```

2. **Data Validation & Formatting:**
   ```python
   def validate_and_format_field_data(field_type, data):
       if field_type == 'date':
           return format_date_for_form(data)
       elif field_type == 'phone':
           return format_phone_number(data)
       elif field_type == 'text':
           return validate_text_length(data)
       
       return data
   ```

3. **Form Generation:**
   - **PyMuPDF Method**: Direct widget manipulation for modern forms
   - **PDFtk Method**: Coordinate-based filling for legacy forms
   - **Hybrid Approach**: Combines both methods for maximum compatibility

**Form Filling Output:**
```json
{
  "patient_name": "Amy",
  "form_filling_timestamp": "2025-06-18T14:31:15Z",
  "processing_stats": {
    "total_fields": 27,
    "filled_fields": 18,
    "empty_fields": 9,
    "filling_accuracy": 0.89,
    "processing_time_seconds": 12.3
  },
  "field_mappings": {
    "patient_first_name": {
      "value": "Amy",
      "source": "nlp_entities.patients[0].first_name",
      "confidence": 0.94,
      "status": "filled"
    },
    "patient_last_name": {
      "value": "Johnson",
      "source": "nlp_entities.patients[0].last_name",
      "confidence": 0.94,
      "status": "filled"
    },
    "member_id": {
      "value": "INS123456789",
      "source": "nlp_entities.insurance_info.member_id",
      "confidence": 0.89,
      "status": "filled"
    }
  },
  "missing_fields": [
    {
      "field_name": "prior_authorization_number",
      "reason": "Not found in referral documents",
      "required": true,
      "suggested_action": "Contact insurance provider"
    },
    {
      "field_name": "prescriber_npi",
      "reason": "Extracted but validation failed",
      "required": true,
      "suggested_action": "Verify NPI number format"
    }
  ],
  "output_files": {
    "filled_form": "/app/data/output/Amy/filled_pa_form.pdf",
    "missing_fields_report": "/app/data/output/Amy/missing_fields_report.txt"
  }
}
```

### Phase 6: Data Consolidation & Completion

```mermaid
flowchart LR
    A[Worker Service] --> B[Consolidate All Data]
    B --> C[Generate Complete Extraction]
    C --> D[Create Final Reports]
    D --> E[Save to File System]
    E --> F[Update Job Status: 100%]
    F --> G[Cleanup Temporary Data]
    G --> H[Send Completion Notification]
```

**Final Consolidation Process:**

1. **Data Aggregation:**
   - Combines analysis, OCR, NLP, and form filling results
   - Creates comprehensive processing summary
   - Generates audit trail for compliance

2. **Quality Assessment:**
   - Calculates overall processing accuracy
   - Identifies potential data quality issues
   - Provides recommendations for improvement

**Final Output Structure:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_name": "Amy",
  "processing_summary": {
    "status": "completed",
    "started_at": "2025-06-18T14:30:25Z",
    "completed_at": "2025-06-18T14:31:30Z",
    "total_processing_time": "65.2s",
    "overall_accuracy": 0.89
  },
  "stage_results": {
    "document_analysis": {
      "status": "success",
      "processing_time": "2.1s",
      "documents_found": 2
    },
    "ocr_extraction": {
      "status": "success",
      "processing_time": "23.4s",
      "confidence": 0.923,
      "text_length": 5430
    },
    "nlp_processing": {
      "status": "success",
      "processing_time": "8.2s",
      "entities_extracted": 23,
      "confidence": 0.89
    },
    "form_filling": {
      "status": "completed_with_issues",
      "processing_time": "12.3s",
      "fields_filled": 18,
      "fields_missing": 9
    }
  },
  "extracted_data": {
    "patient_demographics": {...},
    "insurance_information": {...},
    "medical_information": {...},
    "provider_information": {...}
  },
  "deliverables": {
    "filled_pa_form": "/app/data/output/Amy/filled_pa_form.pdf",
    "missing_fields_report": "/app/data/output/Amy/missing_fields_report.txt",
    "processing_log": "/app/data/output/Amy/processing_log.json",
    "extraction_data": "/app/extracted_data/Amy_complete_extraction.json"
  },
  "quality_metrics": {
    "data_completeness": 0.85,
    "extraction_accuracy": 0.89,
    "form_filling_success": 0.67,
    "overall_confidence": 0.80
  }
}
```

---

## Microservices Architecture

### Service Specifications

#### API Gateway Service
- **Port**: 8000
- **Responsibilities**: Request routing, authentication, rate limiting
- **Technology Stack**: FastAPI, Redis, PostgreSQL
- **Scaling**: Horizontal with load balancer

#### Document Service
- **Port**: 8001
- **Responsibilities**: PDF analysis, file discovery, metadata extraction
- **Technology Stack**: FastAPI, PyMuPDF, MinIO
- **Scaling**: Stateless horizontal scaling

#### OCR Service
- **Port**: 8002
- **Responsibilities**: Text extraction from scanned documents
- **Technology Stack**: FastAPI, EasyOCR, Pillow, NumPy
- **Scaling**: CPU-intensive, requires resource allocation

#### NLP Service
- **Port**: 8003
- **Responsibilities**: Medical entity recognition and extraction
- **Technology Stack**: FastAPI, spaCy, custom medical models
- **Scaling**: Memory-intensive, model caching required

#### Form Service
- **Port**: 8004
- **Responsibilities**: PA form filling and generation
- **Technology Stack**: FastAPI, PyMuPDF, PDFtk
- **Scaling**: I/O intensive, file system dependent

#### Worker Service
- **Responsibilities**: Background job orchestration
- **Technology Stack**: Celery, Redis, Python
- **Scaling**: Horizontal worker scaling

### Service Communication Patterns

1. **Synchronous Communication**:
   - REST API calls between services
   - Timeout handling (300 seconds)
   - Circuit breaker pattern implementation

2. **Asynchronous Communication**:
   - Redis-based job queues
   - Event-driven status updates
   - Pub/sub for real-time notifications

3. **Data Sharing**:
   - Redis cache for temporary data
   - Shared file system for document storage
   - PostgreSQL for persistent data

---

## Data Models & Storage

### Redis Data Model

```
Redis Key Patterns:
├── job:{job_id}                    # Job metadata and status
├── analysis:{patient_name}         # Document analysis results
├── ocr:{patient_name}             # OCR extraction results
├── nlp:{patient_name}             # NLP entity results
├── complete_extraction:{patient_name} # Final consolidated data
├── processing_queue               # Job queue for workers
├── rate_limit:{client_id}         # Rate limiting counters
└── session:{session_id}           # User session data
```

**Job Status Schema:**
```json
{
  "job_id": "uuid",
  "patient_name": "string",
  "status": "pending|processing|completed|failed",
  "progress": "0-100",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "error": "string|null",
  "metadata": {
    "priority": "low|normal|high",
    "callback_url": "string|null",
    "estimated_completion": "ISO8601"
  }
}
```

### PostgreSQL Schema

```sql
-- Jobs table for persistent job tracking
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB,
    processing_stats JSONB
);

-- Processing metrics for analytics
CREATE TABLE processing_metrics (
    id SERIAL PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    service_name VARCHAR(100) NOT NULL,
    processing_time_seconds DECIMAL(10,3),
    accuracy_score DECIMAL(5,4),
    confidence_score DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Audit log for compliance
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    action VARCHAR(100) NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_id VARCHAR(255)
);
```

### File System Structure

```
/app/data/
├── input/
│   └── Input Data/
│       └── {patient_name}/
│           ├── PA.pdf
│           └── referral_package.pdf
├── output/
│   └── {patient_name}/
│       ├── filled_pa_form.pdf
│       ├── missing_fields_report.txt
│       └── processing_log.json
├── temp/
│   └── {job_id}/
│       ├── processed_images/
│       └── intermediate_data/
└── extracted_data/
    ├── {patient_name}_analysis.json
    ├── {patient_name}_ocr.json
    ├── {patient_name}_nlp.json
    └── {patient_name}_complete_extraction.json
```

---

## API Specifications

### Core Endpoints

#### Process Patient
```http
POST /api/v1/patients/{patient_name}/process
Content-Type: application/json
Authorization: Bearer {token}

{
  "priority": "normal",
  "callback_url": "https://example.com/webhook",
  "metadata": {
    "source": "web_portal",
    "user_id": "user123"
  }
}
```

#### Job Status
```http
GET /api/v1/jobs/{job_id}/status
Authorization: Bearer {token}
```

#### Upload Documents
```http
POST /api/v1/patients/{patient_name}/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

Form Data:
- pa_form: file
- referral_package: file
```

#### Download Results
```http
GET /api/v1/patients/{patient_name}/results
Authorization: Bearer {token}
```

### Response Formats

**Success Response:**
```json
{
  "status": "success",
  "data": {...},
  "metadata": {
    "timestamp": "2025-06-18T14:30:25Z",
    "request_id": "req_123456"
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": {
    "code": "PATIENT_NOT_FOUND",
    "message": "Patient documents not found",
    "details": {
      "patient_name": "Amy",
      "expected_path": "/app/data/input/Input Data/Amy/"
    }
  },
  "metadata": {
    "timestamp": "2025-06-18T14:30:25Z",
    "request_id": "req_123456"
  }
}
```

---

## Security & Compliance

### Authentication & Authorization
- **API Key Authentication**: For service-to-service communication
- **JWT Tokens**: For user authentication with expiration
- **Role-Based Access Control**: Different permissions for different users
- **Rate Limiting**: API call limits per client

### Data Security
- **Encryption at Rest**: AES-256 encryption for stored documents
- **Encryption in Transit**: TLS 1.3 for all API communications
- **Data Masking**: PII redaction in logs and error messages
- **Secure File Handling**: Temporary file cleanup and access controls

### HIPAA Compliance
- **Audit Logging**: Complete audit trail of all data access
- **Data Minimization**: Only necessary data is processed and stored
- **Access Controls**: Strict access controls and authentication
- **Data Retention**: Configurable data retention policies

### Security Headers
```nginx
add_header X-Frame-Options "SAMEORIGIN";
add_header X-Content-Type-Options "nosniff";
add_header X-XSS-Protection "1; mode=block";
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
add_header Content-Security-Policy "default-src 'self'";
```

---

## Performance & Scalability

### Performance Metrics
- **Average Processing Time**: 45-65 seconds per patient
- **OCR Accuracy**: 90-95% on high-quality documents
- **NLP Accuracy**: 85-90% for medical entity extraction
- **Throughput**: 10-15 concurrent jobs per worker
- **API Response Time**: <200ms for status checks

### Scalability Strategies

#### Horizontal Scaling
```yaml
# Docker Compose scaling
docker-compose up --scale worker=5 --scale ocr-service=3
```

#### Load Balancing
```nginx
upstream api_backend {
    server api-gateway-1:8000;
    server api-gateway-2:8000;
    server api-gateway-3:8000;
}
```

#### Resource Optimization
- **Memory Management**: Efficient image processing with chunking
- **CPU Utilization**: Parallel processing for multiple pages
- **Storage Optimization**: Temporary file cleanup and compression
- **Cache Strategy**: Redis caching for frequently accessed data

### Performance Monitoring
```python
# Custom metrics collection
from prometheus_client import Counter, Histogram, Gauge

processing_time = Histogram('processing_time_seconds', 'Time spent processing')
job_counter = Counter('jobs_processed_total', 'Total processed jobs')
active_jobs = Gauge('active_jobs', 'Number of active jobs')
```

---

## Monitoring & Observability

### Metrics Collection
- **System Metrics**: CPU, memory, disk usage, network I/O
- **Application Metrics**: Request rates, error rates, processing times
- **Business Metrics**: Job completion rates, accuracy scores
- **Custom Metrics**: OCR confidence, NLP entity extraction success

### Alerting Rules
```yaml
groups:
  - name: claimease_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          
      - alert: ProcessingTimeHigh
        expr: histogram_quantile(0.95, processing_time_seconds) > 120
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Processing time above threshold"
```

### Logging Strategy
```python
import logging
import json

class StructuredLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        
    def log_processing_event(self, job_id, patient_name, event, details):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "job_id": job_id,
            "patient_name": patient_name,
            "event": event,
            "details": details,
            "service": "claimease"
        }
        self.logger.info(json.dumps(log_entry))
```

### Dashboard Configuration
- **Grafana Dashboards**: System overview, service health, business metrics
- **Prometheus Targets**: All services exposed on `/metrics` endpoints
- **Alert Manager**: Email and Slack notifications for critical issues

---

## Error Handling & Recovery

### Error Categories

#### 1. Document Errors
- **Missing Files**: Patient folder or required documents not found
- **Corrupted Files**: PDF files that cannot be opened or processed
- **Invalid Format**: Non-PDF files or unsupported document types

#### 2. Processing Errors
- **OCR Failures**: Low-quality images, unreadable text
- **NLP Errors**: Unable to extract required entities
- **Form Filling Errors**: Incompatible form types, field mapping failures

#### 3. System Errors
- **Service Unavailable**: Microservice downtime or network issues
- **Resource Exhaustion**: Out of memory, disk space, or CPU
- **Database Errors**: Connection failures, query timeouts

### Recovery Strategies

#### Circuit Breaker Pattern
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise ServiceUnavailableError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
```

#### Retry Logic
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(TransientError)
)
def call_service_with_retry(service_url, payload):
    return make_http_request(service_url, payload)
```

#### Graceful Degradation
- **Partial Processing**: Continue with available data when some steps fail
- **Fallback Options**: Use alternative processing methods when primary fails
- **Manual Intervention**: Flag jobs for human review when automated processing fails

---

## Deployment Architecture

### Container Orchestration
```yaml
version: '3.8'
services:
  api-gateway:
    image: claimease/api-gateway:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/claimease
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Production Deployment

#### Infrastructure Requirements
- **Compute**: 4 CPU cores, 16GB RAM minimum per node
- **Storage**: 100GB+ SSD for document processing
- **Network**: 1Gbps minimum for large document transfers
- **Backup**: Daily backups of PostgreSQL and critical files

#### Environment Configuration
```bash
# Production environment variables
export DATABASE_URL="postgresql://user:pass@prod-db:5432/claimease"
export REDIS_URL="redis://prod-redis:6379"
export MINIO_ENDPOINT="prod-minio:9000"
export LOG_LEVEL="INFO"
export SENTRY_DSN="https://your-sentry-dsn"
export PROMETHEUS_ENDPOINT="http://prometheus:9090"
```

#### Load Balancer Configuration
```nginx
upstream claimease_api {
    least_conn;
    server api-gateway-1:8000 max_fails=3 fail_timeout=30s;
    server api-gateway-2:8000 max_fails=3 fail_timeout=30s;
    server api-gateway-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.claimease.com;
    
    location / {
        proxy_pass http://claimease_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

---

## Development Guidelines

### Code Standards
- **Python**: PEP 8 compliance, type hints, docstrings
- **Testing**: Unit tests with >80% coverage, integration tests
- **Documentation**: Inline comments, API documentation
- **Version Control**: Git flow with feature branches

### Testing Strategy
```python
# Unit test example
def test_patient_name_extraction():
    ocr_text = "Patient: John Doe\nDOB: 01/15/1985"
    extractor = MedicalEntityExtractor()
    
    result = extractor.extract_patient_info(ocr_text)
    
    assert result['name'] == 'John Doe'
    assert result['dob'] == '1985-01-15'
    assert result['confidence'] > 0.8

# Integration test example
def test_end_to_end_processing():
    client = TestClient(app)
    
    # Create test patient data
    setup_test_patient_data("TestPatient")
    
    # Start processing
    response = client.post("/api/v1/patients/TestPatient/process")
    job_id = response.json()["job_id"]
    
    # Wait for completion
    wait_for_job_completion(job_id)
    
    # Verify results
    assert_output_files_exist("TestPatient")
    assert_form_fields_filled("TestPatient")
```

### Continuous Integration
```yaml
# GitHub Actions workflow
name: CI/CD Pipeline
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

---

## Conclusion

This technical architecture document provides a comprehensive overview of the ClaimEase system, detailing every aspect from high-level architecture to implementation specifics. The system is designed to be scalable, maintainable, and compliant with healthcare regulations while providing high accuracy and performance in automated PA form processing.

The microservices architecture ensures that each component can be developed, deployed, and scaled independently, while the event-driven design provides resilience and flexibility for handling varying workloads.

---

**Document Version**: 1.0  
**Last Updated**: June 18, 2025  
**Next Review**: July 18, 2025
