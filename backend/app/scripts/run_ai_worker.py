import time
from uuid import uuid4

from app.ai.gateway import AiGateway
from app.ai.provider import build_ai_provider
from app.ai.worker import AiWorker
from app.config import get_settings
from app.infrastructure.database import create_session_factory


def main() -> None:
    settings = get_settings()
    if not settings.ai_worker_enabled:
        raise RuntimeError("AI worker is disabled by AI_WORKER_ENABLED=false")
    provider = build_ai_provider(settings.ai_provider, settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model)
    worker = AiWorker(create_session_factory(settings), AiGateway(provider), f"worker-{uuid4()}", settings.ai_job_lease_seconds, settings.ai_job_max_attempts)
    while True:
        if not worker.process_next():
            time.sleep(settings.ai_worker_poll_seconds)


if __name__ == "__main__":
    main()
