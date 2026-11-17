"""Dagster asset definitions for automated metadata crawling and semantic enrichment."""

from dagster import AssetExecutionContext, asset
from src.fabric.schema_crawler import PostgresSchemaCrawler


@asset(group_name="semantic_data_fabric")
def postgres_raw_metadata(context: AssetExecutionContext) -> list[dict]:
    """Extract relational schemas, data types, and foreign-key topology from PostgreSQL."""
    crawler = PostgresSchemaCrawler()
    metadata = crawler.extract_metadata(target_schemas=("gold",))
    context.log.info(f"Extracted {len(metadata)} relational column definitions.")
    return metadata


@asset(group_name="semantic_data_fabric", deps=[postgres_raw_metadata])
def enriched_semantic_catalog(context: AssetExecutionContext) -> dict:
    """Enrich extracted metadata with local LLM business glossary terms and PII tags."""
    crawler = PostgresSchemaCrawler()
    indexed_count = crawler.sync_semantic_catalog(use_llm=True)
    context.log.info(f"Synchronized {indexed_count} governed entries into gold.semantic_catalog.")
    return {"status": "synchronized", "columns_indexed": indexed_count}