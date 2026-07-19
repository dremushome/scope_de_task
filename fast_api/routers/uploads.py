from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import boto3
import os
from urllib.parse import urlparse
from dwh.database import get_db
from fast_api.schemas import UploadAuditSummary, UploadAudit, UploadStats

router = APIRouter(prefix="/uploads", tags=["Upload Audits"])

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id=os.getenv('MINIO_ROOT_USER', 'minioadmin'),
        aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin')
    )

@router.get("", response_model=List[UploadAuditSummary])
def list_uploads(db: Session = Depends(get_db)):
    """List all file uploads with metadata."""
    query = text("""
        SELECT 
            upload_id::text, 
            filename, 
            updated_at, 
            data_quality_passed,
            business_rules_passed,
            parser_sha, 
            schema_sha 
        FROM marts.fct_upload_audits
        ORDER BY updated_at DESC;
    """)
    result = db.execute(query).mappings().all()
    return result

@router.get("/stats", response_model=UploadStats)
def get_upload_stats(db: Session = Depends(get_db)):
    """Upload statistics and metrics."""
    query_total = text("SELECT COUNT(*) as total FROM marts.fct_upload_audits")
    total = db.execute(query_total).scalar() or 0
    
    query_dates = text("""
        SELECT DATE(updated_at) as date, COUNT(*) as count
        FROM marts.fct_upload_audits
        GROUP BY DATE(updated_at)
        ORDER BY date DESC
    """)
    dates = db.execute(query_dates).mappings().all()
    
    return UploadStats(
        total_uploads=total,
        uploads_by_date=[dict(row) for row in dates]
    )

@router.get("/{upload_id}/details", response_model=UploadAudit)
def get_upload_details(upload_id: str, db: Session = Depends(get_db)):
    """Get specific upload details and parsed payload."""
    query = text("""
        SELECT 
            upload_id::text, 
            filename, 
            updated_at, 
            data_quality_passed,
            business_rules_passed,
            parser_sha, 
            schema_sha, 
            parsed_payload
        FROM marts.fct_upload_audits
        WHERE upload_id::text = :upload_id
    """)
    result = db.execute(query, {"upload_id": upload_id}).mappings().first()
    if not result:
        raise HTTPException(status_code=404, detail="Upload not found")
    return dict(result)

@router.get("/{upload_id}/file")
def download_upload_file(upload_id: int, db: Session = Depends(get_db)):
    """Download original Excel file from MinIO."""
    query = text("SELECT s3_path FROM ingestion.source_files_audit WHERE id = :upload_id")
    s3_path = db.execute(query, {"upload_id": upload_id}).scalar()
    
    if not s3_path:
        raise HTTPException(status_code=404, detail="Upload not found in audit table")
        
    # Parse s3://bucket/key
    parsed = urlparse(s3_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch file from storage: {str(e)}")
        
    return StreamingResponse(
        response['Body'],
        media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
        headers={"Content-Disposition": f"attachment; filename={key.split('_', 1)[-1]}"}
    )
