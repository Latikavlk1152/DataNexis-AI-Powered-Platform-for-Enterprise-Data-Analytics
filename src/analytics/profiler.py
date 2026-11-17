"""Automated Statistical Profiling and Anomaly Detection Engine."""

import numpy as np
import pandas as pd


def summarize_dataframe(df: pd.DataFrame) -> dict:
    """Generate descriptive statistics, top performers, and z-score outlier flags."""
    summary: dict = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "numeric_metrics": {},
        "anomalies_detected": [],
    }

    if df.empty:
        return summary

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        mean_val = float(series.mean())
        std_val = float(series.std()) if len(series) > 1 else 0.0
        summary["numeric_metrics"][col] = {
            "sum": round(float(series.sum()), 2),
            "mean": round(mean_val, 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
        }

        if std_val > 0 and len(series) >= 4:
            z_scores = (series - mean_val) / std_val
            outlier_indices = series[z_scores.abs() > 2.0].index.tolist()
            if outlier_indices:
                summary["anomalies_detected"].append(
                    f"Column '{col}' has {len(outlier_indices)} statistical outlier(s) (|z| > 2.0)."
                )

    return summary