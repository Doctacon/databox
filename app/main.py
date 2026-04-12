"""Databox Explorer — Generic DuckDB data explorer."""

from __future__ import annotations

import io
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

PAGE_SIZE = 500

st.set_page_config(page_title="Databox Explorer", page_icon="📦", layout="wide")


def _find_db() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "databox.db"


@st.cache_resource
def _get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path), read_only=True)


def _get_schemas(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
        "ORDER BY table_schema"
    ).fetchall()
    return [r[0] for r in rows]


def _get_tables(con: duckdb.DuckDBPyConnection, schema: str) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = ? ORDER BY table_name",
        [schema],
    ).fetchall()
    return [r[0] for r in rows]


def _get_columns(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[dict]:
    return con.execute(
        "SELECT column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? "
        "ORDER BY ordinal_position",
        [schema, table],
    ).fetchall()


def _qualified(schema: str, table: str) -> str:
    return f'"{schema}"."{table}"'


st.title("Databox Explorer")

db_path = _find_db()
if not db_path.exists():
    st.error(f"Database not found at `{db_path}`. Run `databox run <pipeline>` first.")
    st.stop()

con = _get_connection(db_path)
schemas = _get_schemas(con)

if not schemas:
    st.warning("No data loaded yet. Run a pipeline first: `databox run ebird`")
    st.stop()

with st.sidebar:
    st.header("Navigation")
    schema = st.selectbox("Schema", schemas)
    tables = _get_tables(con, schema) if schema else []
    table = st.selectbox("Table", tables) if tables else None

    if table:
        qname = _qualified(schema, table)
        row_count = con.execute(f"SELECT COUNT(*) FROM {qname}").fetchone()[0]
        st.metric("Rows", f"{row_count:,}")

        st.divider()
        st.subheader("Columns")
        col_info = _get_columns(con, schema, table)
        for col_name, col_type, nullable in col_info:
            label = f"{col_name} `{col_type}`"
            if nullable == "YES":
                label += " (nullable)"
            st.text(label)

if not table:
    st.info("Select a schema and table from the sidebar.")
    st.stop()

qname = _qualified(schema, table)
tab_data, tab_profile, tab_chart, tab_sql = st.tabs(["Data", "Profile", "Chart", "SQL"])

with tab_data:
    columns = _get_columns(con, schema, table)
    col_names = [c[0] for c in columns]

    col1, col2 = st.columns(2)
    with col1:
        sort_col = st.selectbox("Sort by", ["(none)"] + col_names, key="sort")
    with col2:
        sort_asc = st.checkbox("Ascending", value=True, key="sort_asc")

    filter_col = st.selectbox("Filter column", ["(none)"] + col_names, key="filter_col")
    filter_val = ""
    if filter_col != "(none)":
        filter_val = st.text_input("Filter value (contains)", key="filter_val")

    query = f"SELECT * FROM {qname}"
    conditions = []
    if filter_col != "(none)" and filter_val:
        conditions.append(f"CAST(\"{filter_col}\" AS VARCHAR) ILIKE '%{filter_val}%'")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    if sort_col != "(none)":
        direction = "ASC" if sort_asc else "DESC"
        query += f' ORDER BY "{sort_col}" {direction}'

    page = st.number_input("Page", min_value=1, value=1, step=1)
    offset = (page - 1) * PAGE_SIZE
    query += f" LIMIT {PAGE_SIZE} OFFSET {offset}"

    df = con.execute(query).fetchdf()
    st.dataframe(df, use_container_width=True, hide_index=True)

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, f"{table}.csv", "text/csv")
    with col_dl2:
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        st.download_button("Download Parquet", buf.getvalue(), f"{table}.parquet")

with tab_profile:
    profile_df = con.execute(f"SELECT * FROM {qname} LIMIT 50000").fetchdf()

    if profile_df.empty:
        st.info("Table is empty.")
    else:
        total = len(profile_df)
        metrics = []
        for col_name in profile_df.columns:
            series = profile_df[col_name]
            null_count = series.isna().sum()
            null_pct = round(null_count / total * 100, 1) if total > 0 else 0
            distinct = series.nunique()
            dtype = str(series.dtype)

            entry = {
                "column": col_name,
                "type": dtype,
                "nulls": null_count,
                "null_pct": null_pct,
                "distinct": distinct,
            }

            if pd.api.types.is_numeric_dtype(series):
                clean = series.dropna()
                if len(clean) > 0:
                    entry["min"] = clean.min()
                    entry["max"] = clean.max()
                    entry["mean"] = round(clean.mean(), 2)
                    entry["median"] = round(clean.median(), 2)
                    entry["std"] = round(clean.std(), 2)

            metrics.append(entry)

        st.dataframe(pd.DataFrame(metrics), use_container_width=True, hide_index=True)

        numeric_cols = [
            c
            for c in profile_df.columns
            if pd.api.types.is_numeric_dtype(profile_df[c]) and profile_df[c].notna().any()
        ]
        categorical_cols = [
            c
            for c in profile_df.columns
            if not pd.api.types.is_numeric_dtype(profile_df[c])
            and profile_df[c].nunique() <= 50
            and profile_df[c].notna().any()
        ]

        if numeric_cols:
            st.subheader("Distributions")
            dist_col = st.selectbox("Column", numeric_cols, key="dist_col")
            if dist_col:
                fig = px.histogram(
                    profile_df, x=dist_col, nbins=40, title=f"Distribution of {dist_col}"
                )
                st.plotly_chart(fig, use_container_width=True)

        if categorical_cols:
            st.subheader("Top Values")
            cat_col = st.selectbox("Column", categorical_cols, key="cat_col")
            if cat_col:
                top = profile_df[cat_col].value_counts().head(20).reset_index()
                top.columns = ["value", "count"]
                fig = px.bar(top, x="value", y="count", title=f"Top values for {cat_col}")
                st.plotly_chart(fig, use_container_width=True)

with tab_chart:
    chart_df = con.execute(f"SELECT * FROM {qname} LIMIT 50000").fetchdf()

    if chart_df.empty:
        st.info("Table is empty.")
    else:
        chart_cols = list(chart_df.columns)
        date_cols = [
            c
            for c in chart_cols
            if pd.api.types.is_datetime64_any_dtype(chart_df[c])
            or ("date" in c.lower() and not pd.api.types.is_numeric_dtype(chart_df[c]))
        ]

        col1, col2, col3 = st.columns(3)
        with col1:
            x_col = st.selectbox("X axis", chart_cols, key="chart_x")
        with col2:
            y_col = st.selectbox("Y axis", ["(count)"] + chart_cols, key="chart_y")
        with col3:
            color_col = st.selectbox("Color", ["(none)"] + chart_cols, key="chart_color")

        plot_df = chart_df.copy()

        if y_col == "(count)":
            agg_df = plot_df.groupby(x_col).size().reset_index(name="count")
            x = x_col
            y = "count"
        else:
            agg_df = plot_df
            x = x_col
            y = y_col

        is_x_date = x_col in date_cols or pd.api.types.is_datetime64_any_dtype(plot_df[x_col])
        is_x_numeric = pd.api.types.is_numeric_dtype(plot_df[x_col])
        is_y_numeric = pd.api.types.is_numeric_dtype(agg_df[y]) if y in agg_df.columns else False

        if is_x_date:
            fig = px.line(agg_df, x=x, y=y, color=color_col if color_col != "(none)" else None)
        elif is_x_numeric and is_y_numeric:
            fig = px.scatter(
                agg_df.sample(min(5000, len(agg_df))),
                x=x,
                y=y,
                color=color_col if color_col != "(none)" else None,
                opacity=0.5,
            )
        else:
            fig = px.bar(agg_df, x=x, y=y, color=color_col if color_col != "(none)" else None)

        fig.update_layout(title=f"{y} by {x}")
        st.plotly_chart(fig, use_container_width=True)

with tab_sql:
    st.subheader("SQL Query")
    st.caption(f"Connected to `{db_path.name}` (read-only)")

    default_query = f"SELECT * FROM {qname} LIMIT 100"
    sql = st.text_area("Query", value=default_query, height=200)

    if st.button("Run Query", type="primary"):
        try:
            result_df = con.execute(sql).fetchdf()
            st.dataframe(result_df, use_container_width=True, hide_index=True)

            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                csv_result = result_df.to_csv(index=False)
                st.download_button("Download CSV", csv_result, "query_result.csv", "text/csv")
            with col_dl2:
                buf = io.BytesIO()
                result_df.to_parquet(buf, index=False)
                st.download_button("Download Parquet", buf.getvalue(), "query_result.parquet")

            st.caption(f"{len(result_df)} rows")
        except Exception as e:
            st.error(str(e))

con.close()
