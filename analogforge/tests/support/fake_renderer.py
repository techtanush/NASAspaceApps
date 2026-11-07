"""Tests-only pure renderer. Real presentation is Aradhya's responsibility."""

from __future__ import annotations

import csv
import html
import io
import json

from analogforge.ports.hashing import bytes_sha256
from analogforge.ports.passport_renderer import (
    CSV_COLUMNS,
    ExportFormat,
    PassportExportBundle,
    ProvidedAsset,
    RenderedExport,
    RendererError,
)


class FakePassportRenderer:
    renderer_version = "test-double-1.0"

    def render(self, bundle: PassportExportBundle, assets: list[ProvidedAsset], fmt: ExportFormat) -> RenderedExport:
        if bytes_sha256(bundle.canonical_manifest_json.encode()) != bundle.manifest_sha256:
            raise RendererError("MANIFEST_MISMATCH", "Canonical manifest bytes do not match digest")
        for asset in assets:
            if bytes_sha256(asset.content) != asset.sha256:
                raise RendererError("ASSET_MISMATCH", "Provided image hash mismatch")
        document = bundle.model_dump(mode="json", exclude={"canonical_manifest_json"})
        if fmt == "json":
            content = (
                json.dumps(
                    {
                        "export_schema_version": "1.0",
                        "manifest_sha256": bundle.manifest_sha256,
                        "canonical_manifest": json.loads(bundle.canonical_manifest_json),
                        "bundle": document,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode()
            media_type = "application/json"
        elif fmt == "html":
            content = (
                "<!doctype html><html><body><h1>TEST DOUBLE</h1><pre>"
                + html.escape(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2))
                + "</pre></body></html>\n"
            ).encode()
            media_type = "text/html; charset=utf-8"
        else:
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            candidates = {candidate.id: candidate for candidate in bundle.candidates}
            requirements = {requirement.id: requirement for requirement in bundle.mission.requirements}
            for row in bundle.qualifications:
                requirement = requirements[row.requirement_id]
                data = {
                    "passport_id": str(bundle.passport.id),
                    "run_id": str(bundle.passport.run_id),
                    "mode": bundle.mode,
                    "mission_revision_id": str(bundle.mission.id),
                    "rover_revision_id": str(bundle.rover.id) if bundle.rover else "",
                    "candidate_id": str(row.candidate_id),
                    "candidate_name": candidates[row.candidate_id].name,
                    "requirement_id": row.requirement_id,
                    "requirement_label": requirement.label,
                    "mandatory": str(requirement.mandatory),
                    "qualification_status": row.status,
                    "observable": requirement.observable,
                    "operator": requirement.operator,
                    "threshold_lower": str(requirement.lower) if requirement.lower is not None else "",
                    "threshold_upper": str(requirement.upper) if requirement.upper is not None else "",
                    "unit": requirement.unit,
                    "comparison_scale_m": str(row.comparison_scale_m or ""),
                    "confidence": row.confidence,
                    "critic_status": row.critic_status,
                    "limitations": " | ".join(row.limitations),
                    "evidence_ids": " | ".join(map(str, row.evidence_ids)),
                    "assurance_disposition": bundle.assurance.publication if bundle.assurance else "DRAFT",
                    "manifest_sha256": bundle.manifest_sha256,
                }
                writer.writerow(
                    {
                        key: "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
                        for key, value in data.items()
                    }
                )
            content = stream.getvalue().encode()
            media_type = "text/csv; charset=utf-8"
        return RenderedExport(
            format=fmt,
            content=content,
            media_type=media_type,
            filename=f"analogforge-passport-{bundle.mode}-{str(bundle.passport.id)[:8]}-{bundle.manifest_sha256[:8]}.{fmt}",
            sha256=bytes_sha256(content),
            renderer_version=self.renderer_version,
            referenced_evidence_ids=[e.id for e in bundle.evidence_appendix],
        )
