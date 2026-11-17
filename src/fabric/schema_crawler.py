"""PostgreSQL Metadata & Lineage Crawler + Local LLM Semantic Enricher (Life Sciences Domain)."""

import json
import ollama
from loguru import logger
from sqlalchemy import create_engine, text
from config.settings import settings


class PostgresSchemaCrawler:
    """Inspects PostgreSQL information_schema and enriches metadata using local LLM inference."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url)

    def extract_metadata(
        self,
        target_schemas: tuple[str, ...] = ("clinical_edc", "gmp_manufacturing", "supply_chain"),
    ) -> list[dict]:
        """Extract tables, columns, data types, and foreign key topology across Life Sciences domains."""
        query = text("""
            WITH fk_map AS (
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_schema || '.' || ccu.table_name || '(' || ccu.column_name || ')' AS fk_target
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
            )
            SELECT
                c.table_schema,
                c.table_name,
                c.column_name,
                c.data_type,
                (c.is_nullable = 'YES') AS is_nullable,
                fk.fk_target
            FROM information_schema.columns c
            LEFT JOIN fk_map fk
                ON c.table_schema = fk.table_schema
                AND c.table_name = fk.table_name
                AND c.column_name = fk.column_name
            WHERE c.table_schema = ANY(:schemas)
              AND c.table_name != 'semantic_catalog'
            ORDER BY c.table_schema, c.table_name, c.ordinal_position;
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(query, {"schemas": list(target_schemas)}).mappings().all()
            return [dict(r) for r in rows]

    def enrich_column_with_llm(self, col_meta: dict) -> dict:
        """Use local Ollama to infer business meaning and PII classification."""
        prompt = f"""You are a Senior Enterprise Data Architect in Life Sciences. Analyze this database column and return ONLY a valid JSON object with three keys:
- "semantic_description": concise 1-sentence business explanation of what this column represents in a clinical/biopharma context.
- "business_glossary_term": standardized 2-3 word business title (e.g., "Yield Purity Percentage").
- "pii_classification": either "PII" (patient names, personal emails) or "NON_PII".

Column Metadata:
Schema: {col_meta['table_schema']}
Table: {col_meta['table_name']}
Column: {col_meta['column_name']}
Data Type: {col_meta['data_type']}
Foreign Key: {col_meta['fk_target'] or 'None'}
"""
        try:
            response = ollama.chat(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.1},
            )
            parsed = json.loads(response["message"]["content"])
            return {
                "semantic_description": parsed.get("semantic_description", ""),
                "business_glossary_term": parsed.get("business_glossary_term", col_meta["column_name"]),
                "pii_classification": parsed.get("pii_classification", "NON_PII"),
            }
        except Exception as exc:
            logger.warning(f"LLM enrichment fallback for {col_meta['column_name']}: {exc}")
            return {
                "semantic_description": f"Attribute {col_meta['column_name']} in {col_meta['table_name']}.",
                "business_glossary_term": col_meta["column_name"].replace("_", " ").title(),
                "pii_classification": "NON_PII",
            }

    def sync_semantic_catalog(self, use_llm: bool = True) -> int:
        """Crawl database schemas and upsert enriched metadata into semantic_governance.semantic_catalog."""
        columns = self.extract_metadata()
        logger.info(f"Crawled {len(columns)} columns across target Life Sciences schemas.")

        upsert_sql = text("""
            INSERT INTO semantic_governance.semantic_catalog (
                schema_name, table_name, column_name, data_type, is_nullable,
                foreign_key_ref, semantic_description, business_glossary_term, pii_classification
            )
            VALUES (
                :table_schema, :table_name, :column_name, :data_type, :is_nullable,
                :fk_target, :semantic_description, :business_glossary_term, :pii_classification
            )
            ON CONFLICT (schema_name, table_name, column_name)
            DO UPDATE SET
                data_type = EXCLUDED.data_type,
                foreign_key_ref = EXCLUDED.foreign_key_ref,
                semantic_description = EXCLUDED.semantic_description,
                business_glossary_term = EXCLUDED.business_glossary_term,
                pii_classification = EXCLUDED.pii_classification,
                updated_at = CURRENT_TIMESTAMP;
        """)

        with self.engine.begin() as conn:
            for col in columns:
                enrichment = (
                    self.enrich_column_with_llm(col)
                    if use_llm
                    else {
                        "semantic_description": f"Attribute {col['column_name']} of {col['table_name']}",
                        "business_glossary_term": col["column_name"].replace("_", " ").title(),
                        "pii_classification": "NON_PII",
                    }
                )
                payload = {**col, **enrichment}
                conn.execute(upsert_sql, payload)

        return len(columns)

    def get_catalog_context(self) -> list[dict]:
        """Fetch the full semantic catalog from semantic_governance for RAG SQL context engineering."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM semantic_governance.semantic_catalog ORDER BY schema_name, table_name, catalog_id;")
            ).mappings().all()
            return [dict(r) for r in rows]


if __name__ == "__main__":
    crawler = PostgresSchemaCrawler()
    synced_count = crawler.sync_semantic_catalog(use_llm=True)
    print(f"Successfully synced {synced_count} columns into semantic_governance.semantic_catalog.")