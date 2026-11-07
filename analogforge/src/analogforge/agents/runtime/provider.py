"""Provider failures are typed; no prose-to-verdict parser exists."""

from typing import Any, Protocol

from analogforge.agents.schemas.submission import RoleSubmission
from analogforge.agents.schemas.task import AgentTask
from analogforge.ports.hashing import canonical_sha256
from analogforge.tools.registry import ToolContext, ToolRegistry


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ModelProvider(Protocol):
    def run(self, task: AgentTask, registry: ToolRegistry, context: ToolContext) -> RoleSubmission: ...


class ReplayProvider:
    def __init__(self, recordings: dict[str, dict[str, Any]]) -> None:
        self.recordings = recordings

    def run(self, task: AgentTask, registry: ToolRegistry, context: ToolContext) -> RoleSubmission:
        key = task.payload.get("recording_key")
        if key not in self.recordings:
            raise ProviderError("REPLAY_INTEGRITY_ERROR", "No checksummed role recording exists")
        recording = self.recordings[key]
        if (
            set(recording) != {"submission", "sha256"}
            or canonical_sha256(recording["submission"]) != recording["sha256"]
        ):
            raise ProviderError("REPLAY_INTEGRITY_ERROR", "Role recording failed its manifest checksum")
        submission = RoleSubmission.model_validate(recording["submission"])
        submission.validate_payload()
        return submission
