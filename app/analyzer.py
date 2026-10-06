import json
import re
import numpy as np
import pandas as pd


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize a DataFrame."""
    if df.empty:
        return df

    # Remove duplicate rows
    df = df.drop_duplicates()

    for col in df.columns:
        # Strip whitespace
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
            # Remove multiple spaces
            df[col] = df[col].str.replace(r'\s+', ' ', regex=True)
            # Remove leading/trailing special characters
            df[col] = df[col].str.replace(r'^[\s\-_]+|[\s\-_]+$', '', regex=True)

        # Replace empty strings with NaN
        df[col] = df[col].replace('', np.nan)

    # Drop rows where all values are NaN
    df = df.dropna(how='all')

    # Reset index
    df = df.reset_index(drop=True)

    return df


def try_numeric_convert(series: pd.Series) -> pd.Series:
    """Attempt to convert a series to numeric by extracting numbers."""
    def extract_number(val):
        if pd.isna(val):
            return np.nan
        val_str = str(val)
        # Remove currency symbols, commas, percent signs
        cleaned = re.sub(r'[^\d.\-]', '', val_str.replace(',', ''))
        try:
            return float(cleaned) if cleaned else np.nan
        except ValueError:
            return np.nan

    converted = series.apply(extract_number)
    # Only return if at least 50% values are numeric
    non_null = converted.dropna()
    if len(non_null) > 0 and len(non_null) / len(series) >= 0.5:
        return converted
    return series


def analyze_dataframe(df: pd.DataFrame) -> dict:
    """Generate comprehensive statistics from a DataFrame."""
    if df.empty:
        return {'error': 'No data to analyze'}

    total_records = len(df)
    total_columns = len(df.columns)

    column_stats = {}
    numeric_columns = []
    text_columns = []

    for col in df.columns:
        col_data = df[col]
        col_type = 'text'
        stats = {
            'name': col,
            'type': 'text',
            'total': total_records,
            'non_null': int(col_data.notna().sum()),
            'null_count': int(col_data.isna().sum()),
            'null_pct': round(float(col_data.isna().mean() * 100), 2),
            'unique_count': int(col_data.nunique()),
        }

        # Try numeric conversion
        numeric_series = try_numeric_convert(col_data.dropna() if col_data.dtype == object else col_data)
        if numeric_series.dtype in [np.float64, np.int64] or pd.api.types.is_numeric_dtype(numeric_series):
            numeric_vals = pd.to_numeric(numeric_series, errors='coerce').dropna()
            if len(numeric_vals) > 0:
                col_type = 'numeric'
                stats.update({
                    'type': 'numeric',
                    'mean': round(float(numeric_vals.mean()), 4),
                    'median': round(float(numeric_vals.median()), 4),
                    'std': round(float(numeric_vals.std()), 4) if len(numeric_vals) > 1 else 0,
                    'min': round(float(numeric_vals.min()), 4),
                    'max': round(float(numeric_vals.max()), 4),
                    'sum': round(float(numeric_vals.sum()), 4),
                    'q25': round(float(numeric_vals.quantile(0.25)), 4),
                    'q75': round(float(numeric_vals.quantile(0.75)), 4),
                })
                numeric_columns.append(col)

        if col_type == 'text':
            text_cols = col_data.dropna().astype(str)
            value_counts = text_cols.value_counts().head(10)
            stats.update({
                'type': 'text',
                'top_values': [{'value': k, 'count': int(v)} for k, v in value_counts.items()],
                'avg_length': round(float(text_cols.str.len().mean()), 2) if len(text_cols) > 0 else 0,
            })
            text_columns.append(col)

        column_stats[col] = stats

    summary = {
        'total_records': total_records,
        'total_columns': total_columns,
        'numeric_columns': numeric_columns,
        'text_columns': text_columns,
        'column_stats': column_stats,
        'completeness_pct': round(float(df.notna().mean().mean() * 100), 2),
    }

    return summary


def generate_chart_data(df: pd.DataFrame, stats: dict) -> dict:
    """Generate chart data for Plotly visualization."""
    charts = {}

    # Bar chart: value counts for first text column
    text_cols = stats.get('text_columns', [])
    numeric_cols = stats.get('numeric_columns', [])

    if text_cols:
        col = text_cols[0]
        vc = df[col].value_counts().head(15)
        charts['bar_value_counts'] = {
            'title': f'Top Values: {col}',
            'type': 'bar',
            'labels': list(vc.index.astype(str)),
            'values': [int(v) for v in vc.values],
            'column': col,
        }

        # Pie chart for categorical
        if len(vc) <= 10:
            charts['pie_distribution'] = {
                'title': f'Distribution: {col}',
                'type': 'pie',
                'labels': list(vc.index.astype(str)),
                'values': [int(v) for v in vc.values],
                'column': col,
            }

    if numeric_cols:
        col = numeric_cols[0]
        numeric_series = try_numeric_convert(df[col])
        numeric_vals = pd.to_numeric(numeric_series, errors='coerce').dropna()

        if len(numeric_vals) > 0:
            # Histogram data
            bins = min(20, len(numeric_vals))
            counts, bin_edges = np.histogram(numeric_vals, bins=bins)
            bin_labels = [f"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}" for i in range(len(bin_edges)-1)]
            charts['histogram'] = {
                'title': f'Distribution: {col}',
                'type': 'histogram',
                'labels': bin_labels,
                'values': [int(c) for c in counts],
                'column': col,
            }

            # Line chart (index vs value)
            if len(numeric_vals) > 1:
                sample_size = min(100, len(numeric_vals))
                sampled = numeric_vals.head(sample_size)
                charts['line_trend'] = {
                    'title': f'Trend: {col}',
                    'type': 'line',
                    'labels': list(range(1, len(sampled)+1)),
                    'values': [round(float(v), 4) for v in sampled.values],
                    'column': col,
                }

    # Scatter plot: first two numeric columns
    if len(numeric_cols) >= 2:
        col1, col2 = numeric_cols[0], numeric_cols[1]
        s1 = pd.to_numeric(try_numeric_convert(df[col1]), errors='coerce').dropna()
        s2 = pd.to_numeric(try_numeric_convert(df[col2]), errors='coerce').dropna()
        min_len = min(len(s1), len(s2), 200)
        if min_len > 0:
            charts['scatter'] = {
                'title': f'{col1} vs {col2}',
                'type': 'scatter',
                'x': [round(float(v), 4) for v in s1.values[:min_len]],
                'y': [round(float(v), 4) for v in s2.values[:min_len]],
                'x_label': col1,
                'y_label': col2,
            }

    return charts


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to JSON-serializable list of records."""
    return json.loads(df.to_json(orient='records', force_ascii=False))
