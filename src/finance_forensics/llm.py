import json
import re
import time

from openai import BadRequestError, OpenAI

from .models import LLMProfile
from .naming import normalize_summary


def extract_json_object(text):
    text = (text or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model response did not contain a JSON object")
    return json.loads(text[start : end + 1])


def normalize_model_payload(payload):
    allowed = set(LLMProfile.model_fields)
    normalized = {key: value for key, value in payload.items() if key in allowed}
    if "summary" in normalized:
        normalized["summary"] = normalize_summary(str(normalized["summary"]))
    for key, limit in (("keywords", 8), ("review_reasons", 8)):
        value = normalized.get(key)
        if value is None:
            normalized[key] = []
        elif isinstance(value, list):
            normalized[key] = [str(item).strip() for item in value if str(item).strip()][
                :limit
            ]
    return normalized


class InfereraClient:
    def __init__(self, settings):
        settings.validate_api()
        self.settings = settings
        self.system_prompt = settings.prompt_path.read_text(encoding="utf-8")
        self.user_prompt_template = (
            settings.prompt_path.parent / "文档编目输入模板.md"
        ).read_text(encoding="utf-8")
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=180,
            max_retries=0,
        )

    def build_user_prompt(self, context, document_content):
        schema = LLMProfile.model_json_schema()
        return self.user_prompt_template.format(
            schema=json.dumps(schema, ensure_ascii=False),
            context=json.dumps(context, ensure_ascii=False, indent=2),
            document_content=document_content[: self.settings.max_input_chars],
        )

    def analyze(self, context, document_content, retries=3):
        user_prompt = self.build_user_prompt(context, document_content)
        use_response_format = True
        last_error = None
        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                kwargs = {
                    "model": self.settings.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.settings.temperature,
                    "max_tokens": self.settings.max_output_tokens,
                }
                if use_response_format:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(**kwargs)
                if response.choices[0].finish_reason == "length":
                    raise ValueError(
                        "model response was truncated; increase LLM_MAX_OUTPUT_TOKENS"
                    )
                content = response.choices[0].message.content
                payload = normalize_model_payload(extract_json_object(content))
                return LLMProfile.model_validate(payload)
            except BadRequestError as exc:
                if use_response_format:
                    use_response_format = False
                    attempt -= 1
                    continue
                last_error = exc
            except Exception as exc:
                last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"LLM request failed after {retries} attempts: {last_error}")
