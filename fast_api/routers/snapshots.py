from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from dwh.database import get_db
from fast_api.schemas import SnapshotSummary, CompanyDetails

router = APIRouter(prefix="/snapshots", tags=["Snapshots"])

@router.get("", response_model=List[SnapshotSummary])
def list_snapshots(
    company_id: Optional[str] = Query(None, description="Filter by company name"),
    from_date: Optional[datetime] = Query(None, description="System Time start (e.g. Find files uploaded after this date)"),
    to_date: Optional[datetime] = Query(None, description="System Time end (e.g. Find files uploaded before this date)"),
    sector: Optional[str] = Query(None, description="Filter by corporate sector"),
    country: Optional[str] = Query(None, description="Filter by country of origin"),
    currency: Optional[str] = Query(None, description="Filter by reporting currency"),
    db: Session = Depends(get_db)
):
    """
    List all company snapshots with optional filters.
    
    **Target Persona:** Data Engineers, Operations, and Compliance Auditors.
    This endpoint searches the physical System/Audit timeline. `from_date` and `to_date` filter by when the file was processed by the pipeline (`sys_valid_from`), NOT the financial year the document represents.
    """
    where_clauses = []
    params = {}
    
    if company_id:
        where_clauses.append("company_name = :company_id")
        params["company_id"] = company_id
    if from_date:
        where_clauses.append("sys_valid_from >= :from_date")
        params["from_date"] = from_date
    if to_date:
        where_clauses.append("sys_valid_from <= :to_date")
        params["to_date"] = to_date
    if sector:
        where_clauses.append("corporate_sector = :sector")
        params["sector"] = sector
    if country:
        where_clauses.append("country_of_origin = :country")
        params["country"] = country
    if currency:
        where_clauses.append("reporting_currency = :currency")
        params["currency"] = currency
        
    where_sql = " AND ".join(where_clauses)
    if where_sql:
        where_sql = "WHERE " + where_sql
        
    query = text(f"""
        SELECT 
            id, version_id, company_name, filename, 
            DATE_TRUNC('second', sys_valid_from) AS sys_valid_from,
            DATE_TRUNC('second', sys_valid_to) AS sys_valid_to,
            is_latest_version_for_business_year, is_system_current,
            max_actual_year, end_of_business_year, corporate_sector, 
            business_risk_profile, financial_risk_profile
        FROM marts.dim_corporate_ratings
        {where_sql}
        ORDER BY sys_valid_from DESC;
    """)
    result = db.execute(query, params).mappings().all()
    return result

@router.get("/latest", response_model=List[SnapshotSummary])
def get_latest_snapshots(db: Session = Depends(get_db)):
    """Get the absolute newest physical snapshot for each company."""
    query = text("""
        SELECT 
            id, version_id, company_name, filename, 
            DATE_TRUNC('second', sys_valid_from) AS sys_valid_from,
            DATE_TRUNC('second', sys_valid_to) AS sys_valid_to,
            is_latest_version_for_business_year, is_system_current,
            max_actual_year, end_of_business_year, corporate_sector, 
            business_risk_profile, financial_risk_profile
        FROM marts.dim_corporate_ratings
        WHERE is_system_current = TRUE
        ORDER BY company_name;
    """)
    result = db.execute(query).mappings().all()
    return result

@router.get("/{snapshot_id}", response_model=CompanyDetails)
def get_snapshot_details(snapshot_id: str, db: Session = Depends(get_db)):
    """
    Get specific snapshot details including all financial metrics.
    Note: snapshot_id refers to the internal system surrogate key.
    For a more domain-driven approach, see GET /companies/{company_name}/versions/{version_id}
    """
    query = text("""
        SELECT *
        FROM marts.exp_company_details
        WHERE id = :snapshot_id
    """)
    result = db.execute(query, {"snapshot_id": snapshot_id}).mappings().first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Snapshot not found")
        
    return CompanyDetails(**dict(result))
