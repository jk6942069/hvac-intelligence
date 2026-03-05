import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, DateTime, JSON, ForeignKey
from database import Base


def generate_id():
    return str(uuid.uuid4())


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, nullable=False, index=True)
    address = Column(String)
    city = Column(String, index=True)
    state = Column(String, index=True)
    phone = Column(String)
    website = Column(String)
    email = Column(String)
    google_place_id = Column(String, unique=True, index=True)
    google_rating = Column(Float)
    google_review_count = Column(Integer)
    category = Column(String, default="HVAC")

    # Enrichment
    domain = Column(String)
    domain_age_years = Column(Float)
    ssl_valid = Column(Boolean)
    ssl_expiry = Column(String)
    tech_stack = Column(JSON, default=list)
    website_active = Column(Boolean)
    website_load_time_ms = Column(Integer)
    website_last_checked = Column(String)
    has_facebook = Column(Boolean)
    has_instagram = Column(Boolean)
    website_outdated = Column(Boolean)

    # Content enrichment signals (from website analysis)
    is_family_owned_likely = Column(Boolean, nullable=True)
    offers_24_7 = Column(Boolean, nullable=True)
    service_count_estimated = Column(Integer, nullable=True)
    years_in_business_claimed = Column(Integer, nullable=True)
    is_recruiting = Column(Boolean, nullable=True)
    technician_count_estimated = Column(Integer, nullable=True)
    serves_commercial = Column(Boolean, nullable=True)
    discovery_source = Column(String, nullable=True)   # "firecrawl_search" | "yellowpages" | "mock"
    content_enriched = Column(Boolean, default=False)
    council_analyzed = Column(Boolean, default=False)

    # Signals (JSON array of signal objects)
    signals = Column(JSON, default=list)

    # Scoring - old single score kept for backward compat
    score = Column(Integer, default=0, index=True)
    score_breakdown = Column(JSON, default=dict)

    # NEW: 3-dimensional underwriting scores
    transition_score = Column(Integer, default=0)   # 0-40: seller likelihood / pressure
    quality_score = Column(Integer, default=0)       # 0-35: business quality / transferability
    platform_score = Column(Integer, default=0)      # 0-25: roll-up / platform fit
    conviction_score = Column(Integer, default=0, index=True)  # 0-100: final weighted score
    score_explanation = Column(JSON, default=dict)   # factor contributions + thesis

    # Status
    status = Column(String, default="pending", index=True)
    rank = Column(Integer, index=True)

    # Workflow / CRM
    workflow_status = Column(String, default="not_contacted", index=True)
    # Enum: not_contacted / contacted / responded / interested / not_interested / follow_up / closed_lost / closed_won
    workflow_notes = Column(Text)
    outreach_date = Column(String)
    last_contact_date = Column(String)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Legacy feedback fields
    feedback_outcome = Column(String)
    feedback_notes = Column(Text)
    feedback_date = Column(String)

    # Raw data
    raw_google_data = Column(JSON)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True, default=generate_id)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String, default="running")
    total_companies = Column(Integer, default=0)
    processed_companies = Column(Integer, default=0)
    current_stage = Column(String, default="initializing")
    error = Column(Text)
    config_json = Column(JSON)


class Dossier(Base):
    __tablename__ = "dossiers"

    id = Column(String, primary_key=True, default=generate_id)
    company_id = Column(String, nullable=False, index=True)
    content = Column(Text)
    generated_at = Column(DateTime, default=datetime.utcnow)
    model_used = Column(String, default="claude-3-5-sonnet-20241022")


class Memo(Base):
    """Investment memo -- IC-packet style document."""
    __tablename__ = "memos"

    id = Column(String, primary_key=True, default=generate_id)
    company_id = Column(String, nullable=False, index=True)
    version = Column(Integer, default=1)
    title = Column(String)
    content = Column(Text)          # Markdown
    status = Column(String, default="draft")   # draft / final
    generated_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    model_used = Column(String, default="claude-3-5-sonnet-20241022")


class WorkflowEvent(Base):
    """CRM audit trail -- every status change."""
    __tablename__ = "workflow_events"

    id = Column(String, primary_key=True, default=generate_id)
    company_id = Column(String, nullable=False, index=True)
    from_status = Column(String)
    to_status = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompDeal(Base):
    """Comparable HVAC acquisition deals -- proxy comps dataset."""
    __tablename__ = "comp_deals"

    id = Column(String, primary_key=True, default=generate_id)
    deal_name = Column(String)
    deal_year = Column(Integer)
    geography = Column(String)   # e.g. "Southeast US"
    deal_type = Column(String)   # e.g. "PE platform add-on", "Search fund acquisition"
    revenue_range = Column(String)   # e.g. "$1M-$3M"
    ebitda_multiple_low = Column(Float)
    ebitda_multiple_high = Column(Float)
    sde_multiple_low = Column(Float)
    sde_multiple_high = Column(Float)
    notes = Column(Text)
    source = Column(String, default="proxy")  # proxy / verified
    created_at = Column(DateTime, default=datetime.utcnow)
