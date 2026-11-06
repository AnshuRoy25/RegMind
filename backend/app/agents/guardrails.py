"""
Safety filters applied before any code, config or log text is sent to the LLM.

mask_secrets() replaces API keys, passwords, tokens, private keys, emails and
IP addresses with placeholders, so the auditor can review a PR diff without
leaking anything sensitive to the model provider.
"""

import re

_PATTERNS = [
    # private key blocks
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[MASKED_PRIVATE_KEY]"),
    # well known token formats
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[MASKED_AWS_KEY]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "[MASKED_GITHUB_TOKEN]"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{30,}"), "[MASKED_GOOGLE_KEY]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "[MASKED_SLACK_TOKEN]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]{16,}=*"), "Bearer [MASKED_TOKEN]"),
    # key = value style secrets (password: x, api_key="x", SECRET=x ...)
    (re.compile(r"(?i)\b([A-Za-z_]*(?:password|passwd|secret|api_key|apikey|token|access_key)[A-Za-z_]*)\s*([:=])\s*[\"']?[^\s\"',]+[\"']?"),
     r"\1\2 [MASKED]"),
    # personal data
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[MASKED_EMAIL]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[MASKED_IP]"),
]


def mask_secrets(text: str) -> tuple[str, int]:
    """Return (masked_text, number_of_replacements)."""
    total = 0
    for pattern, replacement in _PATTERNS:
        text, count = pattern.subn(replacement, text)
        total += count
    return text, total
