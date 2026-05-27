"""
agent/planner.py — the agent loop: decide → tool → LLM → respond
"""
import json
from services.ollama import chat as ollama_chat
from config import SYSTEM_PROMPT, MAX_TOOL_ROUNDS


# ── tool definitions the LLM sees ────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "list_files",
        "description": "List files and directories at a given path.",
        "params": {"path": "Absolute path to list"},
    },
    {
        "name": "read_file",
        "description": "Read the contents of a text file.",
        "params": {"path": "Absolute file path"},
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates or overwrites).",
        "params": {"path": "Absolute file path", "content": "Text to write"},
    },
    {
        "name": "run_python",
        "description": "Execute Python code and return stdout/stderr.",
        "params": {"code": "Python code string to execute"},
    },
    {
        "name": "search_web",
        "description": "Search the web with a query (requires Playwright).",
        "params": {"query": "Search query string"},
    },
    {
        "name": "save_note",
        "description": "Save a note with a title, content, and optional tags.",
        "params": {"title": "Note title", "content": "Note content", "tags": "Optional comma-separated tags"},
    },
    {
        "name": "search_notes",
        "description": "Search saved notes by keyword.",
        "params": {"query": "Search query"},
    },
]

TOOL_PROMPT = (
    "\n\nYou have access to the following tools. "
    "To use one, respond with a JSON block exactly like this:\n"
    "```tool\n"
    '{"tool": "<tool_name>", "params": {"<param>": "<value>"}}\n'
    "```\n\n"
    "Available tools:\n"
    + "\n".join(
        f"- **{t['name']}**: {t['description']}  params: {t['params']}"
        for t in TOOL_DEFINITIONS
    )
    + "\n\nIf the task does not require any tool, just respond normally."
)


def _parse_tool_call(text: str) -> dict | None:
    """Try to extract a tool-call JSON block from the LLM response."""
    marker = "```tool"
    start = text.find(marker)
    if start == -1:
        return None
    start = text.index("\n", start) + 1
    end = text.find("```", start)
    if end == -1:
        end = len(text)
    try:
        data = json.loads(text[start:end].strip())
        if "tool" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


def run_agent(
    messages: list[dict],
    model: str,
    tool_executor: callable,   # function(tool_name, params) -> str
    max_rounds: int = None,
) -> str:
    """
    Agent loop:
      1. Build prompt with tool list
      2. Call LLM
      3. If LLM wants a tool → execute → feed result back → goto 2
      4. Otherwise return the final reply
    """
    max_rounds = max_rounds or MAX_TOOL_ROUNDS

    system_msg = {"role": "system", "content": SYSTEM_PROMPT + TOOL_PROMPT}
    full_messages = [system_msg] + messages

    for _ in range(max_rounds):
        reply = ollama_chat(model, full_messages)

        tool_call = _parse_tool_call(reply)
        if tool_call is None:
            # No tool call — final answer
            return reply

        # Execute tool
        tool_name = tool_call["tool"]
        params = tool_call.get("params", {})
        try:
            result = tool_executor(tool_name, params)
        except Exception as e:
            result = f"Tool error: {e}"

        # Feed result back to LLM
        full_messages.append({"role": "assistant", "content": reply})
        full_messages.append({
            "role": "user",
            "content": f"Tool `{tool_name}` returned:\n```\n{result}\n```\nNow continue your response.",
        })

    return reply  # fallback after max rounds
