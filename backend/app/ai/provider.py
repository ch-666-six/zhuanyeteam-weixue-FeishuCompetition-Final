import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib import error, request

from app.ai.initial_analysis import InitialAnalysisV1, InitialAnalysisV2
from app.ai.coaching import CoachingQuestionV1
from app.ai.final_evaluation import FinalEvaluationV1

@dataclass(frozen=True)
class ProviderInfo:
    name: str
    model: str


class AiProvider(Protocol):
    @property
    def info(self) -> ProviderInfo: ...

    def invoke(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class AiProviderError(RuntimeError):
    pass


class AiProviderTransientError(AiProviderError):
    pass


class MockAiProvider:
    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="mock", model="deterministic-v1")

    def invoke(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "INITIAL_ANALYSIS":
            answer = str(payload["answer"])
            quote = answer[: min(len(answer), 42)]
            return {
            "mock": True,
            "schema_version": "initial-analysis-v2",
            "elements": [
                {"element": "viewpoint", "status": "present", "summary": "已经表达了自己的主要看法。", "quotes": [quote]},
                {"element": "reasons", "status": "emerging", "summary": "已经开始说明理由，可以再说清理由与观点的关系。", "quotes": []},
                {"element": "evidence", "status": "missing", "summary": "还可以加入一个具体事实或例子。", "quotes": []},
                {"element": "counterpoint", "status": "missing", "summary": "暂未提到可能的不同看法。", "quotes": []},
                {"element": "response", "status": "missing", "summary": "暂未回应不同看法。", "quotes": []},
                {"element": "conditions", "status": "missing", "summary": "暂未说明观点适用的条件或边界。", "quotes": []},
            ],
            "priority_improvement": {"element": "evidence", "suggestion": "补充一个亲身经历或校园中的具体例子，说明这个理由为什么成立。"},
            "opening_question": {"question": "你能举一个具体例子，说明这个理由在真实情境中为什么成立吗？", "focus_element": "evidence", "scaffold_type": "concrete_example"},
        }
        if operation == "COACHING_QUESTION":
            round_number = int(payload.get("roundNumber", 2))
            return {
                "mock": True,
                "schema_version": "coaching-question-v1",
                "question": f"结合你刚才的回答，你还能从另一个角度说明第 {round_number} 轮要补充的内容吗？",
                "focus_element": "response",
                "scaffold_type": "alternative_perspective",
            }
        if operation == "FINAL_EVALUATION":
            initial = str(payload["initialAnswer"])
            final = str(payload["finalAnswer"])
            final_quote = final[: min(len(final), 48)]
            initial_quote = initial[: min(len(initial), 36)]
            return {
                "mock": True, "schema_version": "final-evaluation-v1", "rubric_version": "argument-writing-v1",
                "summary": "终稿保留了原来的观点，并用更具体的内容支持了表达。",
                "strengths": [{"title": "观点清楚", "explanation": "开头直接说明了自己的看法。", "quotes": [final_quote]}],
                "next_step": {"dimension": "perspective", "suggestion": "下一次可以想一想持不同看法的人会担心什么，并作出回应。"},
                "dimensions": [
                    {"dimension": "idea", "status": "clear", "observation": "主要观点清楚。", "quotes": [final_quote]},
                    {"dimension": "material", "status": "developing", "observation": "已经开始使用具体内容。", "quotes": [final_quote]},
                    {"dimension": "structure", "status": "developing", "observation": "观点和理由有基本顺序。", "quotes": [final_quote]},
                    {"dimension": "language", "status": "clear", "observation": "语句能够传达主要意思。", "quotes": [final_quote]},
                    {"dimension": "perspective", "status": "not_yet_visible", "observation": "还可以加入不同看法。", "quotes": []},
                ],
                "revision_evidence": [{"change": "终稿在原观点基础上补充了表达。", "initial_quote": initial_quote, "final_quote": final_quote}],
            }
        raise AiProviderError(f"Unsupported operation: {operation}")


class DeepSeekAiProvider:
    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: float = 45.0):
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required when AI_PROVIDER=deepseek")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(name="deepseek", model=self.model)

    def invoke(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        operation_specs = {
            "INITIAL_ANALYSIS": ("initial-analysis-v2.md", InitialAnalysisV2),
            "COACHING_QUESTION": ("coaching-question-v1.md", CoachingQuestionV1),
            "FINAL_EVALUATION": ("final-evaluation-v1.md", FinalEvaluationV1),
        }
        if operation not in operation_specs:
            raise AiProviderError(f"Unsupported operation: {operation}")
        prompt_file, schema_model = operation_specs[operation]
        prompt_path = Path(__file__).parent / "prompts" / prompt_file
        system_prompt = prompt_path.read_text(encoding="utf-8")
        system_prompt += "\n\nJSON Schema:\n" + json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                response_body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            if exc.code == 429 or exc.code >= 500:
                raise AiProviderTransientError(f"DeepSeek returned HTTP {exc.code}") from exc
            raise AiProviderError(f"DeepSeek returned HTTP {exc.code}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise AiProviderTransientError("DeepSeek request failed") from exc
        try:
            return json.loads(response_body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AiProviderError("DeepSeek returned an invalid response envelope") from exc


def build_ai_provider(
    provider_name: str,
    deepseek_api_key: str = "",
    deepseek_base_url: str = "https://api.deepseek.com",
    deepseek_model: str = "deepseek-chat",
) -> AiProvider:
    if provider_name == "deepseek":
        return DeepSeekAiProvider(deepseek_api_key, deepseek_base_url, deepseek_model)
    raise ValueError(f"Unsupported AI provider: {provider_name}")
