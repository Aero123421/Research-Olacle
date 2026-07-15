from __future__ import annotations

import csv
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .utils import atomic_write_json, atomic_write_text, iso_now, markdown_table

NULL_VALUES = {"", "na", "n/a", "nan", "none", "null", "missing"}


def _numeric(values: list[str]) -> list[float]:
    result = []
    for value in values:
        if value.strip().lower() in NULL_VALUES:
            continue
        try:
            number = float(value)
            if math.isfinite(number):
                result.append(number)
        except ValueError:
            return []
    return result


def profile_csv(path: Path, *, max_rows: int = 100_000) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        columns: dict[str, list[str]] = {name: [] for name in reader.fieldnames}
        row_count = 0
        duplicate_counter: Counter[tuple[str, ...]] = Counter()
        for row in reader:
            if row_count >= max_rows:
                break
            row_count += 1
            key = tuple(row.get(name, "") or "" for name in reader.fieldnames)
            duplicate_counter[key] += 1
            for name in reader.fieldnames:
                columns[name].append(row.get(name, "") or "")
    profiles = []
    for name, values in columns.items():
        missing = sum(1 for value in values if value.strip().lower() in NULL_VALUES)
        unique = len(set(values))
        numeric = _numeric(values)
        profile: dict[str, Any] = {
            "name": name,
            "missing": missing,
            "missing_fraction": missing / row_count if row_count else 0,
            "unique": unique,
            "unique_fraction": unique / row_count if row_count else 0,
            "inferred_type": "numeric"
            if numeric and len(numeric) >= max(1, row_count - missing)
            else "categorical_or_text",
        }
        if profile["inferred_type"] == "numeric" and numeric:
            ordered = sorted(numeric)
            profile.update(
                {
                    "min": ordered[0],
                    "max": ordered[-1],
                    "mean": statistics.fmean(ordered),
                    "median": statistics.median(ordered),
                    "stdev": statistics.pstdev(ordered) if len(ordered) > 1 else 0.0,
                }
            )
        else:
            profile["top_values"] = Counter(values).most_common(10)
        profiles.append(profile)
    duplicates = sum(count - 1 for count in duplicate_counter.values() if count > 1)
    return {
        "schema_version": 1,
        "path": str(path),
        "sampled_rows": row_count,
        "max_rows": max_rows,
        "truncated": row_count >= max_rows,
        "duplicate_rows_in_sample": duplicates,
        "columns": profiles,
        "generated_at": iso_now(),
    }


def render_profile(value: dict[str, Any]) -> str:
    rows = []
    for column in value["columns"]:
        rows.append(
            (
                column["name"],
                column["inferred_type"],
                column["missing"],
                f"{column['missing_fraction']:.1%}",
                column["unique"],
            )
        )
    return f"""# Data inventory

Source: `{value["path"]}`

Sampled rows: **{value["sampled_rows"]}**

Duplicate rows in sample: **{value["duplicate_rows_in_sample"]}**

Generated: `{value["generated_at"]}`

{markdown_table(("Column", "Type", "Missing", "Missing %", "Unique"), rows)}

> This inventory is descriptive evidence for Research Planner. It is not a
> substitute for competition-specific leakage analysis, data-generating-process
> analysis, or a validated cross-validation contract.
"""


def profile_dataset(path: Path, *, output_dir: Path, max_rows: int = 100_000) -> tuple[Path, Path]:
    if path.suffix.lower() != ".csv":
        raise ValueError(
            "Base installation profiles CSV files. Install the data extra for Parquet/Arrow support."
        )
    value = profile_csv(path, max_rows=max_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{path.stem}-inventory.json"
    md_path = output_dir / f"{path.stem}-inventory.md"
    atomic_write_json(json_path, value)
    atomic_write_text(md_path, render_profile(value))
    return json_path, md_path
