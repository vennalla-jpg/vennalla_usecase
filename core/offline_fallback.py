"""Deterministic pipeline steps used when the configured LLM is unavailable."""

import json
import html
import os
from pathlib import Path

import pandas as pd

from agents.profiler import _compute_stats
from agents.bronze_agent import _apply_bronze_rules
from agents.silver_agent import _apply_silver_rules
from agents.gold_agent import _apply_gold_rules
from core.config import PROFILES_DIR, STTM_DIR, REPORTS_DIR


def run_phase1_without_llm(file_paths: list[str], run_id: str) -> tuple[str, str]:
    """Create the Phase 1 profile and Bronze STTM using local data inspection."""
    profile = _compute_stats(file_paths)
    profile["analysis"] = {
        "semantic_meanings": {},
        "join_keys": [],
        "quality_notes": [
            "Profile generated locally because the configured LLM provider was unavailable."
        ],
    }

    for file_path in file_paths:
        dataset_name = Path(file_path).stem
        columns = profile.get("datasets", {}).get(dataset_name, {}).get("columns", {})
        for column_name in columns:
            for other_path in file_paths:
                if other_path == file_path:
                    continue
                other_name = Path(other_path).stem
                other_columns = profile.get("datasets", {}).get(other_name, {}).get("columns", {})
                if column_name in other_columns and column_name.lower().endswith("_id"):
                    profile["analysis"]["join_keys"].append({
                        "left_dataset": dataset_name,
                        "left_column": column_name,
                        "right_dataset": other_name,
                        "right_column": column_name,
                        "confidence": "high",
                    })

    profile_path = PROFILES_DIR / f"profile_combined_{run_id[:8]}_offline.json"
    profile_path.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")

    rows: list[dict] = []
    for file_path in file_paths:
        file_name = os.path.basename(file_path)
        dataset_name = Path(file_path).stem
        dataset = profile.get("datasets", {}).get(dataset_name, {})
        for column_name, column_info in dataset.get("columns", {}).items():
            dtype = str(column_info.get("dtype", ""))
            if "int" in dtype:
                cast_logic = "Cast to integer"
            elif "float" in dtype or "double" in dtype:
                cast_logic = "Cast to numeric decimal"
            elif "datetime" in dtype or "date" in dtype:
                cast_logic = "Cast to datetime"
            else:
                cast_logic = "Preserve as text"
            rows.append({
                "source_schema": "CSV",
                "source_table": file_name,
                "source_column": column_name,
                "target_schema": "Bronze",
                "target_table": f"bronze_{dataset_name}",
                "target_column": column_name,
                "transformation_type": "Direct",
                "transformation_logic": cast_logic,
            })

        for target_column, logic in (
            ("_load_timestamp", "Add UTC ingestion timestamp"),
            ("_source_file", "Add source file path for lineage"),
        ):
            rows.append({
                "source_schema": "CSV",
                "source_table": file_name,
                "source_column": "",
                "target_schema": "Bronze",
                "target_table": f"bronze_{dataset_name}",
                "target_column": target_column,
                "transformation_type": "Indirect",
                "transformation_logic": logic,
            })

    sttm_path = STTM_DIR / f"sttm_bronze_{run_id[:8]}_offline.csv"
    pd.DataFrame(rows).to_csv(sttm_path, index=False)
    return str(profile_path), str(sttm_path)


def run_phase2_without_llm(
    file_paths: list[str], bronze_sttm_path: str, run_id: str
) -> tuple[list[str], str]:
    """Execute approved Bronze rules and create a deterministic Silver STTM."""
    bronze_paths = _apply_bronze_rules(file_paths, bronze_sttm_path, run_id)
    rows: list[dict] = []

    for bronze_path in bronze_paths:
        file_name = os.path.basename(bronze_path)
        stem = Path(file_name).stem
        target_table = f"silver_{stem.removesuffix('_bronze')}"
        df = pd.read_parquet(bronze_path)
        rows.append({
            "source_schema": "Bronze",
            "source_table": file_name,
            "source_column": "",
            "target_schema": "Silver",
            "target_table": target_table,
            "target_column": f"pk_{stem}_silver_id",
            "transformation_type": "Indirect",
            "transformation_logic": "Auto-generated sequential surrogate primary key starting from 1",
        })
        for column in df.columns:
            if column.startswith("_"):
                logic = "Preserve lineage metadata"
            elif "date" in column.lower() or "time" in column.lower():
                logic = "Trim text; standardise dates"
            elif pd.api.types.is_numeric_dtype(df[column]):
                logic = "Fill nulls with median; preserve numeric values"
            else:
                logic = "Trim text; fill nulls with mode for categorical values"
            rows.append({
                "source_schema": "Bronze",
                "source_table": file_name,
                "source_column": column,
                "target_schema": "Silver",
                "target_table": target_table,
                "target_column": column,
                "transformation_type": "Indirect",
                "transformation_logic": logic,
            })

    sttm_path = STTM_DIR / f"sttm_silver_{run_id[:8]}_offline.csv"
    pd.DataFrame(rows).to_csv(sttm_path, index=False)
    return bronze_paths, str(sttm_path)


def run_phase3_without_llm(
    bronze_paths: list[str], silver_sttm_path: str, business_intent: str, run_id: str
) -> tuple[list[str], str]:
    """Execute approved Silver rules and create a retail Gold STTM locally."""
    silver_paths = _apply_silver_rules(bronze_paths, silver_sttm_path, run_id)
    target_table = "retail_sales_summary"
    rows: list[dict] = []

    def add_rule(source_table: str, source_column: str, target_column: str, logic: str, kind: str = "Direct"):
        rows.append({
            "source_schema": "Silver",
            "source_table": source_table,
            "source_column": source_column,
            "target_schema": "Gold",
            "target_table": target_table,
            "target_column": target_column,
            "transformation_type": kind,
            "transformation_logic": logic,
        })

    sales_table = next((os.path.basename(path) for path in silver_paths if "sales_data" in path), "sales_data_silver.parquet")
    products_table = next((os.path.basename(path) for path in silver_paths if "products" in path), "products_silver.parquet")
    stores_table = next((os.path.basename(path) for path in silver_paths if "stores" in path), "stores_silver.parquet")

    for column in ("store_id", "product_id", "category", "product_name"):
        source_table = products_table if column in {"category", "product_name"} else sales_table
        add_rule(source_table, column, column, "Group by dimension")
    add_rule(stores_table, "store_id", "store_id", "Group by dimension")
    add_rule(stores_table, "store_name", "store_name", "Group by dimension")
    add_rule(stores_table, "region", "region", "Group by dimension")
    add_rule(sales_table, "total_amount", "total_amount", "Sum total sales amount", "Indirect")
    add_rule(sales_table, "quantity", "quantity", "Sum quantity sold", "Indirect")
    add_rule(sales_table, "transaction_id", "transaction_count", "Count transactions", "Indirect")

    sttm_path = STTM_DIR / f"sttm_gold_{run_id[:8]}_offline.csv"
    pd.DataFrame(rows).to_csv(sttm_path, index=False)
    return silver_paths, str(sttm_path)


def run_phase4_without_llm(
    silver_paths: list[str], gold_sttm_path: str, business_intent: str, run_id: str
) -> tuple[list[str], str]:
    """Materialise Gold tables and write a basic evidence-backed HTML report locally."""
    gold_paths = _apply_gold_rules(silver_paths, gold_sttm_path, business_intent, run_id)
    tables = [pd.read_parquet(path) for path in gold_paths]
    combined = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    answer = "No Gold records were produced."
    if not combined.empty:
        if {"region", "category", "total_amount"}.issubset(combined.columns):
            grouped = combined.dropna(subset=["region", "category"]).copy()
            grouped["total_amount"] = pd.to_numeric(grouped["total_amount"], errors="coerce")
            grouped = (
                grouped.dropna(subset=["total_amount"])
                .groupby(["region", "category"], as_index=False)["total_amount"]
                .sum()
            )
            top_by_region = grouped.loc[grouped.groupby("region")["total_amount"].idxmax()]
            top_by_region = top_by_region.sort_values("region")
            details = ", ".join(
                f"{row.category} in the {row.region} region with ${row.total_amount:,.2f}"
                for row in top_by_region.itertuples(index=False)
            )
            answer = f"The top-performing product categories by total sales revenue for each store region are: {details}."
        else:
            numeric = combined.select_dtypes(include="number")
            metric_text = ", ".join(
                f"{column}: {numeric[column].sum():,.2f}"
                for column in numeric.columns
                if column != "pk_gold_id"
            )
            answer = f"The report analysed {len(combined):,} Gold rows. Numeric totals: {metric_text or 'none available'}."
    report_path = REPORTS_DIR / f"report_{run_id[:8]}_offline.html"
    report_path.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>IDAMP Offline Report</title>"
        "<style>@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:translateY(0)}}"
        "@keyframes rule{from{transform:scaleX(0);transform-origin:left}to{transform:scaleX(1);transform-origin:left}}"
        "body{font-family:Segoe UI,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#263238}"
        "header{background:#176b87;color:white;padding:1.5rem;border-radius:8px}section{margin-top:1.5rem;padding:1.25rem;border:1px solid #d5dee3;border-radius:8px;animation:rise .55s ease-out both}"
        "section h2{color:#667eea;border-bottom:3px solid #667eea;padding-bottom:10px;margin-top:0;position:relative}"
        "section h2:after{content:'';position:absolute;left:0;right:0;bottom:-3px;height:3px;background:#667eea;animation:rule .65s .2s ease-out both}"
        ".answer{background:#e8f4f8;padding:20px;border-radius:8px;border-left:4px solid #28a745;animation:rise .6s .2s ease-out both}"
        "table{border-collapse:collapse;width:100%}th,td{padding:.5rem;border-bottom:1px solid #d5dee3;text-align:left}"
        "@media(prefers-reduced-motion:reduce){*,*:after{animation-duration:.01ms!important;animation-delay:0ms!important}}</style></head><body>"
        f"<header><h1>Retail Executive Report</h1><p>{html.escape(business_intent)}</p></header>"
        f"<section><h2>&#9989; Answer</h2><div class='answer'><p>{html.escape(answer)}</p></div></section>"
        f"<section><h2>Gold Outputs</h2><p>{html.escape(', '.join(gold_paths) or 'None')}</p>"
        f"{combined.head(25).to_html(index=False, escape=True) if not combined.empty else '<p>No rows.</p>'}</section>"
        "<footer><p>Generated locally because the configured LLM provider was unavailable.</p></footer></body></html>",
        encoding="utf-8",
    )
    return gold_paths, str(report_path)
