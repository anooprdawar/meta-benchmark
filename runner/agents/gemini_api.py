"""
Google Gemini API agent — calls Gemini and parses file output.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from runner.agents.claude_code import AgentResult
from runner.agents.anthropic_api import SYSTEM_PROMPT, _parse_and_write_files

# Cost per million tokens (USD)
_MODEL_COSTS = {
    "gemini-2.5-pro":         {"input": 1.25,  "output": 10.0},
    "gemini-2.5-flash":       {"input": 0.075, "output": 0.30},
    "gemini-2.5-flash-8b":    {"input": 0.0375, "output": 0.15},
    "gemini-2.0-flash":       {"input": 0.10,  "output": 0.40},
    "gemini-2.0-pro":         {"input": 1.25,  "output": 5.0},
}
_DEFAULT_COST = {"input": 1.25, "output": 10.0}


class GeminiAPIAgent:
    """Calls the Gemini API and writes files to workspace."""

    def __init__(self, model: str, harness_path: Path) -> None:
        self.model = model
        self.harness_path = Path(harness_path)

    def run(self, workspace_path: Path) -> AgentResult:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")

        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        prompt_text = (self.harness_path / "prompt.md").read_text(encoding="utf-8")
        (workspace_path / "PROMPT.md").write_text(prompt_text, encoding="utf-8")

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        client = genai.Client(api_key=api_key)

        # Strip the "models/" prefix if present — the API accepts both
        model_id = self.model.replace("models/", "")

        full_prompt = SYSTEM_PROMPT + "\n\n---\n\n" + prompt_text

        print(f"  Calling {model_id} via Gemini API...")
        start = time.monotonic()

        response = client.models.generate_content(
            model=model_id,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=65536,
                temperature=0.2,
            ),
        )

        elapsed = time.monotonic() - start
        print(f"  API call complete in {elapsed:.1f}s")

        raw_text = response.text or ""
        tokens_input = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        tokens_output = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        costs = _MODEL_COSTS.get(model_id, _DEFAULT_COST)
        cost = (tokens_input / 1_000_000 * costs["input"]
                + tokens_output / 1_000_000 * costs["output"])

        files_written = _parse_and_write_files(raw_text, workspace_path)
        print(f"  Files written: {len(files_written)}")
        for f in files_written[:10]:
            print(f"    {f}")
        if len(files_written) > 10:
            print(f"    ... and {len(files_written) - 10} more")

        (workspace_path / "_raw_response.txt").write_text(raw_text, encoding="utf-8")

        return AgentResult(
            output=raw_text,
            exit_code=0 if files_written else 1,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_estimate_usd=round(cost, 4),
            raw_response=raw_text,
        )
