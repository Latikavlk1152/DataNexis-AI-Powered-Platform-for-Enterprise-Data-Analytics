from src.agent.sql_guardrails import is_safe_read_only_sql


def test_allows_select_query() -> None:
    is_valid, _ = is_safe_read_only_sql("SELECT region, SUM(revenue) FROM gold.sales GROUP BY 1;")
    assert is_valid is True


def test_blocks_destructive_query() -> None:
    is_valid, reason = is_safe_read_only_sql("DROP TABLE gold.sales;")
    assert is_valid is False
    assert "Only SELECT" in reason
