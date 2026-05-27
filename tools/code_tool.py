"""
maisuclaw v0.3.0 — Tool: Code Execution
Execute Python code snippets safely.
"""

import subprocess
import textwrap


def execute(code: str, timeout: int = 30) -> str:
    """Execute Python code and return output."""
    if not code.strip():
        return "Error: No code provided"

    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="."
        )
        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        if result.returncode != 0:
            output.append(f"Exit code: {result.returncode}")

        return "\n".join(output) if output else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: Code execution timed out after {timeout}s"
    except Exception as e:
        return f"Error executing code: {e}"
