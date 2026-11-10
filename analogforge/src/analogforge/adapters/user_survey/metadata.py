"""Metadata contract for user-uploaded Earth DEMs (architecture 08 section 8)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from analogforge.adapters.source_http.errors import AdapterError

REQUIRED_FOR_QUANTITATIVE = (
    "body",
    "horizontal_reference",
    "vertical_reference",
    "vertical_units",
    "acquisition_time",
    "cell_support_m",
    "provenance",
    "rights_declaration",
    "stated_uncertainty_m",
)


class SurveyMetadata(BaseModel):
    """Everything a user must declare. Absent fields are ``None`` (unknown) and block quantitative use."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    body: str | None = None
    horizontal_reference: str | None = None
    vertical_reference: str | None = None
    vertical_units: str | None = None
    acquisition_time: str | None = None
    cell_support_m: float | None = Field(default=None, gt=0)
    provenance: str | None = None
    rights_declaration: str | None = None
    stated_uncertainty_m: float | None = Field(default=None, ge=0)
    nodata_value: float | None = None  # used when the GeoTIFF itself declares none

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        for name in REQUIRED_FOR_QUANTITATIVE:
            value = getattr(self, name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(name)
        return missing


def load_metadata(path: Path) -> SurveyMetadata:
    try:
        return SurveyMetadata.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        raise AdapterError(
            "SOURCE_CONTENT_INVALID",
            f"{path.name} is not a valid survey metadata file",
            detail_code="METADATA_INCOMPLETE",
        ) from exc
