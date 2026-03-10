from runner.agents.claude_code import ClaudeCodeAgent
from runner.agents.manual import ManualAgent
from runner.agents.anthropic_api import AnthropicAPIAgent
from runner.agents.gemini_api import GeminiAPIAgent
from pathlib import Path

AGENTS: dict[str, type] = {
    "claude-code": ClaudeCodeAgent,
    "claude-api": AnthropicAPIAgent,
    "gemini-api": GeminiAPIAgent,
    "manual": ManualAgent,
}


def get_agent(name: str, model: str, harness_path: Path):
    """Factory: return an agent instance by name."""
    if name not in AGENTS:
        raise ValueError(f"Unknown agent '{name}'. Available: {list(AGENTS)}")
    return AGENTS[name](model=model, harness_path=harness_path)
