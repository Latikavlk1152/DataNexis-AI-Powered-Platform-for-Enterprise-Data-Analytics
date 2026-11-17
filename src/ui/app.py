"""Streamlit + Apache ECharts Workspace for the Semantic Data Fabric & Autonomous Analyst."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
    
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts
from config.settings import settings
from src.agent.analyst_agent import AutonomousAnalyst
from src.agent.sql_guardrails import is_safe_read_only_sql
from src.analytics.profiler import summarize_dataframe
from src.fabric.schema_crawler import PostgresSchemaCrawler

st.set_page_config(
    page_title="Semantic Data Fabric & Autonomous Analyst",
    layout="wide",
)


@st.cache_resource
def get_analyst() -> AutonomousAnalyst:
    return AutonomousAnalyst()


@st.cache_resource
def get_crawler() -> PostgresSchemaCrawler:
    return PostgresSchemaCrawler()


def render_echarts(df: pd.DataFrame, chart_type: str, x_col: str | None, y_col: str | None) -> None:
    """Render interactive Apache ECharts visualizations from analytical query outputs."""
    if df.empty or len(df.columns) < 2:
        return

    x_field = x_col if x_col in df.columns else df.columns[0]
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    y_field = y_col if y_col in numeric_cols else (numeric_cols[0] if numeric_cols else None)

    if not y_field:
        return

    x_data = df[x_field].astype(str).tolist()
    y_data = [round(float(v), 2) if pd.notnull(v) else 0 for v in df[y_field].tolist()]

    if chart_type == "pie":
        pie_data = [{"value": y, "name": x} for x, y in zip(x_data, y_data)]
        options = {
            "tooltip": {"trigger": "item"},
            "legend": {"top": "bottom"},
            "series": [
                {
                    "name": y_field,
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "data": pie_data,
                }
            ],
        }
    else:
        series_type = "line" if chart_type == "line" else "bar"
        options = {
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 20}},
            "yAxis": {"type": "value"},
            "series": [{"name": y_field, "type": series_type, "data": y_data, "smooth": True}],
        }

    st_echarts(options=options, height="380px")


st.title("DataNexis — AI-Powered Platform for Enterprise Data Analytics")
st.caption(
    f"Privacy-Preserving Local Inference (`{settings.ollama_model}`) | "
    f"PostgreSQL 16 Medallion Store | Human-in-the-Loop Governance"
)

tab_analyst, tab_catalog = st.tabs(["Autonomous Analyst", "Semantic Data Fabric Catalog"])

# -------------------------------------------------------------------------
# TAB 1: AUTONOMOUS ANALYST
# -------------------------------------------------------------------------
with tab_analyst:
    st.subheader("Natural Language Enterprise Intelligence")

    sample_questions = [
        "What is the average yield purity and batch disposition breakdown across manufacturing facilities?",
        "Which clinical trial sites have the highest protocol deviation and adverse event counts?",
        "Show total active patient enrollment and protocol deviations by therapeutic area and trial phase.",
        "Which logistics carriers have experienced temperature excursions in cold-chain shipments?",
    ]

    selected_sample = st.selectbox("Sample Executive Queries:", ["Custom question..."] + sample_questions)
    default_q = "" if selected_sample == "Custom question..." else selected_sample
    user_question = st.text_input(
        "Ask a business question across orders, customers, products, or logistics SLAs:",
        value=default_q,
        placeholder="e.g., What is the SLA breach rate by origin hub?",
    )

    hitl_enabled = st.checkbox(
        "Enable Human-in-the-Loop (HITL) SQL Inspection before execution",
        value=settings.enable_hitl_approval,
    )

    if st.button("Generate Semantic Query Plan", type="primary") and user_question.strip():
        analyst = get_analyst()
        with st.spinner("Retrieving semantic catalog context & synthesizing SQL via local LLM..."):
            try:
                plan = analyst.generate_query_plan(user_question)
                st.session_state["current_plan"] = plan
                st.session_state["current_question"] = user_question
            except Exception as exc:
                st.error(f"Failed to generate query plan: {exc}")

    if "current_plan" in st.session_state:
        plan = st.session_state["current_plan"]
        st.markdown("### 1. Explainable Reasoning & Lineage")
        st.info(plan.get("reasoning", "No reasoning provided."))

        st.markdown("### 2. Governed SQL Verification")
        edited_sql = st.text_area("Generated PostgreSQL Query (Editable):", value=plan.get("sql", ""), height=140)
        is_safe, guardrail_msg = is_safe_read_only_sql(edited_sql)

        if is_safe:
            st.success(f"Guardrail Check Passed: {guardrail_msg}")
        else:
            st.error(f"Guardrail Violation: {guardrail_msg}")

        execute_clicked = True if not hitl_enabled else st.button("Approve & Execute Read-Only Query")

        if execute_clicked and is_safe:
            analyst = get_analyst()
            with st.spinner("Executing query on PostgreSQL & profiling results..."):
                try:
                    df_result = analyst.execute_governed_query(edited_sql)
                    stats = summarize_dataframe(df_result)
                    insight_text = analyst.synthesize_executive_insight(
                        st.session_state["current_question"], df_result, stats
                    )

                    st.markdown("### 3. Executive Insights & Statistical Summary")
                    st.markdown(insight_text)

                    if stats["anomalies_detected"]:
                        for alert in stats["anomalies_detected"]:
                            st.warning(alert)

                    col_viz, col_data = st.columns([1.2, 1])
                    with col_viz:
                        st.markdown("**Interactive Visualization (Apache ECharts)**")
                        render_echarts(
                            df_result,
                            plan.get("suggested_chart", "bar"),
                            plan.get("x_axis"),
                            plan.get("y_axis"),
                        )
                    with col_data:
                        st.markdown("**Governed Result Set**")
                        st.dataframe(df_result, use_container_width=True)
                except Exception as exc:
                    st.error(f"Query execution error: {exc}")

# -------------------------------------------------------------------------
# TAB 2: SEMANTIC DATA FABRIC CATALOG
# -------------------------------------------------------------------------
with tab_catalog:
    st.subheader("Automated Metadata & Governance Catalog")
    st.write(
        "Crawled from PostgreSQL `information_schema` and enriched locally with business glossary "
        "terms, foreign-key lineage, and PII classifications."
    )

    if st.button("Re-run Schema Crawler & LLM Enrichment"):
        with st.spinner("Crawling PostgreSQL schemas and enriching with Mistral..."):
            count = get_crawler().sync_semantic_catalog(use_llm=True)
            st.success(f"Synchronized {count} columns into the Semantic Catalog.")

    catalog_rows = get_crawler().get_catalog_context()
    if catalog_rows:
        df_cat = pd.DataFrame(catalog_rows)[
            [
                "schema_name",
                "table_name",
                "column_name",
                "data_type",
                "business_glossary_term",
                "pii_classification",
                "foreign_key_ref",
                "semantic_description",
            ]
        ]
        st.dataframe(df_cat, use_container_width=True, height=520)