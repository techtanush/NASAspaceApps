"""Reads HTTP operations selected from the immutable contract."""

from fastapi import APIRouter

from analogforge.api.router import build_route_group

OPERATION_IDS = frozenset(
    [
        "listEarthAnalogCandidate",
        "getEarthAnalogCandidate",
        "listQualificationDimension",
        "getQualificationDimension",
        "listVerificationTest",
        "getVerificationTest",
        "getTestResult",
        "getCompositePortfolio",
        "getCompatibility",
        "getTargetProfile",
        "getReview",
        "listDisplayLayers",
    ]
)


def build_router() -> APIRouter:
    return build_route_group(OPERATION_IDS)
