"""Streamlit Dashboard — Nursing Home Inspection & Deficiency Tracker.

Interactive dashboard with 7 sections: National Overview, Deficiency Explorer,
Ownership Analysis, Penalty Tracker, Quality Comparison, Geographic Map,
and Facility Deep Dive.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "nursing_homes.db"


# ── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_resource
def get_db():
    """Get a cached database connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=300)
def run_query(sql: str, params=()) -> pd.DataFrame:
    """Run a SQL query and return a DataFrame."""
    conn = get_db()
    return pd.read_sql_query(sql, conn, params=params)


def format_currency(val):
    """Format a number as currency."""
    if val is None or pd.isna(val):
        return "—"
    if val >= 1_000_000_000:
        return f"${val/1e9:.1f}B"
    if val >= 1_000_000:
        return f"${val/1e6:.1f}M"
    if val >= 1_000:
        return f"${val/1e3:.0f}K"
    return f"${val:,.0f}"


# ── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Nursing Home Tracker",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏥 Nursing Home Tracker")
    st.caption("CMS Inspection & Deficiency Data")

    page = st.radio(
        "Navigate",
        [
            "National Overview",
            "Deficiency Explorer",
            "Ownership Analysis",
            "Penalty Tracker",
            "Quality Comparison",
            "Geographic Map",
            "Facility Deep Dive",
        ],
    )

    st.divider()

    # State filter
    try:
        states_df = run_query(
            "SELECT DISTINCT provider_state FROM providers WHERE provider_state IS NOT NULL ORDER BY provider_state"
        )
        all_states = states_df["provider_state"].tolist()
        selected_states = st.multiselect("Filter by State", all_states, default=[])
    except Exception:
        selected_states = []
        all_states = []

    st.divider()
    st.markdown(
        "**Built by [Nathan Goldberg](https://www.linkedin.com/in/nathanmauricegoldberg/)**"
    )
    st.caption("nathanmauricegoldberg@gmail.com")


def state_filter_sql(alias="p"):
    """Build a SQL WHERE clause for state filtering."""
    if not selected_states:
        return ""
    placeholders = ",".join(["?"] * len(selected_states))
    return f" AND {alias}.provider_state IN ({placeholders})"


def state_filter_params():
    return tuple(selected_states) if selected_states else ()


# ── Check DB ─────────────────────────────────────────────────────────────────

if not DB_PATH.exists():
    st.error("Database not found. Run `python -m src.cli pipeline` first.")
    st.stop()


# ── Pages ────────────────────────────────────────────────────────────────────

if page == "National Overview":
    st.header("National Overview")

    # KPI cards
    try:
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        total = run_query(f"SELECT COUNT(*) as n FROM providers p WHERE 1=1{sfilt}", sparams)
        total_facilities = int(total["n"].iloc[0]) if not total.empty else 0

        avg_r = run_query(
            f"SELECT AVG(overall_rating) as avg_r FROM providers p WHERE overall_rating IS NOT NULL{sfilt}",
            sparams,
        )
        avg_rating = avg_r["avg_r"].iloc[0] if not avg_r.empty else None

        total_pen = run_query(
            f"SELECT SUM(pen.fine_amount) as total FROM penalties pen JOIN providers p ON pen.federal_provider_number = p.federal_provider_number WHERE 1=1{sfilt}",
            sparams,
        )
        total_fines = total_pen["total"].iloc[0] if not total_pen.empty else None

        pe = run_query(
            f"SELECT COUNT(*) as n FROM providers p WHERE owner_classification = 'private_equity'{sfilt}",
            sparams,
        )
        pe_count = int(pe["n"].iloc[0]) if not pe.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Facilities", f"{total_facilities:,}")
        c2.metric("Avg Star Rating", f"{avg_rating:.2f}/5" if avg_rating and not pd.isna(avg_rating) else "—")
        c3.metric("Total Fines", format_currency(total_fines))
        c4.metric("PE-Owned", f"{pe_count:,}")
    except Exception as e:
        st.warning(f"Could not load metrics: {e}")

    st.divider()

    # Rating distribution
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Star Rating Distribution")
        try:
            df = run_query(
                f"SELECT overall_rating, COUNT(*) as count FROM providers p WHERE overall_rating IS NOT NULL{sfilt} GROUP BY overall_rating ORDER BY overall_rating",
                sparams,
            )
            fig = px.bar(df, x="overall_rating", y="count", labels={"overall_rating": "Stars", "count": "Facilities"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No rating data available.")

    with col2:
        st.subheader("Ownership Classification")
        try:
            df = run_query(
                f"SELECT owner_classification, COUNT(*) as count FROM providers p WHERE owner_classification IS NOT NULL{sfilt} GROUP BY owner_classification ORDER BY count DESC",
                sparams,
            )
            fig = px.pie(df, names="owner_classification", values="count", hole=0.4)
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.info("No ownership data available.")

    # Facilities by state
    st.subheader("Facilities by State")
    try:
        df = run_query(
            "SELECT provider_state, COUNT(*) as count FROM providers WHERE provider_state IS NOT NULL GROUP BY provider_state ORDER BY count DESC"
        )
        fig = px.bar(df.head(20), x="provider_state", y="count", labels={"provider_state": "State", "count": "Facilities"})
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.info("No state data available.")


elif page == "Deficiency Explorer":
    st.header("Deficiency Explorer")

    try:
        sfilt = state_filter_sql("d")
        sparams = state_filter_params()

        # Severity filter
        severity_options = ["All", "A-C (Minimal)", "D-F (More than minimal)", "G-I (Actual harm)", "J-L (Immediate jeopardy)"]
        severity_choice = st.selectbox("Severity Level", severity_options)

        sev_filter = ""
        if severity_choice == "A-C (Minimal)":
            sev_filter = " AND d.scope_severity_code IN ('A','B','C')"
        elif severity_choice == "D-F (More than minimal)":
            sev_filter = " AND d.scope_severity_code IN ('D','E','F')"
        elif severity_choice == "G-I (Actual harm)":
            sev_filter = " AND d.scope_severity_code IN ('G','H','I')"
        elif severity_choice == "J-L (Immediate jeopardy)":
            sev_filter = " AND d.scope_severity_code IN ('J','K','L')"

        total_def = run_query(
            f"SELECT COUNT(*) as n FROM health_deficiencies d WHERE 1=1{sfilt}{sev_filter}",
            sparams,
        )
        def_count = int(total_def["n"].iloc[0]) if not total_def.empty else 0
        st.metric("Total Deficiencies", f"{def_count:,}")

        # Severity distribution
        st.subheader("Severity Distribution")
        df = run_query(
            f"SELECT scope_severity_code, COUNT(*) as count FROM health_deficiencies d WHERE scope_severity_code IS NOT NULL{sfilt} GROUP BY scope_severity_code ORDER BY scope_severity_code",
            sparams,
        )
        if not df.empty:
            fig = px.bar(df, x="scope_severity_code", y="count", color="scope_severity_code",
                         labels={"scope_severity_code": "Severity Code", "count": "Count"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Recent deficiencies table
        st.subheader("Recent Deficiencies")
        df = run_query(
            f"""SELECT d.federal_provider_number, d.provider_name, d.provider_state,
                       d.survey_date, d.deficiency_tag_number, d.scope_severity_code,
                       d.deficiency_description
                FROM health_deficiencies d
                WHERE 1=1{sfilt}{sev_filter}
                ORDER BY d.survey_date DESC
                LIMIT 100""",
            sparams,
        )
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No deficiency records found.")
    except Exception as e:
        st.warning(f"Error loading deficiency data: {e}")


elif page == "Ownership Analysis":
    st.header("Ownership Analysis")

    try:
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        # Classification comparison
        st.subheader("Quality by Ownership Type")
        df = run_query(
            f"""SELECT owner_classification,
                       COUNT(*) as facilities,
                       AVG(overall_rating) as avg_rating,
                       AVG(quality_score) as avg_quality_score
                FROM providers p
                WHERE owner_classification IS NOT NULL{sfilt}
                GROUP BY owner_classification
                ORDER BY avg_rating""",
            sparams,
        )

        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(df, x="owner_classification", y="avg_rating",
                             color="owner_classification",
                             labels={"owner_classification": "Owner Type", "avg_rating": "Avg Star Rating"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(df, x="owner_classification", y="facilities",
                             color="owner_classification",
                             labels={"owner_classification": "Owner Type", "facilities": "Count"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df, use_container_width=True, hide_index=True)

        # PE-owned facilities detail
        st.subheader("PE-Owned Facilities")
        pe_df = run_query(
            f"""SELECT p.provider_name, p.provider_state, p.overall_rating,
                       p.number_of_certified_beds, o.owner_name, o.owner_classification
                FROM providers p
                JOIN ownership o ON p.federal_provider_number = o.federal_provider_number
                WHERE o.owner_classification = 'private_equity'{sfilt}
                ORDER BY p.overall_rating ASC
                LIMIT 50""",
            sparams,
        )
        if not pe_df.empty:
            st.dataframe(pe_df, use_container_width=True, hide_index=True)
        else:
            st.info("No PE-owned facilities found.")
    except Exception as e:
        st.warning(f"Error loading ownership data: {e}")


elif page == "Penalty Tracker":
    st.header("Penalty Tracker")

    try:
        sfilt = state_filter_sql("p")
        sparams = state_filter_params()

        # KPI
        total_fines = run_query(
            f"SELECT SUM(pen.fine_amount) as total, COUNT(*) as count FROM penalties pen JOIN providers p ON pen.federal_provider_number = p.federal_provider_number WHERE 1=1{sfilt}",
            sparams,
        )
        c1, c2 = st.columns(2)
        if not total_fines.empty:
            c1.metric("Total Fines", format_currency(total_fines["total"].iloc[0]))
            c2.metric("Total Penalties", f"{int(total_fines['count'].iloc[0]):,}")
        else:
            c1.metric("Total Fines", "$0")
            c2.metric("Total Penalties", "0")

        # Top penalized
        st.subheader("Top 20 Most Penalized Facilities")
        df = run_query(
            f"""SELECT pr.provider_name, pr.provider_state, pr.overall_rating,
                       COUNT(pen.id) as penalty_count, SUM(pen.fine_amount) as total_fines
                FROM penalties pen
                JOIN providers pr ON pen.federal_provider_number = pr.federal_provider_number
                JOIN providers p ON pen.federal_provider_number = p.federal_provider_number
                WHERE 1=1{sfilt}
                GROUP BY pen.federal_provider_number
                ORDER BY total_fines DESC
                LIMIT 20""",
            sparams,
        )
        if not df.empty:
            fig = px.bar(df, x="provider_name", y="total_fines",
                         hover_data=["provider_state", "overall_rating", "penalty_count"],
                         labels={"provider_name": "Facility", "total_fines": "Total Fines ($)"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Penalties by type
        st.subheader("Penalties by Type")
        df = run_query(
            f"""SELECT pen.penalty_type, COUNT(*) as count, SUM(pen.fine_amount) as total
                FROM penalties pen
                JOIN providers p ON pen.federal_provider_number = p.federal_provider_number
                WHERE pen.penalty_type IS NOT NULL{sfilt}
                GROUP BY pen.penalty_type
                ORDER BY total DESC""",
            sparams,
        )
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Error loading penalty data: {e}")


elif page == "Quality Comparison":
    st.header("Quality Comparison")

    try:
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        # Rating comparison by ownership type
        st.subheader("Star Ratings by Ownership Type")
        df = run_query(
            f"""SELECT owner_classification,
                       AVG(overall_rating) as avg_overall,
                       AVG(health_inspection_rating) as avg_health,
                       AVG(staffing_rating) as avg_staffing,
                       AVG(quality_measure_rating) as avg_quality
                FROM providers p
                WHERE owner_classification IS NOT NULL AND overall_rating IS NOT NULL{sfilt}
                GROUP BY owner_classification""",
            sparams,
        )

        if not df.empty:
            melted = df.melt(id_vars="owner_classification",
                             value_vars=["avg_overall", "avg_health", "avg_staffing", "avg_quality"],
                             var_name="Rating Type", value_name="Average")
            melted["Rating Type"] = melted["Rating Type"].str.replace("avg_", "").str.title()
            fig = px.bar(melted, x="owner_classification", y="Average", color="Rating Type",
                         barmode="group", labels={"owner_classification": "Owner Type"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Quality score distribution
        st.subheader("Data Quality Score Distribution")
        df = run_query(
            f"""SELECT
                    CASE
                        WHEN quality_score >= 0.9 THEN '0.9-1.0'
                        WHEN quality_score >= 0.7 THEN '0.7-0.9'
                        WHEN quality_score >= 0.5 THEN '0.5-0.7'
                        WHEN quality_score >= 0.3 THEN '0.3-0.5'
                        ELSE '0.0-0.3'
                    END as score_range,
                    COUNT(*) as count
                FROM providers p
                WHERE quality_score IS NOT NULL{sfilt}
                GROUP BY score_range
                ORDER BY score_range""",
            sparams,
        )
        if not df.empty:
            fig = px.bar(df, x="score_range", y="count",
                         labels={"score_range": "Quality Score Range", "count": "Facilities"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # State comparison
        st.subheader("Average Rating by State")
        df = run_query(
            "SELECT provider_state, AVG(overall_rating) as avg_rating, COUNT(*) as facilities FROM providers WHERE overall_rating IS NOT NULL AND provider_state IS NOT NULL GROUP BY provider_state ORDER BY avg_rating DESC"
        )
        if not df.empty:
            fig = px.bar(df, x="provider_state", y="avg_rating",
                         hover_data=["facilities"],
                         labels={"provider_state": "State", "avg_rating": "Avg Rating"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Error loading quality data: {e}")


elif page == "Geographic Map":
    st.header("Geographic Map")

    try:
        metric = st.selectbox("Color by", ["Average Rating", "Facility Count", "Total Fines", "PE-Owned %"])

        if metric == "Average Rating":
            df = run_query(
                "SELECT provider_state as state, AVG(overall_rating) as value FROM providers WHERE overall_rating IS NOT NULL GROUP BY provider_state"
            )
            color_label = "Avg Rating"
        elif metric == "Facility Count":
            df = run_query(
                "SELECT provider_state as state, COUNT(*) as value FROM providers GROUP BY provider_state"
            )
            color_label = "Facilities"
        elif metric == "Total Fines":
            df = run_query(
                "SELECT p.provider_state as state, SUM(pen.fine_amount) as value FROM penalties pen JOIN providers p ON pen.federal_provider_number = p.federal_provider_number GROUP BY p.provider_state"
            )
            color_label = "Total Fines ($)"
        else:
            df = run_query("""
                SELECT provider_state as state,
                       100.0 * SUM(CASE WHEN owner_classification = 'private_equity' THEN 1 ELSE 0 END) / COUNT(*) as value
                FROM providers
                WHERE provider_state IS NOT NULL
                GROUP BY provider_state
            """)
            color_label = "PE-Owned %"

        if not df.empty:
            fig = px.choropleth(
                df,
                locations="state",
                locationmode="USA-states",
                color="value",
                scope="usa",
                color_continuous_scale="RdYlGn" if metric == "Average Rating" else "Reds",
                labels={"value": color_label},
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                geo=dict(bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0, r=0, t=0, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No geographic data available.")
    except Exception as e:
        st.warning(f"Error loading map data: {e}")


elif page == "Facility Deep Dive":
    st.header("Facility Deep Dive")

    try:
        # Search
        search = st.text_input("Search by facility name or provider number")

        if search:
            results = run_query(
                "SELECT federal_provider_number, provider_name, provider_state, overall_rating FROM providers WHERE provider_name LIKE ? OR federal_provider_number LIKE ? LIMIT 20",
                (f"%{search}%", f"%{search}%"),
            )

            if results.empty:
                st.info("No facilities found.")
            else:
                def _format_provider(x):
                    match = results[results["federal_provider_number"] == x]
                    if not match.empty:
                        return f"{match['provider_name'].iloc[0]} ({x})"
                    return str(x)

                selected = st.selectbox(
                    "Select facility",
                    results["federal_provider_number"].tolist(),
                    format_func=_format_provider,
                )

                if selected:
                    # Provider info
                    prov = run_query("SELECT * FROM providers WHERE federal_provider_number = ?", (selected,))
                    if not prov.empty:
                        r = prov.iloc[0]
                        st.subheader(f"{r['provider_name']}")
                        st.caption(f"{r.get('provider_city', '')} {r.get('provider_state', '')} | ID: {selected}")

                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Overall Rating", f"{r.get('overall_rating', '—')}/5")
                        c2.metric("Health Rating", f"{r.get('health_inspection_rating', '—')}/5")
                        c3.metric("Staffing Rating", f"{r.get('staffing_rating', '—')}/5")
                        c4.metric("Beds", f"{r.get('number_of_certified_beds', '—')}")

                        qs = r.get('quality_score', 0)
                        st.metric("Quality Score", f"{qs:.2f}" if qs is not None and not pd.isna(qs) else "—")
                        st.caption(f"Owner Classification: {r.get('owner_classification', 'Unknown')}")

                    # Deficiencies
                    st.subheader("Deficiency History")
                    defs = run_query(
                        "SELECT survey_date, deficiency_tag_number, scope_severity_code, deficiency_description FROM health_deficiencies WHERE federal_provider_number = ? ORDER BY survey_date DESC",
                        (selected,),
                    )
                    if not defs.empty:
                        st.dataframe(defs, use_container_width=True, hide_index=True)
                    else:
                        st.info("No deficiency records.")

                    # Penalties
                    st.subheader("Penalties")
                    pens = run_query(
                        "SELECT penalty_date, penalty_type, fine_amount, penalty_status FROM penalties WHERE federal_provider_number = ? ORDER BY penalty_date DESC",
                        (selected,),
                    )
                    if not pens.empty:
                        st.dataframe(pens, use_container_width=True, hide_index=True)
                    else:
                        st.info("No penalty records.")

                    # Ownership
                    st.subheader("Ownership")
                    owns = run_query(
                        "SELECT owner_name, owner_type, owner_percentage, role_description, owner_classification FROM ownership WHERE federal_provider_number = ? ORDER BY owner_percentage DESC",
                        (selected,),
                    )
                    if not owns.empty:
                        st.dataframe(owns, use_container_width=True, hide_index=True)
                    else:
                        st.info("No ownership records.")
        else:
            st.info("Enter a facility name or CMS provider number to search.")
    except Exception as e:
        st.warning(f"Error: {e}")
