"""
Direct OpenAI API agent — calls the OpenAI Chat Completions API and parses file output.

Supports GPT-5.x and Codex models. Uses streaming for long outputs.
API key read from OPENAI_META_BENCHMARK_KEY environment variable.
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


class OpenAIAPIAgent:
    """Calls the OpenAI Chat Completions API and writes files to workspace."""

    def __init__(self, model: str, harness_path: Path) -> None:
        self.model = model
        self.harness_path = Path(harness_path)

    def extend(self, workspace_path: Path, extension_prompt: str) -> AgentResult:
        """Send a second API call with current code + extension prompt, overwrite files."""
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai SDK not installed. Run: pip install openai")

        workspace_path = Path(workspace_path)

        api_key = os.environ.get("OPENAI_META_BENCHMARK_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_META_BENCHMARK_KEY not set")

        client = openai.OpenAI(api_key=api_key)

        current_code = _read_workspace_code(workspace_path)
        user_prompt = f"{extension_prompt}\n\n## Your current implementation\n\n{current_code}"

        print(f"  Running extension round (second prompt)...")
        print(f"  Calling {self.model} via OpenAI API (streaming)...")
        start = time.monotonic()

        raw_text = ""
        tokens_input = 0
        tokens_output = 0

        if "codex" in self.model.lower():
            response = client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=user_prompt,
                max_output_tokens=32768,
            )
            raw_text = response.output_text
            if hasattr(response, "usage") and response.usage:
                tokens_input = response.usage.input_tokens
                tokens_output = response.usage.output_tokens
        else:
            stream = client.chat.completions.create(
                model=self.model,
                max_completion_tokens=32768,
                stream=True,
                stream_options={"include_usage": True},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    raw_text += chunk.choices[0].delta.content
                if chunk.usage:
                    tokens_input = chunk.usage.prompt_tokens
                    tokens_output = chunk.usage.completion_tokens

        elapsed = time.monotonic() - start
        print(f"  Extension API call complete in {elapsed:.1f}s")

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
            import openai
        except ImportError:
            raise RuntimeError("openai SDK not installed. Run: pip install openai")

        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        prompt_text = (self.harness_path / "prompt.md").read_text(encoding="utf-8")
        (workspace_path / "PROMPT.md").write_text(prompt_text, encoding="utf-8")

        api_key = os.environ.get("OPENAI_META_BENCHMARK_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_META_BENCHMARK_KEY not set")

        client = openai.OpenAI(api_key=api_key)

        print(f"  Calling {self.model} via OpenAI API (streaming)...")
        start = time.monotonic()

        raw_text = ""
        tokens_input = 0
        tokens_output = 0

        if "codex" in self.model.lower():
            # Codex models use the Responses API
            response = client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=prompt_text,
                max_output_tokens=32768,
            )
            raw_text = response.output_text
            if hasattr(response, "usage") and response.usage:
                tokens_input = response.usage.input_tokens
                tokens_output = response.usage.output_tokens
        else:
            stream = client.chat.completions.create(
                model=self.model,
                max_completion_tokens=32768,
                stream=True,
                stream_options={"include_usage": True},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_text},
                ],
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    raw_text += chunk.choices[0].delta.content
                if chunk.usage:
                    tokens_input = chunk.usage.prompt_tokens
                    tokens_output = chunk.usage.completion_tokens

        elapsed = time.monotonic() - start
        print(f"  API call complete in {elapsed:.1f}s")

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
