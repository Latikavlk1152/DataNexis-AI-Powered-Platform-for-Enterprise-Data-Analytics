"""Deterministic SQL Guardrails ensuring read-only and safe query execution."""

FORBIDDEN_KEYWORDS = {
    "DROP",
    "DELETE",
    "TRUNCATE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "GRANT",
    "REVOKE",
}


def is_safe_read_only_sql(query: str) -> tuple[bool, str]:
    """Validate that a generated SQL query is strictly read-only."""
    normalized = query.strip().upper()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return False, "Only SELECT or CTE (WITH) queries are permitted."

    tokens = set(normalized.replace(";", " ").split())
    violations = tokens.intersection(FORBIDDEN_KEYWORDS)
    if violations:
        return False, f"Forbidden SQL keywords detected: {', '.join(sorted(violations))}"

    return True, "Query passed read-only validation."
