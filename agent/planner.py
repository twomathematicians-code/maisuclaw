"""
agent/planner.py — the agent loop: decide → tool → LLM → respond
Supports both streaming and non-streaming modes.
"""
import json
from services.ollama import chat as ollama_chat, chat_stream as ollama_stream
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


def _needs_tools(message: str) -> bool:
    """Quick heuristic: does this message likely need tools?"""
    lower = message.lower()
    tool_hints = {
        "list file", "read file", "write file", "run code", "execute",
        "search", "save note", "browse", "open", "show me", "what files",
        "git status", "git log", "create file", "write a script",
        "my desktop", "my documents", "directory", "folder",
    }
    return any(hint in lower for hint in tool_hints)


def run_agent(
    messages: list[dict],
    model: str,
    tool_executor: callable,
    max_rounds: int = None,
) -> str:
    """Non-streaming agent loop."""
    max_rounds = max_rounds or MAX_TOOL_ROUNDS
    system_msg = {"role": "system", "content": SYSTEM_PROMPT + TOOL_PROMPT}
    full_messages = [system_msg] + messages

    for _ in range(max_rounds):
        reply = ollama_chat(model, full_messages)
        tool_call = _parse_tool_call(reply)
        if tool_call is None:
            return reply

        tool_name = tool_call["tool"]
        params = tool_call.get("params", {})
        try:
            result = tool_executor(tool_name, params)
        except Exception as e:
            result = f"Tool error: {e}"

        full_messages.append({"role": "assistant", "content": reply})
        full_messages.append({
            "role": "user",
            "content": f"Tool `{tool_name}` returned:\n```\n{result}\n```\nNow continue your response.",
        })

    return reply


def run_agent_stream(
    messages: list[dict],
    model: str,
    tool_executor: callable,
    max_rounds: int = None,
):
    """
    Streaming agent loop — yields dicts:
      {"type": "token", "content": "...", "model": "..."}
      {"type": "tool", "name": "...", "result": "..."}
      {"type": "done", "full_reply": "...", "model": "..."}
    """
    max_rounds = max_rounds or MAX_TOOL_ROUNDS
    system_msg = {"role": "system", "content": SYSTEM_PROMPT + TOOL_PROMPT}
    full_messages = [system_msg] + messages

    last_message = messages[-1]["content"] if messages else ""

    # Quick check: skip tools entirely for simple questions
    if not _needs_tools(last_message):
        full_reply = ""
        for chunk in ollama_stream(model, [{"role": "system", "content": SYSTEM_PROMPT}] + messages):
            full_reply += chunk["content"]
            yield {"type": "token", "content": chunk["content"], "model": chunk["model"]}
        yield {"type": "done", "full_reply": full_reply, "model": model}
        return

    # Agent loop with streaming on the FINAL round
    for round_i in range(max_rounds):
        is_final_attempt = (round_i == max_rounds - 1) or True  # always try streaming

        if is_final_attempt:
            # Stream this round
            reply = ""
            for chunk in ollama_stream(model, full_messages):
                reply += chunk["content"]
                yield {"type": "token", "content": chunk["content"], "model": chunk["model"]}
        else:
            reply = ollama_chat(model, full_messages)

        tool_call = _parse_tool_call(reply)
        if tool_call is None:
            yield {"type": "done", "full_reply": reply, "model": model}
            return

        tool_name = tool_call["tool"]
        params = tool_call.get("params", {})
        yield {"type": "tool", "name": tool_name}

        try:
            result = tool_executor(tool_name, params)
        except Exception as e:
            result = f"Tool error: {e}"

        yield {"type": "tool_result", "name": tool_name, "result": result[:500]}

        full_messages.append({"role": "assistant", "content": reply})
        full_messages.append({
            "role": "user",
            "content": f"Tool `{tool_name}` returned:\n```\n{result}\n```\nNow continue your response.",
        })

    yield {"type": "done", "full_reply": reply, "model": model}
