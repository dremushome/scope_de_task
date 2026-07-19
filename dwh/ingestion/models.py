from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from dwh.database import Base

class SourceFileAudit(Base):
    __tablename__ = 'source_files_audit'

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    file_hash = Column(String(64), unique=True, nullable=False) # SHA-256 checksum
    s3_path = Column(String(512), nullable=False)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Link back to parsed staging records
    parsed_records = relationship("RawCorporateCreditRating", back_populates="upload", cascade="all, delete-orphan")


class RawCorporateCreditRating(Base):
    __tablename__ = 'raw_corporate_credit_ratings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer, ForeignKey('source_files_audit.id', ondelete='CASCADE'), nullable=False)
    parsed_payload = Column(JSONB, nullable=False)
    parsed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Link back to raw upload
    upload = relationship("SourceFileAudit", back_populates="parsed_records")
