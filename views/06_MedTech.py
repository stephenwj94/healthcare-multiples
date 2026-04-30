"""
MedTech comp table.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from components.comp_table import render_comp_table
from config.settings import DB_PATH
from fetcher.db_manager import DBManager

render_sidebar()

st.title("MedTech")

db = DBManager(DB_PATH)

# Get data freshness date
try:
    last_fetch = db.get_last_fetch_time()
    if last_fetch:
        from datetime import datetime
        dt = datetime.strptime(last_fetch[:10], "%Y-%m-%d")
        date_str = dt.strftime("%B %d, %Y")
        st.markdown(
            f'<p style="color:#94A3B8;font-size:12px;margin:-4px 0 4px 0;">'
            f'All financials in millions ($mm) · Data as of {date_str}</p>',
            unsafe_allow_html=True,
        )
except Exception:
    pass

try:
    data = db.get_latest_snapshots(segment="medtech")
    render_comp_table(data, "MedTech")
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.info("Run the data fetcher to populate the database.")
