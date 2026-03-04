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

def _table_exists(conn, name):
    try:
        r = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        return r is not None
    except Exception:
        return False


def _safe_query(sql, conn, params=()):
    try:
        return pd.read_sql_query(sql, conn, params=params if params else None)
    except Exception:
        return pd.DataFrame()


def _safe_fetchone(conn, sql, params=(), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else default
    except Exception:
        return default


@st.cache_resource
def get_db():
    """Get a cached database connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=300)
def run_query(sql: str, params=()) -> pd.DataFrame:
    """Run a SQL query and return a DataFrame. Returns empty on error."""
    try:
        conn = get_db()
        return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        return pd.DataFrame()


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
            "Owner Portfolio",
            "Ownership Changes",
            "Penalty Tracker",
            "Staffing Analysis",
            "Financial Analysis",
            "Related Party Transactions",
            "California Financial Detail",
            "Chain Report Cards",
            "Star Rating Reality Check",
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
        "**Built by [Nathan Goldberg](https://www.linkedin.com/in/nathan-goldberg-62a44522a/)**"
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

_db_available = DB_PATH.exists()
if _db_available:
    try:
        _conn_check = get_db()
        _db_available = _table_exists(_conn_check, "providers")
    except Exception:
        _db_available = False

if not _db_available:
    st.warning("No data loaded. Run `python -m src.cli pipeline` first to populate the database.")


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

        reit = run_query(
            f"SELECT COUNT(*) as n FROM providers p WHERE owner_classification = 'reit'{sfilt}",
            sparams,
        )
        reit_count = int(reit["n"].iloc[0]) if not reit.empty else 0

        total_def = run_query(
            f"SELECT COUNT(*) as n FROM health_deficiencies d JOIN providers p ON d.federal_provider_number = p.federal_provider_number WHERE 1=1{sfilt}",
            sparams,
        )
        def_count = int(total_def["n"].iloc[0]) if not total_def.empty else 0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Facilities", f"{total_facilities:,}")
        c2.metric("Avg Star Rating", f"{avg_rating:.2f}/5" if avg_rating and not pd.isna(avg_rating) else "—")
        c3.metric("Total Fines", format_currency(total_fines))
        c4.metric("PE-Owned", f"{pe_count:,}")
        c5.metric("REIT-Owned", f"{reit_count:,}")
        c6.metric("Deficiencies", f"{def_count:,}")
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
            f"SELECT provider_state, COUNT(*) as count FROM providers p WHERE provider_state IS NOT NULL{sfilt} GROUP BY provider_state ORDER BY count DESC",
            sparams,
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

        # Severity distribution (respects severity filter)
        st.subheader("Severity Distribution")
        df = run_query(
            f"SELECT scope_severity_code, COUNT(*) as count FROM health_deficiencies d WHERE scope_severity_code IS NOT NULL{sfilt}{sev_filter} GROUP BY scope_severity_code ORDER BY scope_severity_code",
            sparams,
        )
        if not df.empty:
            fig = px.bar(df, x="scope_severity_code", y="count", color="scope_severity_code",
                         labels={"scope_severity_code": "Severity Code", "count": "Count"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Top F-tags
        st.subheader("Top 20 Most Common F-Tags")
        ftag_df = run_query(
            f"""SELECT d.deficiency_tag_number as tag, d.deficiency_description as description,
                       COUNT(*) as count
                FROM health_deficiencies d
                WHERE d.deficiency_tag_number IS NOT NULL{sfilt}{sev_filter}
                GROUP BY d.deficiency_tag_number, d.deficiency_description
                ORDER BY count DESC
                LIMIT 20""",
            sparams,
        )
        if not ftag_df.empty:
            fig = px.bar(ftag_df, x="tag", y="count", hover_data=["description"],
                         labels={"tag": "F-Tag", "count": "Citations"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Deficiency category breakdown
        st.subheader("Deficiency Categories")
        cat_df = run_query(
            f"""SELECT d.deficiency_category as category, COUNT(*) as count
                FROM health_deficiencies d
                WHERE d.deficiency_category IS NOT NULL{sfilt}{sev_filter}
                GROUP BY d.deficiency_category
                ORDER BY count DESC""",
            sparams,
        )
        if not cat_df.empty:
            fig = px.pie(cat_df, names="category", values="count", hole=0.4)
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
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
                       p.number_of_certified_beds
                FROM providers p
                WHERE p.owner_classification = 'private_equity'{sfilt}
                ORDER BY p.overall_rating ASC
                LIMIT 50""",
            sparams,
        )
        if not pe_df.empty:
            st.dataframe(pe_df, use_container_width=True, hide_index=True)
        else:
            st.info("No PE-owned facilities found.")

        # ── Shared Address Networks ──
        st.divider()
        st.subheader("Shared Address Networks")
        st.caption(
            "Clusters of distinct owner LLCs sharing the same registered address — "
            "a common PE structure where separate LLCs are created for each facility "
            "but all route back to the same principal office."
        )

        network_df = run_query("""
            SELECT network_id, owner_count, facility_count, normalized_address,
                   owner_names, states, has_pe_flag, has_reit_flag, avg_overall_rating
            FROM address_networks
            ORDER BY owner_count DESC
            LIMIT 50
        """)

        if not network_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Address Networks", f"{len(network_df):,}")
            c2.metric("PE-Linked Networks", int(network_df["has_pe_flag"].sum()))
            c3.metric("Total Facilities in Networks", int(network_df["facility_count"].sum()))

            # Distribution chart
            fig = px.histogram(network_df, x="owner_count",
                               title="Network Size Distribution (# owners at same address)",
                               labels={"owner_count": "Owners at Address", "count": "Networks"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                network_df[["network_id", "owner_count", "facility_count", "owner_names",
                            "has_pe_flag", "has_reit_flag", "avg_overall_rating"]],
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Run shared address detection to populate. Use `python -m src.cli normalize`.")

    except Exception as e:
        st.warning(f"Error loading ownership data: {e}")


elif page == "Owner Portfolio":
    st.header("Owner Portfolio View")
    st.caption("Look up any owner/chain and see their full portfolio of facilities with aggregate quality metrics.")

    try:
        search = st.text_input("Search by owner name or chain name")
        if search:
            # Search owner_profiles first
            profiles = run_query(
                """SELECT owner_name, classification, facility_count,
                          avg_overall_rating, avg_health_inspection_rating,
                          avg_staffing_rating, total_penalties, total_fines,
                          avg_total_nurse_staffing_hours, avg_deficiency_count,
                          total_rpt_spending, states, is_pe, is_reit
                   FROM owner_profiles
                   WHERE owner_name LIKE ?
                   ORDER BY facility_count DESC
                   LIMIT 20""",
                (f"%{search.upper()}%",),
            )

            if not profiles.empty:
                selected_owner = st.selectbox(
                    "Select owner",
                    profiles["owner_name"].tolist(),
                    format_func=lambda x: f"{x} ({profiles[profiles['owner_name']==x]['facility_count'].iloc[0]} facilities)"
                )

                if selected_owner:
                    row = profiles[profiles["owner_name"] == selected_owner].iloc[0]
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Facilities", f"{int(row['facility_count']):,}")
                    c2.metric("Avg Rating", f"{row['avg_overall_rating']:.1f}/5" if row['avg_overall_rating'] else "—")
                    c3.metric("Total Fines", format_currency(row["total_fines"]))
                    c4.metric("Total Penalties", f"{int(row['total_penalties']):,}")

                    c5, c6, c7, c8 = st.columns(4)
                    c5.metric("Classification", row["classification"] or "Unknown")
                    c6.metric("Avg Staffing Hrs", f"{row['avg_total_nurse_staffing_hours']:.2f}" if row['avg_total_nurse_staffing_hours'] else "—")
                    c7.metric("Avg Deficiencies", f"{row['avg_deficiency_count']:.1f}" if row['avg_deficiency_count'] else "—")
                    c8.metric("RPT Spending", format_currency(row["total_rpt_spending"]))

                    # Show individual facilities
                    st.subheader("Facilities")
                    facilities = run_query(
                        """SELECT p.federal_provider_number, p.provider_name, p.provider_state,
                                  p.overall_rating, p.health_inspection_rating,
                                  p.staffing_rating, p.number_of_certified_beds,
                                  p.reported_total_nurse_staffing_hours
                           FROM ownership o
                           JOIN providers p ON o.federal_provider_number = p.federal_provider_number
                           WHERE o.normalized_owner_name = ?
                           ORDER BY p.overall_rating ASC""",
                        (selected_owner,),
                    )
                    if not facilities.empty:
                        st.dataframe(facilities, use_container_width=True, hide_index=True)
            else:
                # Also try chain name from providers
                chain_results = run_query(
                    """SELECT chain_name, COUNT(*) as facilities, AVG(overall_rating) as avg_rating
                       FROM providers WHERE chain_name LIKE ? AND chain_name IS NOT NULL
                       GROUP BY chain_name ORDER BY facilities DESC LIMIT 20""",
                    (f"%{search}%",),
                )
                if not chain_results.empty:
                    st.subheader("Chain Results")
                    st.dataframe(chain_results, use_container_width=True, hide_index=True)
                else:
                    st.info("No matching owners or chains found.")
        else:
            # Show top owners by facility count
            st.subheader("Top 20 Owners by Facility Count")
            top = run_query(
                """SELECT owner_name, classification, facility_count,
                          avg_overall_rating, total_fines, total_penalties, is_pe, is_reit
                   FROM owner_profiles
                   ORDER BY facility_count DESC LIMIT 20"""
            )
            if not top.empty:
                st.dataframe(top, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Error loading owner portfolio: {e}")


elif page == "Ownership Changes":
    st.header("Ownership Changes (CHOW) Timeline")

    try:
        sfilt = state_filter_sql("p")
        sparams = state_filter_params()

        # KPIs
        kpis = run_query(
            f"""SELECT COUNT(*) as total_changes,
                       COUNT(DISTINCT oc.federal_provider_number) as facilities_changed,
                       MIN(oc.change_date) as earliest,
                       MAX(oc.change_date) as latest
                FROM ownership_changes oc
                JOIN providers p ON oc.federal_provider_number = p.federal_provider_number
                WHERE 1=1{sfilt}""",
            sparams,
        )
        if not kpis.empty:
            row = kpis.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Ownership Changes", f"{int(row['total_changes']):,}")
            c2.metric("Facilities Changed", f"{int(row['facilities_changed']):,}")
            c3.metric("Earliest Change", str(row["earliest"])[:10] if row["earliest"] else "—")
            c4.metric("Latest Change", str(row["latest"])[:10] if row["latest"] else "—")

        st.divider()

        # Volume over time
        st.subheader("Ownership Change Volume Over Time")
        df = run_query(
            f"""SELECT substr(oc.change_date, 1, 7) as month, COUNT(*) as changes
                FROM ownership_changes oc
                JOIN providers p ON oc.federal_provider_number = p.federal_provider_number
                WHERE oc.change_date IS NOT NULL{sfilt}
                GROUP BY month ORDER BY month""",
            sparams,
        )
        if not df.empty:
            fig = px.bar(df, x="month", y="changes",
                         labels={"month": "Month", "changes": "Ownership Changes"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Top buyers
        st.subheader("Top Buyers (Most Acquisitions)")
        buyers = run_query(
            f"""SELECT oc.new_owner, COUNT(*) as acquisitions
                FROM ownership_changes oc
                JOIN providers p ON oc.federal_provider_number = p.federal_provider_number
                WHERE oc.new_owner IS NOT NULL{sfilt}
                GROUP BY oc.new_owner ORDER BY acquisitions DESC LIMIT 20""",
            sparams,
        )
        if not buyers.empty:
            st.dataframe(buyers, use_container_width=True, hide_index=True)

        # Top sellers
        st.subheader("Top Sellers (Most Divestitures)")
        sellers = run_query(
            f"""SELECT oc.previous_owner, COUNT(*) as sales
                FROM ownership_changes oc
                JOIN providers p ON oc.federal_provider_number = p.federal_provider_number
                WHERE oc.previous_owner IS NOT NULL{sfilt}
                GROUP BY oc.previous_owner ORDER BY sales DESC LIMIT 20""",
            sparams,
        )
        if not sellers.empty:
            st.dataframe(sellers, use_container_width=True, hide_index=True)

        # Recent changes
        st.subheader("Recent Ownership Changes")
        recent = run_query(
            f"""SELECT oc.change_date, p.provider_name, p.provider_state,
                       oc.previous_owner, oc.new_owner, oc.change_type
                FROM ownership_changes oc
                JOIN providers p ON oc.federal_provider_number = p.federal_provider_number
                WHERE 1=1{sfilt}
                ORDER BY oc.change_date DESC LIMIT 100""",
            sparams,
        )
        if not recent.empty:
            st.dataframe(recent, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"Error loading ownership change data: {e}")


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
            f"""SELECT p.provider_name, p.provider_state, p.overall_rating,
                       COUNT(pen.id) as penalty_count, SUM(pen.fine_amount) as total_fines
                FROM penalties pen
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


elif page == "Staffing Analysis":
    st.header("Staffing Analysis")

    try:
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        # KPIs
        kpis = run_query(f"""
            SELECT
                AVG(reported_total_nurse_staffing_hours) as avg_total_hours,
                AVG(reported_rn_staffing_hours) as avg_rn_hours,
                AVG(total_nursing_staff_turnover) as avg_turnover,
                AVG(rn_turnover) as avg_rn_turnover
            FROM providers p
            WHERE reported_total_nurse_staffing_hours IS NOT NULL{sfilt}
        """, sparams)

        if not kpis.empty:
            row = kpis.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Total Nurse Hrs/Resident/Day", f"{row['avg_total_hours']:.2f}" if row['avg_total_hours'] else "—")
            c2.metric("Avg RN Hrs/Resident/Day", f"{row['avg_rn_hours']:.2f}" if row['avg_rn_hours'] else "—")
            c3.metric("Avg Nursing Turnover %", f"{row['avg_turnover']:.1f}%" if row['avg_turnover'] else "—")
            c4.metric("Avg RN Turnover %", f"{row['avg_rn_turnover']:.1f}%" if row['avg_rn_turnover'] else "—")

        st.divider()

        # Staffing by ownership type
        st.subheader("Staffing Hours by Ownership Type")
        st.caption("Hours per resident per day. Research shows PE-owned facilities average lower staffing hours.")
        df = run_query(f"""
            SELECT owner_classification,
                   AVG(reported_total_nurse_staffing_hours) as avg_total_hours,
                   AVG(reported_rn_staffing_hours) as avg_rn_hours,
                   AVG(reported_nurse_aide_staffing_hours) as avg_cna_hours,
                   AVG(reported_lpn_staffing_hours) as avg_lpn_hours,
                   COUNT(*) as facilities
            FROM providers p
            WHERE owner_classification IS NOT NULL
              AND reported_total_nurse_staffing_hours IS NOT NULL{sfilt}
            GROUP BY owner_classification
            ORDER BY avg_total_hours DESC
        """, sparams)

        if not df.empty:
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(df, x="owner_classification", y="avg_total_hours",
                             color="owner_classification",
                             labels={"owner_classification": "Owner Type",
                                     "avg_total_hours": "Avg Total Nurse Hrs/Resident/Day"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                melted = df.melt(id_vars="owner_classification",
                                 value_vars=["avg_rn_hours", "avg_lpn_hours", "avg_cna_hours"],
                                 var_name="Staff Type", value_name="Hours")
                melted["Staff Type"] = melted["Staff Type"].str.replace("avg_", "").str.replace("_hours", "").str.upper()
                fig = px.bar(melted, x="owner_classification", y="Hours", color="Staff Type",
                             barmode="stack",
                             labels={"owner_classification": "Owner Type"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df, use_container_width=True, hide_index=True)

        # Turnover by ownership type
        st.subheader("Nursing Staff Turnover by Ownership Type")
        df = run_query(f"""
            SELECT owner_classification,
                   AVG(total_nursing_staff_turnover) as avg_turnover,
                   AVG(rn_turnover) as avg_rn_turnover,
                   AVG(number_of_admin_departures) as avg_admin_departures,
                   COUNT(*) as facilities
            FROM providers p
            WHERE owner_classification IS NOT NULL
              AND total_nursing_staff_turnover IS NOT NULL{sfilt}
            GROUP BY owner_classification
            ORDER BY avg_turnover DESC
        """, sparams)

        if not df.empty:
            fig = px.bar(df, x="owner_classification", y=["avg_turnover", "avg_rn_turnover"],
                         barmode="group",
                         labels={"owner_classification": "Owner Type", "value": "Turnover %"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

        # Staffing vs quality scatter
        st.subheader("Staffing Hours vs. Star Rating")
        df = run_query(f"""
            SELECT overall_rating,
                   AVG(reported_total_nurse_staffing_hours) as avg_hours,
                   COUNT(*) as facilities
            FROM providers p
            WHERE overall_rating IS NOT NULL AND reported_total_nurse_staffing_hours IS NOT NULL{sfilt}
            GROUP BY overall_rating ORDER BY overall_rating
        """, sparams)

        if not df.empty:
            fig = px.bar(df, x="overall_rating", y="avg_hours",
                         hover_data=["facilities"],
                         labels={"overall_rating": "Star Rating", "avg_hours": "Avg Total Nurse Hours/Resident/Day"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"Error loading staffing data: {e}")


elif page == "Financial Analysis":
    st.header("Financial Analysis")

    try:
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        # Check if cost_reports table exists and has data
        has_cost = run_query("SELECT COUNT(*) as n FROM cost_reports")
        cost_count = int(has_cost["n"].iloc[0]) if not has_cost.empty else 0

        if cost_count == 0:
            st.info("No cost report data available. Run `python -m src.cli download-hcris` and `python -m src.cli extract-hcris` to load HCRIS data.")
        else:
            # KPI cards — use latest fiscal year per facility only
            kpis = run_query(f"""
                SELECT
                    COUNT(DISTINCT cr.federal_provider_number) as facilities,
                    AVG(cr.total_revenue) as avg_revenue,
                    AVG(cr.total_expenses) as avg_expenses,
                    AVG(cr.net_income) as avg_net_income,
                    AVG(cr.cost_per_patient_day) as avg_cost_per_day,
                    MAX(cr.fiscal_year) as latest_year
                FROM cost_reports cr
                INNER JOIN (
                    SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                    FROM cost_reports GROUP BY federal_provider_number
                ) latest ON cr.federal_provider_number = latest.federal_provider_number
                       AND cr.fiscal_year = latest.max_fy
                JOIN providers p ON cr.federal_provider_number = p.federal_provider_number
                WHERE cr.total_revenue > 100000{sfilt}
            """, sparams)

            if not kpis.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Facilities w/ Cost Data", f"{int(kpis['facilities'].iloc[0]):,}")
                c2.metric("Avg Net Patient Revenue", format_currency(kpis["avg_revenue"].iloc[0]))
                c3.metric("Avg Operating Expenses", format_currency(kpis["avg_expenses"].iloc[0]))
                c4.metric("Avg Cost/Patient Day", format_currency(kpis["avg_cost_per_day"].iloc[0]))
                st.caption("Based on each facility's most recent cost report (revenue > $100K). Revenue = Net Patient Revenue per CMS HCRIS.")

            st.divider()

            # Revenue/Expense by ownership type (latest year per facility)
            st.subheader("Net Patient Revenue & Expenses by Ownership Type")
            st.caption("Each facility's most recent cost report. Revenue > $100K filter applied.")
            df = run_query(f"""
                SELECT p.owner_classification,
                       COUNT(*) as facilities,
                       AVG(cr.total_revenue) as avg_revenue,
                       AVG(cr.total_expenses) as avg_expenses,
                       AVG(cr.net_income) as avg_net_income,
                       AVG(cr.cost_per_patient_day) as avg_cost_per_day
                FROM cost_reports cr
                INNER JOIN (
                    SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                    FROM cost_reports GROUP BY federal_provider_number
                ) latest ON cr.federal_provider_number = latest.federal_provider_number
                       AND cr.fiscal_year = latest.max_fy
                JOIN providers p ON cr.federal_provider_number = p.federal_provider_number
                WHERE p.owner_classification IS NOT NULL AND cr.total_revenue > 100000{sfilt}
                GROUP BY p.owner_classification
                ORDER BY avg_revenue DESC
            """, sparams)

            if not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(df, x="owner_classification", y=["avg_revenue", "avg_expenses"],
                                 barmode="group",
                                 labels={"owner_classification": "Owner Type", "value": "Amount ($)",
                                         "avg_revenue": "Avg Revenue", "avg_expenses": "Avg Expenses"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = px.bar(df, x="owner_classification", y="avg_net_income",
                                 color="owner_classification",
                                 labels={"owner_classification": "Owner Type", "avg_net_income": "Avg Net Income ($)"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                st.dataframe(df, use_container_width=True, hide_index=True)

            # Operating margins by ownership type (latest year, excludes extreme outliers)
            st.subheader("Operating Margin by Ownership Type (Latest Year)")
            st.caption("Operating margin = (Revenue − Expenses) / Revenue. Excludes facilities with revenue < $100K or margins beyond ±100%.")
            df = run_query(f"""
                SELECT p.owner_classification,
                       AVG(100.0 * (cr.total_revenue - cr.total_expenses) / cr.total_revenue) as avg_margin,
                       COUNT(*) as facilities
                FROM cost_reports cr
                INNER JOIN (
                    SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                    FROM cost_reports GROUP BY federal_provider_number
                ) latest ON cr.federal_provider_number = latest.federal_provider_number
                       AND cr.fiscal_year = latest.max_fy
                JOIN providers p ON cr.federal_provider_number = p.federal_provider_number
                WHERE p.owner_classification IS NOT NULL
                  AND cr.total_revenue > 100000
                  AND cr.total_expenses IS NOT NULL
                  AND ABS(100.0 * (cr.total_revenue - cr.total_expenses) / cr.total_revenue) <= 100{sfilt}
                GROUP BY p.owner_classification
            """, sparams)

            if not df.empty:
                fig = px.bar(df, x="owner_classification", y="avg_margin",
                             color="owner_classification",
                             labels={"owner_classification": "Owner Type", "avg_margin": "Avg Operating Margin (%)"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            # Cost trends by fiscal year (exclude partial years and outliers)
            st.subheader("Cost Trends Over Time")
            st.caption("Full fiscal years only (2019–2023). Excludes facilities with revenue < $100K.")
            df = run_query(f"""
                SELECT cr.fiscal_year,
                       AVG(cr.total_revenue) as avg_revenue,
                       AVG(cr.total_expenses) as avg_expenses,
                       AVG(cr.cost_per_patient_day) as avg_cost_per_day,
                       COUNT(*) as facilities
                FROM cost_reports cr
                JOIN providers p ON cr.federal_provider_number = p.federal_provider_number
                WHERE cr.fiscal_year IS NOT NULL
                  AND cr.fiscal_year BETWEEN 2019 AND 2023
                  AND cr.total_revenue > 100000{sfilt}
                GROUP BY cr.fiscal_year
                ORDER BY cr.fiscal_year
            """, sparams)

            if not df.empty:
                fig = px.line(df, x="fiscal_year", y=["avg_revenue", "avg_expenses"],
                              labels={"fiscal_year": "Fiscal Year", "value": "Amount ($)",
                                      "avg_revenue": "Avg Revenue", "avg_expenses": "Avg Expenses"},
                              hover_data=["facilities"])
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            # ── RPT Transparency Analysis ──
            st.divider()
            st.subheader("RPT Transparency Analysis")
            st.caption(
                "Flags facilities reporting suspiciously low related-party transactions "
                "relative to their peers. Based on NBER methodology (Gandhi & Olenski, w32258) "
                "finding 68% of nursing home profits hidden through RPT."
            )

            anomaly_df = run_query("""
                SELECT anomaly_type, COUNT(*) as count,
                       SUM(CASE WHEN is_pe_owned = 1 THEN 1 ELSE 0 END) as pe_count
                FROM rpt_anomaly_flags
                GROUP BY anomaly_type
                ORDER BY count DESC
            """)

            if not anomaly_df.empty:
                c1, c2, c3 = st.columns(3)
                zero_row = anomaly_df[anomaly_df["anomaly_type"] == "zero_reporter"]
                under_row = anomaly_df[anomaly_df["anomaly_type"] == "under_reporter"]
                normal_row = anomaly_df[anomaly_df["anomaly_type"] == "normal"]
                c1.metric("Zero Reporters", int(zero_row["count"].iloc[0]) if not zero_row.empty else 0,
                          help="Facilities reporting $0 in related-party transactions despite >$1M revenue")
                c2.metric("Under Reporters", int(under_row["count"].iloc[0]) if not under_row.empty else 0,
                          help="Facilities >1.5 SDs below their peer group median RPT ratio")
                c3.metric("Normal", int(normal_row["count"].iloc[0]) if not normal_row.empty else 0)

                # Zero reporters by ownership type
                zero_by_type = run_query(f"""
                    SELECT p.owner_classification, COUNT(*) as count
                    FROM rpt_anomaly_flags raf
                    JOIN providers p ON raf.federal_provider_number = p.federal_provider_number
                    WHERE raf.anomaly_type IN ('zero_reporter', 'under_reporter')
                    {'AND p.provider_state IN (' + ','.join(['?']*len(selected_states)) + ')' if selected_states else ''}
                    GROUP BY p.owner_classification
                    ORDER BY count DESC
                """, state_filter_params())

                if not zero_by_type.empty:
                    fig = px.bar(zero_by_type, x="owner_classification", y="count",
                                 color="owner_classification",
                                 title="Flagged Facilities by Ownership Type",
                                 labels={"owner_classification": "Owner Type", "count": "Flagged Facilities"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                # Revenue vs RPT scatter
                scatter_df = run_query(f"""
                    SELECT p.provider_name, p.owner_classification,
                           cr.total_revenue, COALESCE(rpt_sum.total_rpt, 0) as total_rpt,
                           raf.anomaly_type
                    FROM rpt_anomaly_flags raf
                    JOIN providers p ON raf.federal_provider_number = p.federal_provider_number
                    JOIN cost_reports cr ON raf.federal_provider_number = cr.federal_provider_number
                    INNER JOIN (
                        SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                        FROM cost_reports GROUP BY federal_provider_number
                    ) latest ON cr.federal_provider_number = latest.federal_provider_number
                           AND cr.fiscal_year = latest.max_fy
                    LEFT JOIN (
                        SELECT federal_provider_number, SUM(amount) as total_rpt
                        FROM related_party_transactions WHERE amount IS NOT NULL
                        GROUP BY federal_provider_number
                    ) rpt_sum ON raf.federal_provider_number = rpt_sum.federal_provider_number
                    WHERE cr.total_revenue > 100000
                    {'AND p.provider_state IN (' + ','.join(['?']*len(selected_states)) + ')' if selected_states else ''}
                    LIMIT 2000
                """, state_filter_params())

                if not scatter_df.empty:
                    fig = px.scatter(scatter_df, x="total_revenue", y="total_rpt",
                                     color="owner_classification", symbol="anomaly_type",
                                     hover_data=["provider_name"],
                                     title="Revenue vs RPT Spending (colored by ownership)",
                                     labels={"total_revenue": "Total Revenue ($)", "total_rpt": "Total RPT ($)"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                # Table of flagged under-reporters
                flagged_df = run_query(f"""
                    SELECT p.provider_name, p.provider_state, p.owner_classification,
                           raf.anomaly_type, raf.actual_rpt_ratio, raf.peer_median_ratio,
                           raf.z_score, raf.flag_reason
                    FROM rpt_anomaly_flags raf
                    JOIN providers p ON raf.federal_provider_number = p.federal_provider_number
                    WHERE raf.anomaly_type IN ('zero_reporter', 'under_reporter')
                    {'AND p.provider_state IN (' + ','.join(['?']*len(selected_states)) + ')' if selected_states else ''}
                    ORDER BY raf.z_score ASC
                    LIMIT 50
                """, state_filter_params())

                if not flagged_df.empty:
                    st.subheader("Flagged Facilities — RPT Under-Reporting")
                    st.dataframe(flagged_df, use_container_width=True, hide_index=True)
            else:
                st.info("Run RPT anomaly detection to populate this section. Use `python -m src.cli validate`.")

            # ── SEC EDGAR REIT Filings ──
            st.divider()
            st.subheader("SEC EDGAR — REIT 10-K Filings")
            st.caption(
                "Annual report filings from publicly traded healthcare REITs. "
                "Compare SEC-disclosed portfolio size and lease income against "
                "HCRIS self-reported data at their facilities."
            )

            sec_df = run_query("""
                SELECT reit_name, COUNT(*) as filing_count,
                       MIN(filing_date) as earliest_filing,
                       MAX(filing_date) as latest_filing
                FROM sec_reit_filings
                GROUP BY reit_name
                ORDER BY filing_count DESC
            """)

            if not sec_df.empty:
                c1, c2 = st.columns(2)
                c1.metric("REITs Tracked", len(sec_df))
                c2.metric("Total 10-K Filings", int(sec_df["filing_count"].sum()))

                st.dataframe(sec_df, use_container_width=True, hide_index=True)

                # Cross-reference: REIT facilities vs HCRIS data
                reit_comparison = run_query("""
                    SELECT p.owner_classification,
                           COUNT(DISTINCT p.federal_provider_number) as facilities,
                           AVG(cr.total_revenue) as avg_hcris_revenue,
                           SUM(COALESCE(rpt_sum.total_rpt, 0)) as total_hcris_rpt
                    FROM providers p
                    LEFT JOIN cost_reports cr ON p.federal_provider_number = cr.federal_provider_number
                    LEFT JOIN (
                        SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                        FROM cost_reports GROUP BY federal_provider_number
                    ) latest ON cr.federal_provider_number = latest.federal_provider_number
                           AND cr.fiscal_year = latest.max_fy
                    LEFT JOIN (
                        SELECT federal_provider_number, SUM(amount) as total_rpt
                        FROM related_party_transactions WHERE amount IS NOT NULL
                        GROUP BY federal_provider_number
                    ) rpt_sum ON p.federal_provider_number = rpt_sum.federal_provider_number
                    WHERE p.owner_classification = 'reit'
                    GROUP BY p.owner_classification
                """)

                if not reit_comparison.empty:
                    st.subheader("REIT-Owned Facilities — HCRIS Financial Summary")
                    st.dataframe(reit_comparison, use_container_width=True, hide_index=True)
            else:
                st.info("Run `python -m src.cli download-sec` to fetch REIT filing metadata from SEC EDGAR.")

    except Exception as e:
        st.warning(f"Error loading financial data: {e}")


elif page == "Related Party Transactions":
    st.header("Related Party Transactions")

    try:
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        has_rpt = run_query("SELECT COUNT(*) as n FROM related_party_transactions")
        rpt_count = int(has_rpt["n"].iloc[0]) if not has_rpt.empty else 0

        if rpt_count == 0:
            st.info("No related-party transaction data available. Run the full pipeline with HCRIS data to load.")
        else:
            # KPI cards
            kpis = run_query(f"""
                SELECT
                    COUNT(*) as total_transactions,
                    SUM(rpt.amount) as total_amount,
                    COUNT(DISTINCT rpt.federal_provider_number) as facilities,
                    COUNT(DISTINCT rpt.related_party_name) as unique_parties
                FROM related_party_transactions rpt
                JOIN providers p ON rpt.federal_provider_number = p.federal_provider_number
                WHERE 1=1{sfilt}
            """, sparams)

            if not kpis.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Transactions", f"{int(kpis['total_transactions'].iloc[0]):,}")
                c2.metric("Total Amount", format_currency(kpis["total_amount"].iloc[0]))
                c3.metric("Facilities", f"{int(kpis['facilities'].iloc[0]):,}")
                c4.metric("Unique Parties", f"{int(kpis['unique_parties'].iloc[0]):,}")

            st.divider()

            # RPT by ownership type
            st.subheader("Related-Party Spending by Ownership Type")
            df = run_query(f"""
                SELECT p.owner_classification,
                       COUNT(*) as transactions,
                       SUM(rpt.amount) as total_amount,
                       AVG(rpt.amount) as avg_amount
                FROM related_party_transactions rpt
                JOIN providers p ON rpt.federal_provider_number = p.federal_provider_number
                WHERE p.owner_classification IS NOT NULL AND rpt.amount IS NOT NULL{sfilt}
                GROUP BY p.owner_classification
                ORDER BY total_amount DESC
            """, sparams)

            if not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.bar(df, x="owner_classification", y="total_amount",
                                 color="owner_classification",
                                 labels={"owner_classification": "Owner Type", "total_amount": "Total RPT ($)"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    fig = px.pie(df, names="owner_classification", values="total_amount", hole=0.4)
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                st.dataframe(df, use_container_width=True, hide_index=True)

            # Service type breakdown — only actual service categories, not ownership classifications
            st.subheader("Transactions by Service Type")
            df = run_query(f"""
                SELECT rpt.party_classification as service_type,
                       COUNT(*) as transactions,
                       SUM(rpt.amount) as total_amount
                FROM related_party_transactions rpt
                JOIN providers p ON rpt.federal_provider_number = p.federal_provider_number
                WHERE rpt.party_classification IS NOT NULL AND rpt.amount IS NOT NULL
                  AND rpt.party_classification NOT IN ('for_profit_chain','nonprofit','government','reit','private_equity','individual','unknown'){sfilt}
                GROUP BY rpt.party_classification
                ORDER BY total_amount DESC
            """, sparams)

            if not df.empty:
                fig = px.bar(df, x="service_type", y="total_amount",
                             color="service_type",
                             labels={"service_type": "Service Type", "total_amount": "Total ($)"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            # RPT vs Quality correlation
            st.subheader("Related-Party Spending vs. Quality")
            df = run_query(f"""
                SELECT p.overall_rating,
                       AVG(rpt_agg.total_rpt) as avg_rpt_amount,
                       COUNT(*) as facilities
                FROM providers p
                JOIN (
                    SELECT federal_provider_number, SUM(amount) as total_rpt
                    FROM related_party_transactions
                    WHERE amount IS NOT NULL
                    GROUP BY federal_provider_number
                ) rpt_agg ON p.federal_provider_number = rpt_agg.federal_provider_number
                WHERE p.overall_rating IS NOT NULL{sfilt}
                GROUP BY p.overall_rating
                ORDER BY p.overall_rating
            """, sparams)

            if not df.empty:
                fig = px.bar(df, x="overall_rating", y="avg_rpt_amount",
                             hover_data=["facilities"],
                             labels={"overall_rating": "Star Rating", "avg_rpt_amount": "Avg RPT Amount ($)"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            # Top spenders
            st.subheader("Top 20 Facilities by Related-Party Spending")
            df = run_query(f"""
                SELECT p.provider_name, p.provider_state, p.overall_rating,
                       p.owner_classification,
                       SUM(rpt.amount) as total_rpt,
                       COUNT(*) as transaction_count
                FROM related_party_transactions rpt
                JOIN providers p ON rpt.federal_provider_number = p.federal_provider_number
                WHERE rpt.amount IS NOT NULL{sfilt}
                GROUP BY rpt.federal_provider_number
                ORDER BY total_rpt DESC
                LIMIT 20
            """, sparams)

            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)

            # Searchable transactions table
            st.subheader("Search Transactions")
            search = st.text_input("Search by party name or facility")
            if search:
                df = run_query(f"""
                    SELECT rpt.federal_provider_number, p.provider_name, p.provider_state,
                           rpt.fiscal_year, rpt.related_party_name, rpt.relationship,
                           rpt.service_description, rpt.amount, rpt.party_classification
                    FROM related_party_transactions rpt
                    JOIN providers p ON rpt.federal_provider_number = p.federal_provider_number
                    WHERE (rpt.related_party_name LIKE ? OR p.provider_name LIKE ?){sfilt}
                    ORDER BY rpt.amount DESC
                    LIMIT 100
                """, (f"%{search}%", f"%{search}%") + sparams)

                if not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("No matching transactions found.")

    except Exception as e:
        st.warning(f"Error loading related-party data: {e}")


elif page == "California Financial Detail":
    st.header("California Financial Detail (HCAI)")
    st.caption(
        "Detailed financial disclosure from California's Department of Health Care "
        "Access and Information (HCAI). CA requires line-item financial reporting "
        "under SB 650, making it the gold standard for nursing home financial transparency."
    )

    try:
        hcai_count = run_query("SELECT COUNT(*) as n FROM ca_hcai_financials")
        total_hcai = int(hcai_count["n"].iloc[0]) if not hcai_count.empty else 0

        if total_hcai == 0:
            st.info(
                "No CA HCAI data loaded. Run `python -m src.cli download-hcai-ca` "
                "and `python -m src.cli extract-hcai-ca` to load California financial disclosures."
            )
        else:
            # KPI cards
            kpis = run_query("""
                SELECT
                    COUNT(DISTINCT ca_facility_id) as facilities,
                    AVG(total_revenue) as avg_revenue,
                    AVG(management_fees) as avg_mgmt_fee,
                    AVG(related_party_expenses) as avg_rpt,
                    AVG(net_income) as avg_net_income,
                    MAX(report_year) as latest_year
                FROM ca_hcai_financials
                WHERE total_revenue > 100000
            """)

            if not kpis.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("CA Facilities", f"{int(kpis['facilities'].iloc[0]):,}")
                c2.metric("Avg Revenue", format_currency(kpis["avg_revenue"].iloc[0]))
                c3.metric("Avg Mgmt Fees", format_currency(kpis["avg_mgmt_fee"].iloc[0]))
                c4.metric("Avg RPT Expenses", format_currency(kpis["avg_rpt"].iloc[0]))

            st.divider()

            # Management fee comparison: HCAI vs HCRIS
            st.subheader("Management Fee Comparison: HCAI vs Federal HCRIS")
            st.caption(
                "CA facilities report management fees to both state (HCAI) and federal (HCRIS). "
                "Discrepancies may indicate selective reporting."
            )

            comparison = run_query("""
                SELECT
                    h.facility_name,
                    h.federal_provider_number,
                    h.management_fees as hcai_mgmt_fees,
                    h.related_party_expenses as hcai_rpt,
                    h.total_revenue as hcai_revenue,
                    cr.total_revenue as hcris_revenue,
                    COALESCE(rpt_sum.total_rpt, 0) as hcris_rpt
                FROM ca_hcai_financials h
                LEFT JOIN cost_reports cr ON h.federal_provider_number = cr.federal_provider_number
                LEFT JOIN (
                    SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                    FROM cost_reports GROUP BY federal_provider_number
                ) latest ON cr.federal_provider_number = latest.federal_provider_number
                       AND cr.fiscal_year = latest.max_fy
                LEFT JOIN (
                    SELECT federal_provider_number, SUM(amount) as total_rpt
                    FROM related_party_transactions WHERE amount IS NOT NULL
                    GROUP BY federal_provider_number
                ) rpt_sum ON h.federal_provider_number = rpt_sum.federal_provider_number
                WHERE h.total_revenue > 100000 AND h.federal_provider_number IS NOT NULL
                ORDER BY h.management_fees DESC
                LIMIT 100
            """)

            if not comparison.empty:
                st.dataframe(comparison, use_container_width=True, hide_index=True)

            # Expense breakdown by owner type
            st.subheader("Expense Breakdown by Owner Type")
            expense_df = run_query("""
                SELECT
                    h.owner_type,
                    COUNT(*) as facilities,
                    AVG(h.total_revenue) as avg_revenue,
                    AVG(h.labor_expenses) as avg_labor,
                    AVG(h.management_fees) as avg_mgmt_fees,
                    AVG(h.lease_rent_expenses) as avg_rent,
                    AVG(h.related_party_expenses) as avg_rpt,
                    AVG(h.net_income) as avg_net_income
                FROM ca_hcai_financials h
                WHERE h.owner_type IS NOT NULL AND h.total_revenue > 100000
                GROUP BY h.owner_type
                ORDER BY avg_revenue DESC
            """)

            if not expense_df.empty:
                fig = px.bar(expense_df, x="owner_type",
                             y=["avg_labor", "avg_mgmt_fees", "avg_rent", "avg_rpt"],
                             barmode="stack",
                             title="Average Expense Components by Owner Type",
                             labels={"owner_type": "Owner Type", "value": "Amount ($)"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(expense_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.warning(f"Error loading CA HCAI data: {e}")


elif page == "Chain Report Cards":
    st.header("Chain & Affiliated Entity Report Cards")
    st.caption("CMS aggregate performance metrics for nursing home chains and affiliated entities.")

    try:
        tab1, tab2 = st.tabs(["Chain Performance", "Affiliated Entity Performance"])

        with tab1:
            chain_df = run_query(
                """SELECT chain_name, chain_id, num_facilities, num_states,
                          avg_overall_rating, avg_health_inspection_rating,
                          avg_staffing_rating, avg_quality_rating,
                          avg_total_nurse_hours, avg_nursing_turnover,
                          total_fines, total_payment_denials,
                          num_sff, num_sff_candidates,
                          pct_for_profit, avg_readmission_rate
                   FROM chain_performance
                   WHERE chain_name != 'National'
                   ORDER BY num_facilities DESC"""
            )
            if not chain_df.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Chains", f"{len(chain_df):,}")
                c2.metric("Avg Rating (all chains)", f"{chain_df['avg_overall_rating'].mean():.2f}/5")
                c3.metric("Total Fines (all chains)", format_currency(chain_df["total_fines"].sum()))

                st.subheader("Lowest-Rated Chains (10+ facilities)")
                low = chain_df[chain_df["num_facilities"] >= 10].nsmallest(20, "avg_overall_rating")
                if not low.empty:
                    fig = px.bar(low, x="chain_name", y="avg_overall_rating",
                                 hover_data=["num_facilities", "num_states", "total_fines"],
                                 labels={"chain_name": "Chain", "avg_overall_rating": "Avg Rating"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                      plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)

                st.subheader("Largest Chains by Facility Count")
                top = chain_df.head(20)
                fig = px.bar(top, x="chain_name", y="num_facilities",
                             color="avg_overall_rating", color_continuous_scale="RdYlGn",
                             hover_data=["num_states", "total_fines"],
                             labels={"chain_name": "Chain", "num_facilities": "Facilities"})
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

                st.subheader("All Chains")
                st.dataframe(chain_df, use_container_width=True, hide_index=True)
            else:
                st.info("No chain performance data. Run the pipeline to download.")

        with tab2:
            aff_df = run_query(
                """SELECT entity_name, entity_id, num_facilities, num_states,
                          avg_overall_rating, avg_health_inspection_rating,
                          avg_staffing_rating, avg_quality_rating,
                          avg_total_nurse_hours, avg_nursing_turnover,
                          total_fines, total_payment_denials,
                          num_sff, num_sff_candidates, avg_readmission_rate
                   FROM affiliated_entity_performance
                   WHERE entity_name != 'National'
                   ORDER BY num_facilities DESC"""
            )
            if not aff_df.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Entities", f"{len(aff_df):,}")
                c2.metric("Avg Rating", f"{aff_df['avg_overall_rating'].mean():.2f}/5")
                c3.metric("With SFF Facilities", f"{(aff_df['num_sff'] > 0).sum():,}")

                st.subheader("Lowest-Rated Entities (10+ facilities)")
                low = aff_df[aff_df["num_facilities"] >= 10].nsmallest(20, "avg_overall_rating")
                if not low.empty:
                    fig = px.bar(low, x="entity_name", y="avg_overall_rating",
                                 hover_data=["num_facilities", "total_fines"],
                                 labels={"entity_name": "Entity", "avg_overall_rating": "Avg Rating"})
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                      plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)

                st.subheader("All Affiliated Entities")
                st.dataframe(aff_df, use_container_width=True, hide_index=True)
            else:
                st.info("No affiliated entity data. Run the pipeline to download.")

    except Exception as e:
        st.warning(f"Error loading chain/entity data: {e}")


elif page == "Star Rating Reality Check":
    st.header("Star Rating Reality Check")
    st.caption("Facilities with 4-5 star ratings AND Immediate Jeopardy (J/K/L) citations — potential rating inflation.")

    try:
        sfilt = state_filter_sql("p")
        sparams = state_filter_params()

        # Facilities with high ratings but IJ citations
        ij_df = run_query(f"""
            SELECT p.federal_provider_number, p.provider_name, p.provider_state,
                   p.overall_rating, p.health_inspection_rating, p.staffing_rating,
                   p.owner_classification,
                   COUNT(d.id) as ij_citations,
                   GROUP_CONCAT(DISTINCT d.deficiency_tag_number) as ij_tags,
                   MAX(d.survey_date) as latest_ij_date
            FROM providers p
            JOIN health_deficiencies d ON p.federal_provider_number = d.federal_provider_number
            WHERE p.overall_rating >= 4
              AND d.scope_severity_code IN ('J', 'K', 'L'){sfilt}
            GROUP BY p.federal_provider_number
            ORDER BY ij_citations DESC
        """, sparams)

        if not ij_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("4-5 Star Facilities with IJ Citations", f"{len(ij_df):,}")
            c2.metric("Total IJ Citations at High-Rated Facilities", f"{ij_df['ij_citations'].sum():,}")
            pe_ij = ij_df[ij_df["owner_classification"] == "private_equity"]
            c3.metric("PE-Owned with IJ + High Rating", f"{len(pe_ij):,}")

            st.divider()

            st.subheader("Facilities with Most IJ Citations Despite High Ratings")
            fig = px.bar(ij_df.head(20), x="provider_name", y="ij_citations",
                         color="overall_rating", color_continuous_scale="RdYlGn",
                         hover_data=["provider_state", "owner_classification", "latest_ij_date"],
                         labels={"provider_name": "Facility", "ij_citations": "IJ Citations",
                                 "overall_rating": "Star Rating"})
            fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Full List")
            st.dataframe(ij_df, use_container_width=True, hide_index=True)
        else:
            st.success("No 4-5 star facilities with Immediate Jeopardy citations found.")

        # Also show RPT non-reporters (PE with $0 RPT)
        st.divider()
        st.subheader("Suspicious RPT Non-Reporters")
        st.caption("PE-owned facilities with zero related-party transactions — potential underreporting of hidden profit extraction.")

        rpt_df = run_query(f"""
            SELECT p.federal_provider_number, p.provider_name, p.provider_state,
                   p.overall_rating, p.owner_classification,
                   p.reported_total_nurse_staffing_hours,
                   COALESCE(cr.total_revenue, 0) as revenue,
                   COALESCE(cr.net_income, 0) as net_income
            FROM providers p
            LEFT JOIN (
                SELECT federal_provider_number, SUM(amount) as total_rpt
                FROM related_party_transactions
                WHERE amount IS NOT NULL AND amount > 0
                GROUP BY federal_provider_number
            ) rpt ON p.federal_provider_number = rpt.federal_provider_number
            LEFT JOIN (
                SELECT cr_inner.federal_provider_number, cr_inner.total_revenue, cr_inner.net_income
                FROM cost_reports cr_inner
                INNER JOIN (
                    SELECT federal_provider_number, MAX(fiscal_year) as max_fy
                    FROM cost_reports GROUP BY federal_provider_number
                ) cr_max ON cr_inner.federal_provider_number = cr_max.federal_provider_number
                         AND cr_inner.fiscal_year = cr_max.max_fy
            ) cr ON p.federal_provider_number = cr.federal_provider_number
            WHERE p.owner_classification = 'private_equity'
              AND (rpt.total_rpt IS NULL OR rpt.total_rpt = 0){sfilt}
            ORDER BY cr.total_revenue DESC
        """, sparams)

        if not rpt_df.empty:
            st.metric("PE Facilities with $0 RPT", f"{len(rpt_df):,}")
            st.dataframe(rpt_df, use_container_width=True, hide_index=True)
        else:
            st.info("No PE facilities with zero RPT found.")

    except Exception as e:
        st.warning(f"Error loading reality check data: {e}")


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
            f"SELECT provider_state, AVG(overall_rating) as avg_rating, COUNT(*) as facilities FROM providers p WHERE overall_rating IS NOT NULL AND provider_state IS NOT NULL{sfilt} GROUP BY provider_state ORDER BY avg_rating DESC",
            sparams,
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
        sfilt = state_filter_sql()
        sparams = state_filter_params()

        metric = st.selectbox("Color by", ["Average Rating", "Facility Count", "Total Fines", "PE-Owned %"])

        if metric == "Average Rating":
            df = run_query(
                f"SELECT provider_state as state, AVG(overall_rating) as value FROM providers p WHERE overall_rating IS NOT NULL{sfilt} GROUP BY provider_state",
                sparams,
            )
            color_label = "Avg Rating"
        elif metric == "Facility Count":
            df = run_query(
                f"SELECT provider_state as state, COUNT(*) as value FROM providers p WHERE 1=1{sfilt} GROUP BY provider_state",
                sparams,
            )
            color_label = "Facilities"
        elif metric == "Total Fines":
            df = run_query(
                f"SELECT p.provider_state as state, SUM(pen.fine_amount) as value FROM penalties pen JOIN providers p ON pen.federal_provider_number = p.federal_provider_number WHERE 1=1{sfilt} GROUP BY p.provider_state",
                sparams,
            )
            color_label = "Total Fines ($)"
        else:
            df = run_query(f"""
                SELECT provider_state as state,
                       100.0 * SUM(CASE WHEN owner_classification = 'private_equity' THEN 1 ELSE 0 END) / COUNT(*) as value
                FROM providers p
                WHERE provider_state IS NOT NULL{sfilt}
                GROUP BY provider_state
            """, sparams)
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
                        "SELECT penalty_date, penalty_type, fine_amount, payment_denial_start_date, payment_denial_length_days FROM penalties WHERE federal_provider_number = ? ORDER BY penalty_date DESC",
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

                    # Cost Reports
                    st.subheader("Cost Report History")
                    try:
                        costs = run_query(
                            """SELECT fiscal_year, total_revenue, total_expenses, net_income,
                                      medicare_revenue, other_revenue, cost_per_patient_day,
                                      total_beds, total_patient_days
                               FROM cost_reports WHERE federal_provider_number = ?
                               ORDER BY fiscal_year DESC""",
                            (selected,),
                        )
                        if not costs.empty:
                            st.dataframe(costs, use_container_width=True, hide_index=True)
                            if len(costs) > 1:
                                fig = px.line(costs.sort_values("fiscal_year"),
                                              x="fiscal_year", y=["total_revenue", "total_expenses"],
                                              labels={"fiscal_year": "Year", "value": "$",
                                                      "total_revenue": "Net Patient Revenue",
                                                      "total_expenses": "Operating Expenses"})
                                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                                st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No cost report data.")
                    except Exception:
                        st.info("Cost report data not available.")

                    # Related Party Transactions
                    st.subheader("Related Party Transactions")
                    try:
                        rpts = run_query(
                            """SELECT fiscal_year, related_party_name, relationship,
                                      service_description, amount, party_classification
                               FROM related_party_transactions WHERE federal_provider_number = ?
                               ORDER BY fiscal_year DESC, amount DESC""",
                            (selected,),
                        )
                        if not rpts.empty:
                            total_rpt = rpts["amount"].sum()
                            st.metric("Total Related-Party Spending", format_currency(total_rpt))
                            st.dataframe(rpts, use_container_width=True, hide_index=True)
                        else:
                            st.info("No related-party transaction data.")
                    except Exception:
                        st.info("Related-party data not available.")

                    # SNF All Owners (detailed ownership with PE/REIT flags)
                    st.subheader("Detailed Ownership (SNF All Owners)")
                    try:
                        snf = run_query(
                            """SELECT owner_name, owner_type, ownership_pct,
                                      is_pe_flag, is_reit_flag, is_parent_company,
                                      is_created_for_acquisition, is_chain_home_office,
                                      is_financial_institution, is_for_profit, is_non_profit,
                                      owner_state, party_type
                               FROM snf_all_owners WHERE federal_provider_number = ?
                               ORDER BY ownership_pct DESC""",
                            (selected,),
                        )
                        if not snf.empty:
                            st.dataframe(snf, use_container_width=True, hide_index=True)
                        else:
                            st.info("No SNF All Owners data.")
                    except Exception:
                        st.info("SNF ownership data not available.")

                    # Ownership change history
                    st.subheader("Ownership Change History")
                    try:
                        chow = run_query(
                            """SELECT change_date, previous_owner, new_owner, change_type
                               FROM ownership_changes WHERE federal_provider_number = ?
                               ORDER BY change_date DESC""",
                            (selected,),
                        )
                        if not chow.empty:
                            st.dataframe(chow, use_container_width=True, hide_index=True)
                        else:
                            st.info("No ownership changes recorded.")
                    except Exception:
                        st.info("Ownership change data not available.")

                    # Quality Measures
                    st.subheader("Quality Measures")
                    try:
                        qm = run_query(
                            """SELECT measure_code, measure_description, resident_type, score,
                                      observed_score, expected_score
                               FROM quality_measures WHERE federal_provider_number = ?
                               ORDER BY measure_code""",
                            (selected,),
                        )
                        if not qm.empty:
                            st.dataframe(qm, use_container_width=True, hide_index=True)
                        else:
                            st.info("No quality measure data.")
                    except Exception:
                        st.info("Quality measure data not available.")

                    # SNF VBP (Value-Based Purchasing)
                    st.subheader("Value-Based Purchasing (VBP)")
                    try:
                        vbp = run_query(
                            """SELECT program_year, snhrd_rate, performance_score,
                                      achievement_score, improvement_score,
                                      incentive_multiplier, performance_rate
                               FROM snf_vbp WHERE federal_provider_number = ?
                               ORDER BY program_year DESC""",
                            (selected,),
                        )
                        if not vbp.empty:
                            r = vbp.iloc[0]
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Performance Score", f"{r['performance_score']:.1f}" if pd.notna(r.get('performance_score')) else "—")
                            c2.metric("Incentive Multiplier", f"{r['incentive_multiplier']:.3f}" if pd.notna(r.get('incentive_multiplier')) else "—")
                            c3.metric("SNHRD Rate", f"{r['snhrd_rate']:.1f}%" if pd.notna(r.get('snhrd_rate')) else "—")
                            st.dataframe(vbp, use_container_width=True, hide_index=True)
                        else:
                            st.info("No VBP data.")
                    except Exception:
                        st.info("VBP data not available.")

                    # Fire safety deficiencies
                    st.subheader("Fire Safety Deficiencies")
                    try:
                        fire = run_query(
                            """SELECT survey_date, deficiency_tag_number, scope_severity_code,
                                      deficiency_description
                               FROM fire_safety_deficiencies WHERE federal_provider_number = ?
                               ORDER BY survey_date DESC""",
                            (selected,),
                        )
                        if not fire.empty:
                            st.dataframe(fire, use_container_width=True, hide_index=True)
                        else:
                            st.info("No fire safety deficiency data.")
                    except Exception:
                        st.info("Fire safety data not available.")
        else:
            st.info("Enter a facility name or CMS provider number to search.")
    except Exception as e:
        st.warning(f"Error: {e}")
