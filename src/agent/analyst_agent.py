"""Autonomous Analyst: Low-Latency Semantic Context Engineering + Local LLM Text-to-SQL Agent."""

import json
import re
import ollama
import pandas as pd
from sqlalchemy import create_engine, text
from config.settings import settings
from src.agent.sql_guardrails import is_safe_read_only_sql
from src.fabric.schema_crawler import PostgresSchemaCrawler


class AutonomousAnalyst:
    """Translates natural language business questions into governed PostgreSQL queries."""

    def __init__(self) -> None:
        self.engine = create_engine(settings.database_url)
        self.crawler = PostgresSchemaCrawler(settings.database_url)
        self._cached_context: str | None = None

    def build_semantic_context(self, force_refresh: bool = False) -> str:
        """Cache structured schema, foreign-key topology, and glossary terms in memory."""
        if self._cached_context and not force_refresh:
            return self._cached_context

        catalog = self.crawler.get_catalog_context()
        if not catalog:
            self.crawler.sync_semantic_catalog(use_llm=False)
            catalog = self.crawler.get_catalog_context()

        grouped: dict[str, list[str]] = {}
        for row in catalog:
            tbl = f"{row['schema_name']}.{row['table_name']}"
            fk_note = f" [FK->{row['foreign_key_ref']}]" if row["foreign_key_ref"] else ""
            line = f"  - {row['column_name']} ({row['data_type']}){fk_note}: {row['business_glossary_term']}"
            grouped.setdefault(tbl, []).append(line)

        self._cached_context = "\n\n".join(f"Table: {tbl}\n" + "\n".join(cols) for tbl, cols in grouped.items())
        return self._cached_context

    def generate_query_plan(self, user_question: str) -> dict:
        """Generate SQL and explainable lineage using local Ollama with persistent RAM caching."""
        semantic_context = self.build_semantic_context()

        system_prompt = f"""You are an Expert Life Sciences PostgreSQL 16 Data Architect. Use ONLY the tables and columns below.
{semantic_context}

Rules:
1. Qualify every table with its schema (e.g., gmp_manufacturing.fact_batch_records, clinical_edc.fact_patient_cohorts, clinical_edc.dim_clinical_protocols).
2. NEVER invent tables (no dim_facility_plants, no gold schema).
3. WHEN QUERYING ACROSS TABLES, ALWAYS PERFORM EXPLICIT JOINS:
   - To get trial metadata (therapeutic_area, trial_phase) with patient metrics, JOIN clinical_edc.dim_clinical_protocols ON protocol_id.
   - Example: SELECT d.therapeutic_area, SUM(f.active_enrolled_cnt) FROM clinical_edc.fact_patient_cohorts f JOIN clinical_edc.dim_clinical_protocols d ON f.protocol_id = d.protocol_id GROUP BY d.therapeutic_area
4. Ensure x_axis and y_axis match the EXACT column names or AS aliases in your SELECT clause.
5. Return ONLY valid JSON:
{{"reasoning": "1 concise sentence", "sql": "SELECT ...", "suggested_chart": "bar|line|pie|table", "x_axis": "exact_x_col", "y_axis": "exact_y_col"}}"""

        response = ollama.chat(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            format="json",
            keep_alive="10m",
            options={"temperature": 0.1, "num_predict": 800},
        )

        raw_content = response["message"]["content"].strip()
        raw_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content, flags=re.IGNORECASE).strip()

        try:
            plan = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            sql_match = re.search(r'"sql"\s*:\s*"((?:[^"\\]|\\.)*)', raw_content, re.DOTALL)
            reason_match = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)', raw_content, re.DOTALL)
            if not sql_match:
                raise ValueError(f"LLM returned unparseable output: {exc}") from exc
            plan = {
                "reasoning": reason_match.group(1) if reason_match else "Generated query from semantic catalog.",
                "sql": sql_match.group(1).replace('\\"', '"').replace("\\n", " "),
                "suggested_chart": "bar",
                "x_axis": "",
                "y_axis": "",
            }

        sql_clean = re.sub(r"^```sql\s*|\s*```$", "", plan.get("sql", "").strip(), flags=re.IGNORECASE).strip()
        plan["sql"] = sql_clean
        return plan

    def execute_governed_query(self, sql_query: str) -> pd.DataFrame:
        """Validate SQL against deterministic guardrails and execute in read-only mode."""
        is_safe, reason = is_safe_read_only_sql(sql_query)
        if not is_safe:
            raise ValueError(f"SQL Guardrail Blocked Execution: {reason}")

        with self.engine.connect() as conn:
            return pd.read_sql_query(text(sql_query), conn)

    def synthesize_executive_insight(self, user_question: str, df: pd.DataFrame, summary_stats: dict) -> str:
        """Fast deterministic statistical insight generator (zero extra LLM latency)."""
        if df.empty:
            return "The query executed cleanly but returned zero matching records."

        bullets = [f"- **Dataset Coverage:** Retrieved **{len(df)}** aggregated records across **{len(df.columns)}** dimensions/metrics."]
        for col, metrics in summary_stats.get("numeric_metrics", {}).items():
            bullets.append(
                f"- **{col}:** Total = **{metrics['sum']:,.2f}** | Mean = **{metrics['mean']:,.2f}** "
                f"(Range: {metrics['min']:,.2f} to {metrics['max']:,.2f})."
            )
        return "\n".join(bullets)