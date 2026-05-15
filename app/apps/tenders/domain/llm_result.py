"""
Normalized result object returned by every LLM provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResult:
    raw_text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    cost_usd: float = field(init=False)

    # Cost per 1K tokens (approximate, update as pricing changes)
    COST_TABLE = {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-5.2": {"input": 0.002, "output": 0.008},
    }

    def __post_init__(self):
        rates = self.COST_TABLE.get(self.model, {"input": 0.002, "output": 0.008})
        self.cost_usd = (self.input_tokens / 1000 * rates["input"]) + (
            self.output_tokens / 1000 * rates["output"]
        )

    @classmethod
    def failure(cls, provider: str, model: str, error: str) -> "LLMResult":
        return cls(
            raw_text="",
            provider=provider,
            model=model,
            success=False,
            error=error,
        )
