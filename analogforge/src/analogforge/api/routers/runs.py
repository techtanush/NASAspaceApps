"""Runs HTTP operations selected from the immutable contract."""

from fastapi import APIRouter

from analogforge.api.router import build_route_group

OPERATION_IDS = frozenset(["createRun", "listRuns", "getRun", "submitRunAction", "streamRunEvents"])


def build_router() -> APIRouter:
    return build_route_group(OPERATION_IDS)
