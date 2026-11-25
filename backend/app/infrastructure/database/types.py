from sqlalchemy import JSON, DateTime
from sqlalchemy.dialects.postgresql import JSONB

JSONType = JSON().with_variant(JSONB(), "postgresql")
TimestampType = DateTime(timezone=True)
