import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

def main():
    st.title("Fix UserStats Data")
    st.write("This script will recalculate UserStats from the Scores sheet.")
    
    if st.button("Recalculate and Overwrite UserStats"):
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        try:
            # 1. Read Scores
            st.info("Reading Scores sheet...")
            scores_df = conn.read(worksheet="Scores", ttl=0)
            if scores_df is None or scores_df.empty:
                st.error("Scores sheet is empty!")
                return
            
            st.write(f"Read {len(scores_df)} rows from Scores.")
            
            # 2. Aggregate
            st.info("Aggregating scores...")
            # Ensure points is numeric
            scores_df["points"] = pd.to_numeric(scores_df["points"], errors='coerce').fillna(0)
            
            agg = scores_df.groupby("user")["points"].sum().reset_index()
            agg.columns = ["user", "total_points"]
            agg["last_updated"] = datetime.datetime.utcnow().isoformat()
            
            st.write("Aggregated Data:")
            st.dataframe(agg)
            
            # 3. Write to UserStats
            st.info("Writing to UserStats sheet...")
            conn.update(worksheet="UserStats", data=agg)
            
            st.success("Successfully updated UserStats!")
            st.cache_data.clear()
            
        except Exception as e:
            st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
