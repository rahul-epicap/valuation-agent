"""Sandbox validation for agent-generated train.py code.

Validates that generated code only uses allowed imports and doesn't
access filesystem or network resources.
"""

from __future__ import annotations

import ast
import re

ALLOWED_MODULES = {
    "__future__",
    "numpy",
    "np",
    "scipy",
    "sklearn",
    "statsmodels",
    "math",
    "functools",
    "itertools",
    "collections",
    "dataclasses",
    "typing",
    "research",
    "research.prepare",
}

BLOCKED_PATTERNS = [
    r"\bopen\s*\(",
    r"\bos\.",
    r"\bsubprocess\.",
    r"\bsocket\.",
    r"\brequests\.",
    r"\bhttpx\.",
    r"\burllib\.",
    r"\bpathlib\.",
    r"\b__import__\s*\(",
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bcompile\s*\(",
    r"\bglobals\s*\(",
    r"\bimportlib\.",
]


def validate_train_py(code: str) -> list[str]:
    """Validate generated train.py code for safety.

    Returns list of error messages. Empty list means valid.
    """
    errors: list[str] = []

    # Check for blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            errors.append(f"Blocked pattern found: {pattern}")

    # Parse AST to check imports
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Syntax error: {e}")
        return errors

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    errors.append(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in ALLOWED_MODULES:
                    errors.append(f"Disallowed import: {node.module}")

    # Check required functions exist
    func_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    required = {"build_features", "fit_model", "predict", "get_model_description"}
    missing = required - func_names
    if missing:
        errors.append(f"Missing required functions: {missing}")

    return errors
