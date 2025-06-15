# ClaimEase Architecture Overview

**High-level architecture documentation for the ClaimEase system**

## 🏗️ System Architecture

### **Microservices Overview**
```
┌─────────────────────────────────────────────────────────────┐
│                     ClaimEase System                       │
├─────────────────────────────────────────────────────────────┤
│ Client → API Gateway → Worker → Services → Data Storage    │
└─────────────────────────────────────────────────────────────┘
```

### **Service Breakdown**

#### **1. API Gateway (Port 8000)**
- **Technology**: FastAPI + Uvicorn + Nginx
- **Purpose**: Entry point, job management, client communication
- **Responsibilities**: Request routing, authentication, job orchestration

#### **2. Background Worker**
- **Technology**: Celery + Redis broker
- **Purpose**: Orchestrate processing pipeline
- **Responsibilities**: Queue management, service coordination, progress tracking

#### **3. Document Service**
- **Technology**: FastAPI + File System
- **Purpose**: PDF file analysis and management
- **Responsibilities**: File discovery, path resolution, document metadata

#### **4. OCR Service**
- **Technology**: EasyOCR + PyMuPDF + PIL
- **Purpose**: Text extraction from PDF documents
- **Responsibilities**: Image conversion, optical character recognition, text structuring

#### **5. NLP Service**
- **Technology**: spaCy + Regex patterns
- **Purpose**: Medical entity extraction and classification
- **Responsibilities**: Named entity recognition, entity categorization, confidence scoring

#### **6. Form Service**
- **Technology**: pdftk + tempfile (migrating to PyMuPDF)
- **Purpose**: PA form filling with extracted data
- **Responsibilities**: Field mapping, form filling, output generation

## 🔄 Data Flow

### **Processing Pipeline**
```
Upload → Analysis → OCR → NLP → Form Filling → Output
  10%      25%      50%   75%       100%
```

### **Redis Key Structure**
```
job:{job_id}          - Job metadata and status
analysis:{patient}    - File paths and document info
ocr:{patient}         - Extracted text with coordinates  
nlp:{patient}         - Named entities and classifications
form:{patient}        - Final form filling results
```

### **File System Layout**
```
/app/data/
├── Input Data/{patient}/
│   ├── referral_package.pdf  (source document)
│   └── PA.pdf                (form template)
└── output/{patient}/
    └── filled_pa_form.pdf    (final result)
```

## 💾 Infrastructure Components

### **Database Layer**
- **PostgreSQL 15**: Primary data persistence, job metadata
- **Redis 7**: Caching, queuing, inter-service communication
- **MinIO**: S3-compatible object storage for large files

### **Containerization**
- **Docker Compose**: Multi-container orchestration
- **Service Scaling**: 2x replicas for document and OCR services
- **Health Checks**: Automated service monitoring

### **Monitoring Stack**
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Dashboards and visualization
- **Logging**: Structured logging across all services

## 🔧 Current Status

### **✅ Working Components**
- Complete microservices pipeline operational
- Redis-based data flow functioning
- OCR text extraction with high accuracy
- NLP entity extraction mapping 27+ fields
- Background job processing with progress tracking
- Monitoring and health checks active

### **⚠️ Known Issues**
- **Form Filling Visibility**: pdftk fills fields but they're not visible
- **Single Form Support**: Only handles one PA form type
- **Manual Configuration**: Requires manual field mapping

### **🔧 Planned Enhancements**
- **PyMuPDF Migration**: Coordinate-based form filling
- **Multi-Form Support**: Template database and form detection
- **Enhanced NLP**: scispaCy for medical entities
- **AI Form Understanding**: LayoutLM evaluation

## 🚀 Technical Specifications

### **Core Technologies**
- **Backend**: Python 3.x + FastAPI + async/await
- **HTTP Client**: httpx for inter-service communication
- **Database**: asyncpg + SQLAlchemy for PostgreSQL
- **Caching**: redis.asyncio for Redis operations
- **Task Queue**: Celery for background processing

### **AI/ML Stack**
- **OCR**: EasyOCR with CPU processing
- **NLP**: spaCy en_core_web_sm model
- **Image Processing**: PIL for PDF to image conversion
- **PDF Manipulation**: PyMuPDF (fitz) for document handling

### **DevOps & Deployment**
- **Containerization**: Docker with multi-stage builds
- **Orchestration**: Docker Compose with service discovery
- **Configuration**: Environment variables and config files
- **Networking**: Internal Docker networking with port mapping

## 📊 Performance Characteristics

### **Throughput**
- **OCR Processing**: ~30 seconds per document (300 DPI)
- **NLP Analysis**: ~5 seconds per document
- **End-to-End**: ~45 seconds total pipeline time
- **Concurrent Jobs**: Multiple jobs supported via Redis queue

### **Scalability**
- **Horizontal**: Additional service replicas via Docker Compose
- **Vertical**: Resource allocation per container
- **Storage**: Redis for fast access, PostgreSQL for persistence
- **Monitoring**: Real-time metrics and alerting

### **Reliability**
- **Health Checks**: Automated service availability monitoring
- **Error Handling**: Graceful degradation and retry logic
- **Data Persistence**: Multiple storage layers for redundancy
- **Logging**: Comprehensive logging for debugging

---

**📁 Related Documentation**
- [AI Context](../ai-context.md) - Current project status
- [Development Notes](../development/progress-notes.md) - Progress tracking
- [Conversation History](../ai-conversations/) - Technical discussions

**🔄 Last Updated**: June 15, 2025  
**Architecture Version**: v1.0 (microservices foundation)  
**Next Review**: After PyMuPDF migration
