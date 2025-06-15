-- Create tables for ClaimEase
CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    date_of_birth DATE,
    insurance_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id INTEGER REFERENCES patients(id),
    document_type VARCHAR(50) NOT NULL, -- 'pa_form' or 'referral_package'
    file_path VARCHAR(500) NOT NULL,
    status VARCHAR(50) DEFAULT 'uploaded',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id INTEGER REFERENCES patients(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extraction_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES processing_jobs(id),
    service_name VARCHAR(50) NOT NULL, -- ocr, nlp, form
    results JSONB,
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_documents_patient_id ON documents(patient_id);
CREATE INDEX idx_jobs_status ON processing_jobs(status);
CREATE INDEX idx_results_job_id ON extraction_results(job_id);