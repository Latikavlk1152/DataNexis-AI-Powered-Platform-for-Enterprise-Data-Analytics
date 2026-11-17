# Architectural Design & Governance Specification

## 1. Medallion Data Architecture
To separate raw ingestion from business-ready analytical entities, PostgreSQL schemas are partitioned into three logical tiers:
* **`bronze` (Raw Layer):** Immutable landing tables mirroring source operational schemas.
* **`silver` (Cleansed & Enriched Layer):** Standardized data types, deduplicated records, and PII-tagged attributes.
* **`gold` (Semantic Mart Layer):** Star-schema dimensions and fact tables governed by `dbt` metric definitions.

## 2. Semantic Context Engineering
Rather than relying on zero-shot prompt engineering, the Autonomous Analyst retrieves structured context prior to SQL synthesis:
1. **DDL & Foreign Key Topology:** Extracted via `information_schema` crawlers.
2. **Business Glossary & Metric Definitions:** Parsed from `dbt` YAML documentation.
3. **Validated Query Exemplars:** Stored as vector embeddings in `pgvector` for few-shot similarity retrieval.

## 3. Data Sovereignty & Ethical AI Guardrails
* **Zero External Data Egress:** All embeddings and LLM token generation occur locally via Ollama.
* **AST SQL Validation:** Generated SQL statements are parsed to verify read-only (`SELECT`) compliance before execution.
* **Explainability:** Every analytical output surfaces the generated SQL, the retrieved semantic definitions, and confidence/lineage notes.
