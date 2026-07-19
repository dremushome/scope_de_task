from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class CompanySummary(BaseModel):
    company_name: str
    corporate_sector: Optional[str] = None
    country_of_origin: Optional[str] = None
    reporting_currency: Optional[str] = None
    business_risk_profile: Optional[str] = None
    financial_risk_profile: Optional[str] = None

class Metric(BaseModel):
    name: str
    value: Optional[float] = None
    year: Optional[int] = None
    year_type: Optional[str] = None

class CompanyDetails(CompanySummary):
    id: Any
    version_id: Optional[int] = None
    end_of_business_year: Optional[str] = None
    accounting_principles: Optional[str] = None
    metrics: List[Metric] = []

class SnapshotSummary(BaseModel):
    id: Any
    version_id: Optional[int] = None
    company_name: str
    filename: str
    sys_valid_from: datetime
    sys_valid_to: Optional[datetime] = None
    is_latest_version_for_business_year: bool
    is_system_current: bool
    max_actual_year: Optional[int] = None
    end_of_business_year: Optional[str] = None
    corporate_sector: Optional[str] = None
    business_risk_profile: Optional[str] = None
    financial_risk_profile: Optional[str] = None

class UploadAuditSummary(BaseModel):
    upload_id: str
    filename: str
    updated_at: datetime
    data_quality_passed: bool
    business_rules_passed: bool
    parser_sha: Optional[str] = None
    schema_sha: Optional[str] = None

class UploadAudit(UploadAuditSummary):
    parsed_payload: Dict[str, Any]

class UploadStats(BaseModel):
    total_uploads: int
    uploads_by_date: List[Dict[str, Any]]
