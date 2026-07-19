from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from dwh.database import get_db
from fast_api.schemas import CompanySummary, CompanyDetails, Metric, SnapshotSummary

router = APIRouter(prefix="/companies", tags=["Companies"])

@router.get("", response_model=List[CompanySummary])
def list_companies(db: Session = Depends(get_db)):
    """List all companies with current metadata."""
    query = text("""
        SELECT 
            company_name,
            corporate_sector,
            country_of_origin,
            reporting_currency,
            business_risk_profile,
            financial_risk_profile
        FROM marts.dim_corporate_ratings
        WHERE is_system_current = TRUE
        ORDER BY company_name;
    """)
    result = db.execute(query).mappings().all()
    return result

@router.get("/compare", response_model=List[CompanyDetails])
def compare_companies(
    company_ids: List[str] = Query(..., description="List of company names to compare"),
    as_of_date: Optional[datetime] = Query(None, description="Audit point-in-time date (System Time)"),
    business_year: Optional[int] = Query(None, description="Financial/Business year for comparison (Business Time)"),
    db: Session = Depends(get_db)
):
    """Compare multiple companies at specific point in time (Audit timeline) OR specific business year."""
    if not as_of_date and not business_year:
        raise HTTPException(status_code=400, detail="Must provide either as_of_date or business_year")
        
    if as_of_date:
        cte = """
        WITH target_dims AS (
            SELECT * FROM marts.exp_company_details
            WHERE company_name = ANY(:company_ids)
              AND sys_valid_from <= :as_of_date 
              AND (sys_valid_to > :as_of_date OR sys_valid_to IS NULL)
        )
        """
    else:
        # business_year provided
        cte = """
        WITH target_dims AS (
            SELECT *
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY company_name ORDER BY max_actual_year DESC) as rn
                FROM marts.exp_company_details
                WHERE is_latest_version_for_business_year = TRUE
                  AND company_name = ANY(:company_ids)
            ) x
            WHERE rn = 1
        )
        """

    query = text(f"""
        {cte}
        SELECT *
        FROM target_dims
    """)
    result = db.execute(query, {
        "company_ids": company_ids,
        "as_of_date": as_of_date
    }).mappings().all()

    parsed_results = []
    for row in result:
        row_dict = dict(row)
        if business_year:
            row_dict["metrics"] = [
                m for m in row_dict.get("metrics", [])
                if m.get("year") == business_year or m.get("year") is None
            ]
        parsed_results.append(CompanyDetails(**row_dict))

    return parsed_results

@router.get("/{company_id}", response_model=CompanyDetails)
def get_company(company_id: str, db: Session = Depends(get_db)):
    """Get full company details for the absolute latest version."""
    query = text("""
        SELECT *
        FROM marts.exp_company_details
        WHERE company_name = :company_id 
          AND is_latest_version_for_business_year = TRUE
        ORDER BY end_of_business_year DESC
        LIMIT 1
    """)
    result = db.execute(query, {"company_id": company_id}).mappings().first()
    if not result:
        raise HTTPException(status_code=404, detail="Company not found")
        
    return CompanyDetails(**dict(result))

@router.get("/{company_id}/versions", response_model=List[SnapshotSummary])
def get_company_versions(company_id: str, db: Session = Depends(get_db)):
    """Get a lightweight summary of all versions for a company."""
    query = text("""
        SELECT 
            id, version_id, company_name, filename, 
            DATE_TRUNC('second', sys_valid_from) AS sys_valid_from,
            DATE_TRUNC('second', sys_valid_to) AS sys_valid_to,
            is_latest_version_for_business_year, is_system_current,
            max_actual_year, end_of_business_year, corporate_sector, 
            business_risk_profile, financial_risk_profile
        FROM marts.dim_corporate_ratings
        WHERE company_name = :company_id
        ORDER BY sys_valid_from DESC;
    """)
    result = db.execute(query, {"company_id": company_id}).mappings().all()
    return result

@router.get("/{company_id}/history", response_model=List[dict])
def get_company_history(company_id: str, db: Session = Depends(get_db)):
    """Get time-series data for analysis based on restated ultimate truth."""
    query = text("""
        WITH latest_dim AS (
            SELECT *
            FROM marts.dim_corporate_ratings
            WHERE company_name = :company_id 
              AND is_latest_version_for_business_year = TRUE
            ORDER BY end_of_business_year DESC
            LIMIT 1
        )
        SELECT 
            d.end_of_business_year AS evaluation_year,
            f.metric_name AS name,
            f.metric_value_numeric AS value,
            f.metric_year AS year
        FROM latest_dim d
        JOIN marts.fct_corporate_metrics f ON d.id = f.rating_id
        ORDER BY f.metric_year ASC;
    """)
    result = db.execute(query, {"company_id": company_id}).mappings().all()
    return result

@router.get("/{company_id}/versions/{version_id}", response_model=CompanyDetails)
def get_company_version_details(company_id: str, version_id: int, db: Session = Depends(get_db)):
    """
    Get the full financial details and metrics for a specific historical version of a company.
    
    This is much more user-friendly than requiring an internal database `snapshot_id`. 
    Users simply request the company name and the readable version number (e.g., version 1, 2, 3).
    """
    query = text("""
        SELECT *
        FROM marts.exp_company_details
        WHERE company_name = :company_id AND version_id = :version_id
    """)
    result = db.execute(query, {"company_id": company_id, "version_id": version_id}).mappings().first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Company version not found")
        
    return CompanyDetails(**dict(result))
