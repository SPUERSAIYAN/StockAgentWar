from __future__ import annotations


def strip_a_share_exchange(symbol: str) -> str:
    normalized = symbol.strip()
    lowered = normalized.lower()
    for prefix in ("sh", "sz", "bj"):
        if lowered.startswith(prefix) and len(normalized) == 8:
            return normalized[2:]
    if "." in normalized:
        code, suffix = normalized.split(".", 1)
        if suffix.lower() in {"sh", "sz", "bj"}:
            return code
    return normalized


def normalize_tencent_a_share_symbol(symbol: str) -> str:
    normalized = symbol.strip()
    lowered = normalized.lower()

    if lowered.startswith(("sh", "sz", "bj")) and len(normalized) == 8:
        return lowered

    if "." in normalized:
        code, suffix = normalized.split(".", 1)
        suffix = suffix.lower()
        if suffix in {"sh", "sz", "bj"}:
            return f"{suffix}{code}"

    code = strip_a_share_exchange(normalized)
    if len(code) != 6 or not code.isdigit():
        return normalized

    if code.startswith(("6", "5", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sz{code}"
