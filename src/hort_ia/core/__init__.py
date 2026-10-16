"""Building blocks shared by the Hort.IA datasets."""

from .geo import Region, region_from_ibge_code, region_from_uf
from .privacy import (
    ConsentError,
    ConsentRecord,
    ConsentValidator,
    ImageAnonymizer,
    PIIAuditor,
    PIIAuditReport,
    PrivacyPipeline,
    TextAnonymizer,
)
from .sources import ID_PATTERN, Source, SourceRef

__all__ = [
    "ConsentError",
    "ConsentRecord",
    "ConsentValidator",
    "ID_PATTERN",
    "ImageAnonymizer",
    "PIIAuditor",
    "PIIAuditReport",
    "PrivacyPipeline",
    "Region",
    "Source",
    "SourceRef",
    "TextAnonymizer",
    "region_from_ibge_code",
    "region_from_uf",
]
