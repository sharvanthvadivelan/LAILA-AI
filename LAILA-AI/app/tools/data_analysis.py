import json
import pandas as pd
from pydantic import BaseModel, Field
from typing import Literal


class AnalysisRequest(BaseModel):
    document_id: str
    group_by: str | None = None
    value_column: str | None = None
    aggregate: Literal["mean", "sum", "count", "min", "max"] = "mean"
    sort_by: str | None = None
    descending: bool = False
    filter_column: str | None = None
    filter_value: str | None = None


def analyze(path, request):
    suffix = __import__("pathlib").Path(path).suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, nrows=50001)
    elif suffix == ".xlsx":
        from app.rag.loader import extract

        extract(path)  # shared zip/row limit checks
        df = pd.read_excel(path, nrows=50001)
    elif suffix == ".json":
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
        if not isinstance(obj, list):
            raise ValueError("JSON dataset must be an array of records.")
        df = pd.DataFrame(obj)
    else:
        raise ValueError("Data analysis supports CSV, JSON arrays and XLSX.")
    if len(df) > 50000 or len(df.columns) > 200:
        raise ValueError("Dataset limit: 50,000 rows and 200 columns.")
    df.columns = df.columns.map(str)
    for col in (
        request.group_by,
        request.value_column,
        request.sort_by,
        request.filter_column,
    ):
        if col and col not in df.columns:
            raise ValueError("Unknown column: " + col)
    if request.filter_column:
        df = df[df[request.filter_column].astype(str) == str(request.filter_value)]
    if request.sort_by:
        df = df.sort_values(request.sort_by, ascending=not request.descending)
    numeric = df.select_dtypes(include="number")
    chart = []
    if request.group_by and request.value_column:
        grouped = (
            df.groupby(request.group_by, dropna=False)[request.value_column]
            .agg(request.aggregate)
            .head(30)
        )
        chart = [
            {"label": str(k), "value": float(v)}
            for k, v in grouped.items()
            if pd.notna(v)
        ]
    elif len(numeric.columns):
        col = numeric.columns[0]
        chart = [
            {"label": str(i), "value": float(v)}
            for i, v in numeric[col].head(30).items()
            if pd.notna(v)
        ]
    result = {
        "rows": len(df),
        "columns": [
            {
                "name": str(c),
                "dtype": str(df[c].dtype),
                "missing": int(df[c].isna().sum()),
            }
            for c in df.columns
        ],
        "preview": json.loads(df.head(30).to_json(orient="records", date_format="iso")),
        "statistics": (
            json.loads(numeric.describe().to_json()) if len(numeric.columns) else {}
        ),
        "correlations": (
            json.loads(numeric.corr().to_json()) if len(numeric.columns) > 1 else {}
        ),
        "chart": chart,
    }
    return result
