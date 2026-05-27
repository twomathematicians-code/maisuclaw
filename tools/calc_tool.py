"""
maisuclaw v0.3.0 — Tool: Calculator
Safe math evaluation.
"""

import re


def execute(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    if not expression:
        return "Error: No expression provided"

    # Clean the expression
    expr = expression.strip()

    # Only allow safe characters
    allowed = re.compile(r'^[\d\s\+\-\*\/\%\(\)\.\,\^]+$')
    if not allowed.match(expr):
        return "Error: Expression contains invalid characters. Only numbers and math operators are allowed."

    try:
        # Replace ^ with ** for exponentiation
        expr = expr.replace('^', '**')
        # Evaluate
        result = eval(expr, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error evaluating expression: {e}"
