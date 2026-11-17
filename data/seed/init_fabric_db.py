"""Initialize PostgreSQL Life Sciences Domain Schemas (clinical_edc, gmp_manufacturing, supply_chain)."""

from datetime import datetime, timedelta
import random
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from config.settings import settings


def ensure_database_exists() -> None:
    """Create the target database if it does not already exist."""
    conn = psycopg2.connect(
        dbname="postgres",
        user=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s;",
            (settings.postgres_db,),
        )
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{settings.postgres_db}";')
            print(f"Created database: {settings.postgres_db}")
        else:
            print(f"Database already exists: {settings.postgres_db}")
    conn.close()


PHARMA_DOMAINS_DDL_SQL = """
CREATE SCHEMA IF NOT EXISTS clinical_edc;
CREATE SCHEMA IF NOT EXISTS gmp_manufacturing;
CREATE SCHEMA IF NOT EXISTS supply_chain;
CREATE SCHEMA IF NOT EXISTS semantic_governance;

-- Clean up existing tables
DROP TABLE IF EXISTS supply_chain.fact_cold_chain_shipments CASCADE;
DROP TABLE IF EXISTS gmp_manufacturing.fact_batch_records CASCADE;
DROP TABLE IF EXISTS clinical_edc.fact_patient_cohorts CASCADE;
DROP TABLE IF EXISTS clinical_edc.dim_clinical_protocols CASCADE;
DROP TABLE IF EXISTS semantic_governance.semantic_catalog CASCADE;

-- Metadata Governance Catalog
CREATE TABLE semantic_governance.semantic_catalog (
    catalog_id SERIAL PRIMARY KEY,
    schema_name VARCHAR(64) NOT NULL,
    table_name VARCHAR(128) NOT NULL,
    column_name VARCHAR(128) NOT NULL,
    data_type VARCHAR(64) NOT NULL,
    is_nullable BOOLEAN NOT NULL,
    foreign_key_ref VARCHAR(256),
    semantic_description TEXT,
    business_glossary_term VARCHAR(128),
    pii_classification VARCHAR(32) DEFAULT 'NON_PII',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (schema_name, table_name, column_name)
);

-- Clinical EDC: Protocols & Trials Dimension
CREATE TABLE clinical_edc.dim_clinical_protocols (
    protocol_id VARCHAR(16) PRIMARY KEY,
    protocol_title VARCHAR(128) NOT NULL,
    therapeutic_area VARCHAR(64) NOT NULL, -- e.g., 'Oncology', 'Vaccines', 'Immunology'
    trial_phase VARCHAR(16) NOT NULL, -- 'Phase I', 'Phase II', 'Phase III'
    regulatory_region VARCHAR(32) NOT NULL, -- 'EMA (Europe)', 'US FDA', 'PMDA (Japan)'
    lead_investigator VARCHAR(64) NOT NULL,
    target_enrollment INTEGER NOT NULL
);

-- Clinical EDC: Patient Cohorts & Protocol Compliance
CREATE TABLE clinical_edc.fact_patient_cohorts (
    cohort_record_id VARCHAR(20) PRIMARY KEY,
    protocol_id VARCHAR(16) NOT NULL REFERENCES clinical_edc.dim_clinical_protocols(protocol_id),
    site_location VARCHAR(64) NOT NULL,
    active_enrolled_cnt INTEGER NOT NULL,
    protocol_deviation_cnt INTEGER NOT NULL,
    adverse_event_reports_cnt INTEGER NOT NULL,
    site_audit_status VARCHAR(20) NOT NULL -- 'PASSED', 'REVIEW_REQUIRED'
);

-- GMP Manufacturing: Biologics Batch Production & Quality Assays
CREATE TABLE gmp_manufacturing.fact_batch_records (
    batch_id VARCHAR(20) PRIMARY KEY,
    protocol_id VARCHAR(16) NOT NULL REFERENCES clinical_edc.dim_clinical_protocols(protocol_id),
    facility_plant VARCHAR(64) NOT NULL, -- e.g., 'Cork Bio-Plant', 'Visp Facility', 'Singapore Hub'
    biologic_product_name VARCHAR(64) NOT NULL,
    yield_purity_pct NUMERIC(5, 2) NOT NULL,
    impurity_ppm NUMERIC(6, 2) NOT NULL,
    batch_disposition VARCHAR(24) NOT NULL -- 'RELEASED', 'QUARANTINE', 'REJECTED'
);

-- Supply Chain: Cold-Chain Biologics Distribution & Temperature Compliance
CREATE TABLE supply_chain.fact_cold_chain_shipments (
    shipment_id VARCHAR(20) PRIMARY KEY,
    batch_id VARCHAR(20) NOT NULL REFERENCES gmp_manufacturing.fact_batch_records(batch_id),
    origin_hub VARCHAR(64) NOT NULL,
    destination_hospital VARCHAR(64) NOT NULL,
    transit_duration_hrs NUMERIC(6, 2) NOT NULL,
    temp_excursion_flg BOOLEAN NOT NULL, -- True if temp violated 2-8°C window
    logistics_carrier VARCHAR(64) NOT NULL
);
"""


def populate_pharma_data(engine) -> None:
    """Insert realistic Life Sciences R&D and supply chain records."""
    random.seed(42)

    protocols = [
        ("PRT-101", "Monoclonal Antibody Evaluation in Solid Tumors", "Oncology", "Phase III", "EMA (Europe)", "Dr. H. Lindemann", 450),
        ("PRT-102", "Next-Gen mRNA Vaccine Booster Efficacy", "Vaccines", "Phase II", "US FDA", "Dr. S. Vance", 800),
        ("PRT-103", "Autoimmune Targeted Biologic Therapy", "Immunology", "Phase III", "EMA (Europe)", "Dr. M. Weber", 600),
        ("PRT-104", "Cardiovascular Revascularization Biomarker Study", "Cardiology", "Phase II", "PMDA (Japan)", "Dr. K. Tanaka", 350),
    ]

    products = {
        "PRT-101": "Keytruda-BioVariant",
        "PRT-102": "mRNA-Lipid Nanoparticle",
        "PRT-103": "Bivalent Immunomodulator",
        "PRT-104": "CardioTarget Protomer",
    }

    facilities = ["Cork Bio-Plant (Ireland)", "Visp Biologics Hub (Switzerland)", "Singapore R&D Center", "Frankfurt Vaccine Facility"]
    hospitals = ["Charité Berlin", "Karolinska Stockholm", "General Hospital Vienna", "Zurich University Clinic"]
    carriers = ["FedEx HealthCare Logistics", "World Courier ColdChain", "DHL Life Sciences"]

    with engine.begin() as conn:
        for p in protocols:
            conn.execute(
                text("""
                    INSERT INTO clinical_edc.dim_clinical_protocols
                    (protocol_id, protocol_title, therapeutic_area, trial_phase, regulatory_region, lead_investigator, target_enrollment)
                    VALUES (:p0, :p1, :p2, :p3, :p4, :p5, :p6)
                """),
                {f"p{i}": val for i, val in enumerate(p)},
            )

        cohort_counter = 1
        for proto in protocols:
            proto_id = proto[0]
            for s_idx in range(1, 11):
                rec_id = f"COH-{2000 + cohort_counter}"
                site = f"Clinical Site #{s_idx} ({random.choice(['Berlin', 'Stockholm', 'Zurich', 'Vienna', 'Dublin'])})"
                enrolled = random.randint(30, 95)
                deviations = random.randint(0, 4)
                adverse = random.randint(1, 12)
                status = "PASSED" if deviations <= 2 else "REVIEW_REQUIRED"

                conn.execute(
                    text("""
                        INSERT INTO clinical_edc.fact_patient_cohorts
                        (cohort_record_id, protocol_id, site_location, active_enrolled_cnt, protocol_deviation_cnt, adverse_event_reports_cnt, site_audit_status)
                        VALUES (:rid, :pid, :loc, :act, :dev, :adv, :st)
                    """),
                    {
                        "rid": rec_id,
                        "pid": proto_id,
                        "loc": site,
                        "act": enrolled,
                        "dev": deviations,
                        "adv": adverse,
                        "st": status,
                    },
                )
                cohort_counter += 1

        batch_counter = 1
        for proto in protocols:
            proto_id = proto[0]
            prod_name = products[proto_id]
            for b_idx in range(1, 10):
                batch_id = f"BAT-{5000 + batch_counter}"
                fac = random.choice(facilities)
                purity = round(random.uniform(96.50, 99.95), 2)
                impurity = round(random.uniform(0.02, 1.45), 2)
                disposition = "RELEASED" if purity > 98.0 and impurity < 0.8 else random.choice(["RELEASED", "QUARANTINE", "REJECTED"])

                conn.execute(
                    text("""
                        INSERT INTO gmp_manufacturing.fact_batch_records
                        (batch_id, protocol_id, facility_plant, biologic_product_name, yield_purity_pct, impurity_ppm, batch_disposition)
                        VALUES (:bid, :pid, :fac, :prod, :pur, :imp, :dsp)
                    """),
                    {
                        "bid": batch_id,
                        "pid": proto_id,
                        "fac": fac,
                        "prod": prod_name,
                        "pur": purity,
                        "imp": impurity,
                        "dsp": disposition,
                    },
                )

                ship_id = f"SHP-{8000 + batch_counter}"
                origin = fac.split(" ")[0] + " Hub"
                dest = random.choice(hospitals)
                transit = round(random.uniform(18.0, 72.5), 1)
                excursion = True if transit > 55.0 and random.random() > 0.6 else False
                carrier = random.choice(carriers)

                conn.execute(
                    text("""
                        INSERT INTO supply_chain.fact_cold_chain_shipments
                        (shipment_id, batch_id, origin_hub, destination_hospital, transit_duration_hrs, temp_excursion_flg, logistics_carrier)
                        VALUES (:shid, :bid, :org, :dst, :tr, :exc, :car)
                    """),
                    {
                        "shid": ship_id,
                        "bid": batch_id,
                        "org": origin,
                        "dst": dest,
                        "tr": transit,
                        "exc": excursion,
                        "car": carrier,
                    },
                )
                batch_counter += 1

    print("Seeded multi-schema Life Sciences architecture successfully.")


if __name__ == "__main__":
    ensure_database_exists()
    db_engine = create_engine(settings.database_url)
    with db_engine.begin() as connection:
        connection.execute(text(PHARMA_DOMAINS_DDL_SQL))
    populate_pharma_data(db_engine)