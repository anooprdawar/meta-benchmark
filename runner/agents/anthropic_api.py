"""
Direct Anthropic API agent — calls the Claude API and parses file output.

Unlike the Claude Code subprocess agent, this sends the prompt directly to the
Anthropic messages API and parses structured file output from the response.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from runner.agents.claude_code import AgentResult

# Cost per million tokens (USD) by model
_MODEL_COSTS = {
    "claude-opus-4-6":    {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":  {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5":   {"input": 0.80,  "output": 4.0},
}
_DEFAULT_COST = {"input": 15.0, "output": 75.0}

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


class AnthropicAPIAgent:
    """Calls the Anthropic Messages API directly and writes files to workspace."""

    def __init__(self, model: str, harness_path: Path) -> None:
        self.model = model
        self.harness_path = Path(harness_path)

    def extend(self, workspace_path: Path, extension_prompt: str) -> AgentResult:
        """Send a second API call with current code + extension prompt, overwrite files."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic")

        workspace_path = Path(workspace_path)

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)

        current_code = _read_workspace_code(workspace_path)
        prompt = f"{extension_prompt}\n\n## Your current implementation\n\n{current_code}"

        print(f"  Running extension round (second prompt)...")
        print(f"  Calling {self.model} via Anthropic API (streaming)...")
        start = time.monotonic()

        raw_text = ""
        tokens_input = 0
        tokens_output = 0
        with client.messages.stream(
            model=self.model,
            max_tokens=32768,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                raw_text += text
            final = stream.get_final_message()
            tokens_input = final.usage.input_tokens
            tokens_output = final.usage.output_tokens

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
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic SDK not installed. Run: pip install anthropic")

        workspace_path = Path(workspace_path)
        workspace_path.mkdir(parents=True, exist_ok=True)

        prompt_text = (self.harness_path / "prompt.md").read_text(encoding="utf-8")
        (workspace_path / "PROMPT.md").write_text(prompt_text, encoding="utf-8")

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)

        print(f"  Calling {self.model} via Anthropic API (streaming)...")
        start = time.monotonic()

        raw_text = ""
        tokens_input = 0
        tokens_output = 0
        with client.messages.stream(
            model=self.model,
            max_tokens=32768,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_text}],
        ) as stream:
            for text in stream.text_stream:
                raw_text += text
            final = stream.get_final_message()
            tokens_input = final.usage.input_tokens
            tokens_output = final.usage.output_tokens

        elapsed = time.monotonic() - start
        print(f"  API call complete in {elapsed:.1f}s")

        costs = _MODEL_COSTS.get(self.model, _DEFAULT_COST)
        cost = (tokens_input / 1_000_000 * costs["input"]
                + tokens_output / 1_000_000 * costs["output"])

        # Parse and write files
        files_written = _parse_and_write_files(raw_text, workspace_path)
        print(f"  Files written: {len(files_written)}")
        for f in files_written[:10]:
            print(f"    {f}")
        if len(files_written) > 10:
            print(f"    ... and {len(files_written) - 10} more")

        # Save raw response for inspection
        (workspace_path / "_raw_response.txt").write_text(raw_text, encoding="utf-8")

        return AgentResult(
            output=raw_text,
            exit_code=0 if files_written else 1,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_estimate_usd=round(cost, 4),
            raw_response=raw_text,
        )


def _parse_and_write_files(text: str, workspace: Path) -> list[str]:
    """
    Parse === FILE: path === ... === END FILE === blocks and write to disk.
    Falls back to extracting fenced code blocks with filenames if no FILE blocks found.
    """
    written = []

    # Primary format: === FILE: path ===
    pattern = re.compile(
        r"=== FILE: (.+?) ===\n(.*?)=== END FILE ===",
        re.DOTALL,
    )
    matches = list(pattern.finditer(text))

    if matches:
        for m in matches:
            rel_path = m.group(1).strip()
            content = m.group(2)
            _write_file(workspace, rel_path, content)
            written.append(rel_path)
        return written

    # Fallback: fenced code blocks with filename hints
    # Pattern: ```python\n# filename: foo.py\n...\n```  or  ```python foo.py\n...\n```
    fence_pattern = re.compile(
        r"```(?:\w+)?\s*(?:#\s*(?:filename:|file:)\s*)?([^\n`]+\.py)\n(.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    for m in fence_pattern.finditer(text):
        rel_path = m.group(1).strip()
        content = m.group(2)
        if "/" not in rel_path and len(rel_path) < 60:  # Looks like a filename
            _write_file(workspace, rel_path, content)
            written.append(rel_path)

    # Last resort: if still nothing, look for any ```python block and name it mini_git.py
    if not written:
        code_blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
        if code_blocks:
            _write_file(workspace, "mini_git.py", code_blocks[0])
            written.append("mini_git.py")

    return written


def _write_file(workspace: Path, rel_path: str, content: str) -> None:
    """Write content to workspace/rel_path, creating parent dirs as needed."""
    # Security: prevent path traversal
    target = (workspace / rel_path).resolve()
    if not str(target).startswith(str(workspace.resolve())):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _read_workspace_code(workspace: Path, max_chars: int = 40_000) -> str:
    """
    Read source files from workspace (non-test .py files, excluding mutants/).
    Returns content formatted as === FILE: ... === blocks.
    """
    workspace = Path(workspace)
    parts: list[str] = []
    total_chars = 0

    for path in sorted(workspace.rglob("*.py")):
        # Skip test files, mutant directories, and hidden/internal files
        rel = path.relative_to(workspace)
        parts_rel = rel.parts
        if any(p == "mutants" for p in parts_rel):
            continue
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            continue
        if path.name.startswith("_"):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        block = f"=== FILE: {rel.as_posix()} ===\n{content}\n=== END FILE ==="
        if total_chars + len(block) > max_chars:
            break
        parts.append(block)
        total_chars += len(block)

    return "\n\n".join(parts)
