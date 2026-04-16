"""
Job Hunting Agent - Monitoring Dashboard

A Streamlit dashboard for visualizing pipeline metrics and API costs.
This is a standalone version that queries Supabase directly (no internal dependencies).

Run locally:
    streamlit run app.py

Deploy to Streamlit Cloud:
    1. Push to GitHub (public repo)
    2. Connect repo at share.streamlit.io
    3. Set secrets in Streamlit Cloud dashboard

Required secrets (in .streamlit/secrets.toml or Streamlit Cloud):
    SUPABASE_URL = "https://xxx.supabase.co"
    SUPABASE_ANON_KEY = "eyJ..."  # Read-only key
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from supabase import create_client


# =============================================================================
# Page configuration
# =============================================================================

st.set_page_config(
    page_title="Job Hunting Agent | Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Portfolio color palette
COLORS = {
    "primary": "#A67C5B",      # Terracota
    "secondary": "#6B7F5E",    # Verde oliva
    "accent": "#8B9D77",       # Verde claro
    "background": "#F5F3EF",   # Bege creme
    "surface": "#FFFFFF",      # Branco
    "text": "#1a1a1a",         # Preto
    "muted": "#6B7280",        # Cinza
    "success": "#6B7F5E",      # Verde oliva
    "warning": "#D4A574",      # Terracota claro
    "error": "#C45C4A",        # Vermelho terroso
}

# Custom CSS with portfolio colors
st.markdown(f"""
<style>
    /* Main background */
    .stApp {{
        background-color: {COLORS["background"]};
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {COLORS["surface"]};
        border-right: 1px solid #E8E4DD;
    }}
    
    /* Headers */
    h1, h2, h3 {{
        color: {COLORS["text"]} !important;
    }}
    
    /* Metrics */
    [data-testid="stMetric"] {{
        background-color: {COLORS["surface"]};
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #E8E4DD;
    }}
    
    [data-testid="stMetricValue"] {{
        color: {COLORS["primary"]} !important;
    }}
    
    /* Buttons */
    .stButton > button {{
        background-color: {COLORS["primary"]};
        color: white;
        border: none;
        border-radius: 4px;
    }}
    
    .stButton > button:hover {{
        background-color: #8B6B4A;
    }}
    
    /* Success message */
    .stSuccess {{
        background-color: #E8EDE5;
        border-left-color: {COLORS["secondary"]};
    }}
    
    /* Dividers */
    hr {{
        border-color: #E8E4DD;
    }}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class PipelineMetrics:
    """Snapshot of pipeline counts by state."""
    discovered: int = 0
    duplicates: int = 0
    fetched: int = 0
    filtered: int = 0
    filtered_out: int = 0
    matched: int = 0
    not_selected: int = 0
    resume_generated: int = 0
    emailed: int = 0
    failed: int = 0
    
    @property
    def total_processed(self) -> int:
        return self.discovered + self.duplicates
    
    @property
    def match_rate(self) -> float:
        if self.filtered == 0:
            return 0.0
        return self.matched / self.filtered
    
    @property
    def filter_pass_rate(self) -> float:
        total_filtered = self.filtered + self.filtered_out
        if total_filtered == 0:
            return 0.0
        return self.filtered / total_filtered
    
    @property
    def error_rate(self) -> float:
        if self.total_processed == 0:
            return 0.0
        return self.failed / self.total_processed


@dataclass
class APICosts:
    """API usage costs breakdown."""
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    matching_calls: int = 0
    matching_cost: float = 0.0
    tailoring_calls: int = 0
    tailoring_cost: float = 0.0
    
    @property
    def total_calls(self) -> int:
        return self.matching_calls + self.tailoring_calls


@dataclass
class Summary:
    """Complete summary combining pipeline metrics and costs."""
    period_start: datetime
    period_end: datetime
    metrics: PipelineMetrics
    costs: APICosts
    errors: list = field(default_factory=list)


# =============================================================================
# Supabase client
# =============================================================================

@st.cache_resource
def get_supabase_client():
    """Initialize Supabase client with read-only publishable key."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None


# =============================================================================
# Data fetching functions
# =============================================================================

def get_current_counts(client) -> PipelineMetrics:
    """Get current job counts by state (all time)."""
    if not client:
        return PipelineMetrics()
    
    try:
        result = client.table("jobs").select("state").execute()
        
        state_counts = {}
        for job in result.data:
            state = job.get("state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return PipelineMetrics(
            discovered=state_counts.get("DISCOVERED", 0),
            duplicates=state_counts.get("DUPLICATE", 0),
            fetched=state_counts.get("FETCHED", 0),
            filtered=state_counts.get("FILTERED", 0),
            filtered_out=state_counts.get("FILTERED_OUT", 0),
            matched=state_counts.get("MATCHED", 0),
            not_selected=state_counts.get("NOT_SELECTED", 0),
            resume_generated=state_counts.get("RESUME_GENERATED", 0),
            emailed=state_counts.get("EMAILED", 0),
            failed=state_counts.get("FAILED", 0),
        )
    except Exception as e:
        st.error(f"Error fetching counts: {e}")
        return PipelineMetrics()


def get_counts_since(client, since: datetime) -> PipelineMetrics:
    """Get job counts by state since a specific datetime."""
    if not client:
        return PipelineMetrics()
    
    try:
        result = (
            client.table("jobs")
            .select("state, created_at")
            .gte("created_at", since.isoformat())
            .execute()
        )
        
        state_counts = {}
        for job in result.data:
            state = job.get("state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1
        
        return PipelineMetrics(
            discovered=state_counts.get("DISCOVERED", 0),
            duplicates=state_counts.get("DUPLICATE", 0),
            fetched=state_counts.get("FETCHED", 0),
            filtered=state_counts.get("FILTERED", 0),
            filtered_out=state_counts.get("FILTERED_OUT", 0),
            matched=state_counts.get("MATCHED", 0),
            not_selected=state_counts.get("NOT_SELECTED", 0),
            resume_generated=state_counts.get("RESUME_GENERATED", 0),
            emailed=state_counts.get("EMAILED", 0),
            failed=state_counts.get("FAILED", 0),
        )
    except Exception as e:
        st.error(f"Error fetching counts: {e}")
        return PipelineMetrics()


def get_daily_counts(client, days: int = 30) -> list:
    """Get daily job counts for charts."""
    if not client:
        return []
    
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = (
            client.table("jobs")
            .select("state, created_at")
            .gte("created_at", since.isoformat())
            .execute()
        )
        
        daily = {}
        for job in result.data:
            created = job.get("created_at", "")
            if created:
                date_str = created[:10]
                if date_str not in daily:
                    daily[date_str] = {
                        "discovered": 0, "matched": 0, "emailed": 0,
                        "filtered_out": 0, "not_selected": 0, "failed": 0
                    }
                
                state = job.get("state", "")
                if state == "DISCOVERED":
                    daily[date_str]["discovered"] += 1
                elif state == "MATCHED":
                    daily[date_str]["matched"] += 1
                elif state == "EMAILED":
                    daily[date_str]["emailed"] += 1
                elif state == "FILTERED_OUT":
                    daily[date_str]["filtered_out"] += 1
                elif state == "NOT_SELECTED":
                    daily[date_str]["not_selected"] += 1
                elif state == "FAILED":
                    daily[date_str]["failed"] += 1
        
        return [{"date": d, **daily[d]} for d in sorted(daily.keys())]
    except Exception as e:
        st.error(f"Error fetching daily counts: {e}")
        return []


def get_api_costs(client, since: datetime = None) -> APICosts:
    """Get API costs from Supabase."""
    if not client:
        return APICosts()
    
    try:
        query = client.table("api_usage").select("*")
        if since:
            query = query.gte("timestamp", since.isoformat())
        
        result = query.execute()
        
        costs = APICosts()
        for r in result.data:
            costs.total_input_tokens += r.get("input_tokens", 0)
            costs.total_output_tokens += r.get("output_tokens", 0)
            costs.total_cost += float(r.get("cost_usd", 0.0))
            
            operation = r.get("operation", "")
            cost = float(r.get("cost_usd", 0.0))
            if operation == "matching":
                costs.matching_calls += 1
                costs.matching_cost += cost
            elif operation in ("tailoring", "resume_tailoring"):
                costs.tailoring_calls += 1
                costs.tailoring_cost += cost
        
        return costs
    except Exception as e:
        st.error(f"Error fetching API costs: {e}")
        return APICosts()


def get_recent_errors(client, limit: int = 10) -> list:
    """Get recent failed jobs."""
    if not client:
        return []
    
    try:
        result = (
            client.table("jobs")
            .select("id, title, company, state, last_error, updated_at")
            .eq("state", "FAILED")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data
    except Exception as e:
        st.error(f"Error fetching errors: {e}")
        return []


def get_match_rate_trend(client, days: int = 30) -> list:
    """Calculate match rate trend over time."""
    daily = get_daily_counts(client, days)
    
    trend = []
    for day in daily:
        total = day.get("matched", 0) + day.get("not_selected", 0)
        rate = (day.get("matched", 0) / total * 100) if total > 0 else 0.0
        trend.append({
            "date": day["date"],
            "match_rate": round(rate, 1),
            "matched": day.get("matched", 0),
            "not_selected": day.get("not_selected", 0),
        })
    
    return trend


# =============================================================================
# Load all metrics
# =============================================================================

@st.cache_data(ttl=300)
def load_metrics():
    """Load all metrics from Supabase."""
    client = get_supabase_client()
    if not client:
        return None
    
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    try:
        return {
            "weekly": Summary(
                period_start=week_ago,
                period_end=now,
                metrics=get_counts_since(client, week_ago),
                costs=get_api_costs(client, week_ago),
                errors=get_recent_errors(client, 5),
            ),
            "monthly": Summary(
                period_start=month_ago,
                period_end=now,
                metrics=get_counts_since(client, month_ago),
                costs=get_api_costs(client, month_ago),
                errors=get_recent_errors(client, 10),
            ),
            "daily": get_daily_counts(client, 30),
            "current": get_current_counts(client),
            "trend": get_match_rate_trend(client, 30),
            "errors": get_recent_errors(client, 10),
        }
    except Exception as e:
        st.error(f"Error loading metrics: {e}")
        return None


# =============================================================================
# Sidebar
# =============================================================================

def render_sidebar():
    """Render sidebar with controls and info."""
    with st.sidebar:
        st.title("🎯 Job Hunting Agent")
        st.caption("Monitoring Dashboard")
        
        st.divider()
        
        time_range = st.selectbox(
            "Time Range",
            options=["Last 7 days", "Last 30 days"],
            index=0
        )
        
        st.divider()
        
        st.subheader("📊 Quick Stats")
        data = load_metrics()
        if data:
            current = data["current"]
            total_in_db = (
                current.discovered + current.duplicates + current.fetched +
                current.filtered + current.filtered_out + current.matched +
                current.not_selected + current.resume_generated + 
                current.emailed + current.failed
            )
            
            st.metric("Total Jobs in Database", total_in_db)
            st.caption("All jobs ever processed")
            
            st.metric("Total Jobs Emailed", current.emailed)
            st.caption("Jobs sent via weekly digest")
        
        st.divider()
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        st.caption("Built with Streamlit")
        
        return time_range


# =============================================================================
# Dashboard components
# =============================================================================

def render_kpi_cards(summary: Summary):
    """Render top KPI cards."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Jobs Discovered",
            value=summary.metrics.discovered,
            help="New jobs found this period"
        )
    
    with col2:
        st.metric(
            label="Resumes Generated",
            value=summary.metrics.resume_generated,
            help="Tailored resumes created"
        )
    
    with col3:
        st.metric(
            label="Jobs Emailed",
            value=summary.metrics.emailed,
            help="Jobs included in digests"
        )
    
    with col4:
        st.metric(
            label="API Cost",
            value=f"${summary.costs.total_cost:.2f}",
            help="Claude API costs"
        )


def render_pipeline_funnel(summary: Summary):
    """Render pipeline funnel chart."""
    st.subheader("📊 Pipeline Funnel")
    
    m = summary.metrics
    stages = ["Discovered", "Filtered", "Resume Gen", "Emailed"]
    values = [m.discovered, m.filtered, m.resume_generated, m.emailed]
    
    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(color=["#A67C5B", "#8B6B4A", "#6B7F5E", "#8B9D77"]),
        connector=dict(line=dict(color="#E8E4DD", width=2))
    ))
    
    fig.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_daily_chart(daily_data: list):
    """Render daily jobs chart."""
    st.subheader("📈 Daily Job Activity")
    
    if not daily_data:
        st.info("No data available yet")
        return
    
    df = pd.DataFrame(daily_data)
    df["date"] = pd.to_datetime(df["date"])
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name="Emailed",
        x=df["date"],
        y=df.get("emailed", [0] * len(df)),
        marker_color="#6B7F5E"
    ))
    
    fig.add_trace(go.Bar(
        name="Not Selected",
        x=df["date"],
        y=df["not_selected"],
        marker_color="#C45C4A"
    ))
    
    fig.add_trace(go.Bar(
        name="Filtered Out",
        x=df["date"],
        y=df["filtered_out"],
        marker_color="#D4D0C8"
    ))
    
    fig.update_layout(
        barmode="stack",
        height=300,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_title="",
        yaxis_title="Jobs",
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_cost_breakdown(costs: APICosts):
    """Render API cost breakdown."""
    st.subheader("💰 API Costs")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(go.Pie(
            labels=["Input Tokens", "Output Tokens"],
            values=[costs.total_input_tokens, costs.total_output_tokens],
            hole=0.4,
            marker_colors=["#A67C5B", "#6B7F5E"],
            textinfo="percent",
        ))
        
        fig.update_layout(
            height=250,
            margin=dict(l=20, r=20, t=20, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.metric("Total Cost", f"${costs.total_cost:.2f}")
        st.markdown(f"""
        **Token Usage**
        - Input: {costs.total_input_tokens:,}
        - Output: {costs.total_output_tokens:,}
        """)


def render_state_breakdown(current: PipelineMetrics):
    """Render current state breakdown."""
    st.subheader("📋 Current State Breakdown")
    
    states = {
        "Discovered": current.discovered,
        "Fetched": current.fetched,
        "Filtered": current.filtered,
        "Filtered Out": current.filtered_out,
        "Not Selected": current.not_selected,
        "Resume Gen": current.resume_generated,
        "Emailed": current.emailed,
        "Duplicates": current.duplicates,
        "Failed": current.failed,
    }
    
    df = pd.DataFrame({"State": states.keys(), "Count": states.values()})
    
    fig = px.bar(
        df, x="State", y="Count", color="Count",
        color_continuous_scale=["#F5F3EF", "#D4A574", "#A67C5B", "#6B7F5E"]
    )
    
    fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=20, b=60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis_tickangle=-45
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_errors_table(errors: list):
    """Render recent errors table."""
    st.subheader("🔴 Recent Errors")
    
    if not errors:
        st.success("No recent errors!")
        return
    
    df = pd.DataFrame(errors)
    
    if "updated_at" in df.columns:
        df["updated_at"] = pd.to_datetime(df["updated_at"]).dt.strftime("%Y-%m-%d %H:%M")
    
    display_cols = [c for c in ["title", "company", "last_error", "updated_at"] if c in df.columns]
    
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "title": "Job Title",
            "company": "Company",
            "last_error": "Error",
            "updated_at": "Time"
        }
    )


# =============================================================================
# Main app
# =============================================================================

def main():
    """Main dashboard app."""
    time_range = render_sidebar()
    data = load_metrics()
    
    if not data:
        st.error("Could not load metrics. Check your database connection.")
        st.stop()
    
    summary = data["weekly"] if time_range == "Last 7 days" else data["monthly"]
    
    st.title("🎯 Job Hunting Agent Dashboard")
    st.caption(f"Pipeline metrics for {time_range.lower()}")
    
    render_kpi_cards(summary)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        render_pipeline_funnel(summary)
    with col2:
        render_daily_chart(data["daily"])
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        render_cost_breakdown(summary.costs)
    with col2:
        render_state_breakdown(data["current"])
    
    st.divider()
    
    render_errors_table(data["errors"])
    
    st.divider()
    st.caption(
        f"📊 Data refreshes every 5 minutes | "
        f"Period: {summary.period_start.strftime('%Y-%m-%d')} to {summary.period_end.strftime('%Y-%m-%d')}"
    )


if __name__ == "__main__":
    main()
