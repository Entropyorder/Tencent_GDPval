from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
PROMPT_DIR = PROJECT_ROOT / "prompts"
DEFAULT_INPUT_DIR = DATA_DIR / "source_documents"
DEFAULT_COLLECTOR_JSON = DATA_DIR / "collector_metadata.json"


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    max_input_chars: int
    max_output_tokens: int
    query_max_output_tokens: int
    keyword_max_output_tokens: int
    temperature: float
    query_temperature: float
    keyword_temperature: float
    prompt_path: Path
    prompt_version: str = "document_profile_v1"

    @classmethod
    def from_env(cls):
        load_dotenv(PROJECT_ROOT / ".env")
        return cls(
            api_key=os.environ.get("INFERERA_API_KEY", "").strip(),
            base_url=os.environ.get(
                "INFERERA_BASE_URL", "https://api.inferera.com/v1"
            ).rstrip("/"),
            model=os.environ.get("INFERERA_MODEL", "deepseek-v4-flash").strip(),
            max_input_chars=int(os.environ.get("LLM_MAX_INPUT_CHARS", "30000")),
            max_output_tokens=int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "4096")),
            query_max_output_tokens=int(
                os.environ.get("QUERY_MAX_OUTPUT_TOKENS", "2048")
            ),
            keyword_max_output_tokens=int(
                os.environ.get("KEYWORD_MAX_OUTPUT_TOKENS", "2048")
            ),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.1")),
            query_temperature=float(
                os.environ.get("QUERY_LLM_TEMPERATURE", "0.7")
            ),
            keyword_temperature=float(
                os.environ.get("KEYWORD_LLM_TEMPERATURE", "0.1")
            ),
            prompt_path=PROMPT_DIR / "文档编目.md",
        )

    def validate_api(self):
        if not self.api_key:
            raise ValueError("INFERERA_API_KEY is missing; configure it in .env")
        if not self.model:
            raise ValueError("INFERERA_MODEL is missing")
