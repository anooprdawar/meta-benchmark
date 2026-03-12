"""
Direct OpenAI API agent — calls the OpenAI Responses API and parses file output.

Supports GPT-5.x, Codex, o3, and o4-mini models.
API key read from OPENAI_META_BENCHMARK_KEY environment variable (falls back to OPENAI_API_KEY).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from runner.agents.anthropic_api import AgentResult, _parse_and_write_files, _read_workspace_code

# Cost per million tokens (USD) by model
_MODEL_COSTS = {
    "gpt-5.4":              {"input": 2.50,  "output": 15.0},
    "gpt-5.4-pro":          {"input": 2.50,  "output": 15.0},
    "gpt-5.4-2026-03-05":   {"input": 2.50,  "output": 15.0},
    "gpt-5.3-codex":        {"input": 1.75,  "output": 14.0},
    "gpt-5.3-codex-spark":  {"input": 1.75,  "output": 14.0},
    "gpt-5.2-codex":        {"input": 1.75,  "output": 14.0},
    "gpt-5.3":              {"input": 2.50,  "output": 15.0},
    "gpt-5.2":              {"input": 2.50,  "output": 15.0},
    "gpt-5.1":              {"input": 2.50,  "output": 15.0},
    "gpt-5":                {"input": 2.50,  "output": 15.0},
    "gpt-4.1":              {"input": 2.00,  "output": 8.0},
    "gpt-4o":               {"input": 2.50,  "output": 10.0},
    "o3":                   {"input": 10.0,  "output": 40.0},
    "o4-mini":              {"input": 1.10,  "output": 4.40},
}
_DEFAULT_COST = {"input": 2.50, "output": 15.0}

SYSTEM_PROMPT = """\
You are an expert software engineer. You will receive a specification for a software \
project and must implement it completely.

Output your implementation as a series of files using EXACTLY this format:

=== FILE: path/to/file.py ===
<file contents here>
=== END FILE ===

Rules:
- Output every file needed for a complete, working implementation
- Prefer a single self-contained file (e.g., mini_git.py) over a package — it's easier to test
- Do NOT include test files — tests are provided externally
- Include a README.md and requirements.txt
- Use relative paths (e.g., mini_git.py, not /absolute/path)
- Do not include any explanation outside the FILE blocks — code only
- Make the implementation genuinely work: it will be tested against a rigorous test suite
"""


def _get_client():
    """Create an OpenAI client with the correct API key."""
    import openai
    api_key = os.environ.get("OPENAI_META_BENCHMARK_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_META_BENCHMARK_KEY (or OPENAI_API_KEY) not set")
    return openai.OpenAI(api_key=api_key)


def _call_responses_api(client, model: str, instructions: str, user_input: str, label: str = "") -> tuple[str, int, int, float]:
    """Call the OpenAI Responses API. Returns (text, tokens_in, tokens_out, elapsed)."""
    print(f"  Calling {model} via OpenAI Responses API{' (' + label + ')' if label else ''}...")
    start = time.monotonic()

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=user_input,
        max_output_tokens=32768,
    )

    elapsed = time.monotonic() - start
    print(f"  API call complete in {elapsed:.1f}s")

    raw_text = response.output_text
    tokens_input = 0
    tokens_output = 0
    if hasattr(response, "usage") and response.usage:
        tokens_input = response.usage.input_tokens
        tokens_output = response.usage.output_tokens

    return raw_text, tokens_input, tokens_output, elapsed


class OpenAIAPIAgent:
    """Calls the OpenAI Responses API and writes files to workspace."""

    def __init__(self, model: str, harness_path: Path) -> None:
        self.model = model
        self.harness_path = Path(harness_path)

    def extend(self, workspace_path: Path, extension_prompt: str) -> AgentResult:
        """Send a second API call with current code + extension prompt, overwrite files."""
        try:
            import openai  # noqa: F401
        except ImportError:
            raise RuntimeError("openai SDK not installed. Run: pip install openai>=2.0")

        workspace_path = Path(workspace_path)
        client = _get_client()

        current_code = _read_workspace_code(workspace_path)
        user_prompt = f"{extension_prompt}\n\n## Your current implementation\n\n{current_code}"

        raw_text, tokens_input, tokens_output, _ = _call_responses_api(
            client, self.model, SYSTEM_PROMPT, user_prompt, label="extension"
        )

        costs = _MODEL_COSTS.get(self.model, _DEFAULT_COST)
        cost = (tokens_input / 1_000_000 * costs["input"]
                + tokens_output / 1_000_000 * costs["output"])

        files_written = _parse_and_write_files(raw_text, workspace_path)
        print(f"  Files written (extension): {len(files_written)}")
        for f in files_written[:10]:
            print(f"    {f}")
        if len(files_written) > 10:
            print(f"    ... and {len(files_written) - 10} more")

        (workspace_path / "_raw_extension_response.txt").write_text(raw_text, encoding="utf-8")

        return AgentResult(
            output=raw_text,
            exit_code=0 if files_written else 1,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_estimate_usd=round(cost, 4),
            raw_response=raw_text,
        )

    def run(self, workspace_path: Path) -> AgentResult:
        try:
            import openai  # noqa: F401
        except ImportError:
            raise RuntimeError("openai SDK not installed. Run: pip install openai>=2.0")

        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        prompt_text = (self.harness_path / "prompt.md").read_text(encoding="utf-8")
        (workspace_path / "PROMPT.md").write_text(prompt_text, encoding="utf-8")

        client = _get_client()

        raw_text, tokens_input, tokens_output, _ = _call_responses_api(
            client, self.model, SYSTEM_PROMPT, prompt_text
        )

        costs = _MODEL_COSTS.get(self.model, _DEFAULT_COST)
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
