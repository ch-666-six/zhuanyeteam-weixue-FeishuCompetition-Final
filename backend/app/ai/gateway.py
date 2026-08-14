from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.provider import AiProvider
from app.modules.sessions.models import AiJob, AiRun


@dataclass(frozen=True)
class AiRequestContext:
    request_id: Optional[str]
    operation: str
    prompt_version: str
    schema_version: str


class AiGateway:
    """Single entry point for provider calls and debug metadata.

    The gateway deliberately owns run metadata but not business state transitions.
    A later worker can call `execute` without changing the API contract.
    """

    def __init__(self, provider: AiProvider):
        self.provider = provider

    def input_summary(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{digest};keys={','.join(sorted(payload))}"

    def record_queued(self, db: Session, job: AiJob, context: AiRequestContext, payload: dict[str, Any]) -> AiRun:
        run = AiRun(
            id=str(uuid4()),
            job_id=job.id,
            request_id=context.request_id,
            provider=self.provider.info.name,
            model=self.provider.info.model,
            operation=context.operation,
            prompt_version=context.prompt_version,
            schema_version=context.schema_version,
            status="QUEUED",
            input_summary=self.input_summary(payload),
            started_at=datetime.now(timezone.utc),
        )
        db.add(run)
        return run

    def execute(self, run: AiRun, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke a provider with uniform timing, summaries, and error semantics.

        The worker owns transaction commits and domain-result validation. This
        method is the only place allowed to call `provider.invoke`.
        """
        started = time.perf_counter()
        run.status = "RUNNING"
        try:
            output = self.provider.invoke(run.operation, payload)
            run.output_summary = self.input_summary(output)
            run.status = "SUCCEEDED"
            return output
        except Exception:
            run.status = "FAILED"
            run.error_code = "AI_PROVIDER_ERROR"
            raise
        finally:
            run.duration_ms = max(0, round((time.perf_counter() - started) * 1000))
            run.finished_at = datetime.now(timezone.utc)
