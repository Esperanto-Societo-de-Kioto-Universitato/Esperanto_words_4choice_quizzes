import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

def main():
    st.title("Debug Sheets Data")
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    st.subheader("Scores Sheet (Raw Log)")
    try:
        scores_df = conn.read(worksheet="Scores", ttl=0)
        st.write("Shape:", scores_df.shape)
        st.write("Dtypes:", scores_df.dtypes)
        st.dataframe(scores_df.head())
        
        if "points" in scores_df.columns:
            st.write("Points column sample:", scores_df["points"].head())
            # Check if numeric
            is_numeric = pd.to_numeric(scores_df["points"], errors='coerce').notnull().all()
            st.write(f"Is 'points' column fully numeric? {is_numeric}")
    except Exception as e:
        st.error(f"Error reading Scores: {e}")

    st.subheader("UserStats Sheet (Cumulative)")
    try:
        stats_df = conn.read(worksheet="UserStats", ttl=0)
        if stats_df is not None:
            st.write("Shape:", stats_df.shape)
            st.write("Dtypes:", stats_df.dtypes)
            st.dataframe(stats_df)
            
            if "total_points" in stats_df.columns:
                 st.write("total_points sample:", stats_df["total_points"].head())
        else:
            st.write("UserStats is empty or None")
    except Exception as e:
        st.error(f"Error reading UserStats: {e}")

if __name__ == "__main__":
    main()
