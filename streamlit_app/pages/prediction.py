# pages/prediction.py - Temperature prediction page

import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.file_selector import csv_file_selector
from utils.data_processing import detect_columns, summarize_t_est, extract_t_est_from_result
from config import DEFAULT_CSV_DIRS


def render_prediction_tab(predict_fn):
    """
    Render the temperature prediction tab
    
    Args:
        predict_fn: TEXAS prediction function (or None if not available)
    """
    st.subheader("Predict temperature from RI")

    # File selection
    selected_csv_path, df_in = csv_file_selector(DEFAULT_CSV_DIRS)
    
    if df_in is None:
        st.info("Upload a CSV or select one from repo folders to continue.")
        return

    # Display file info
    st.markdown(f"**Using CSV:** `{os.path.basename(selected_csv_path) if selected_csv_path else 'uploaded file'}`")
    with st.expander("Peek at input (first 10 rows)"):
        st.dataframe(df_in.head(10))

    # Column mapping
    st.subheader("Map columns")
    auto_col = detect_columns(df_in, ["scaledRI", "ri", "RI"]) or df_in.columns[0]
    col_scaledRI = st.selectbox("scaledRI column", options=df_in.columns, 
                              index=df_in.columns.tolist().index(auto_col))

    opt_gdgt = st.selectbox("gdgt23ratio column (optional)", 
                          options=["<none>"] + df_in.columns.tolist(), index=0)
    opt_no3 = st.selectbox("no3 column (optional)", 
                         options=["<none>"] + df_in.columns.tolist(), index=0)

    # Inference settings
    st.subheader("Inference settings")
    prior_mu_t = st.number_input("prior_mu_t", value=30.0)
    prior_sigma_t = st.number_input("prior_sigma_t", value=6.0, min_value=0.01)
    fwd_posterior_name = st.text_input("Forward posterior name", 
                                     value="gen_logi_fixed_culmesocore_thermoT")
    no3_cutoff = st.number_input("no3_cutoff (µmol/L)", value=0.0, min_value=0.0)
    site_name = st.text_input("site_name", value="Uploaded CSV")

    # Run prediction
    disabled = predict_fn is None
    if st.button("Run prediction", type="primary", disabled=disabled):
        if predict_fn is None:
            st.error("predict_T_from_proxyObs not available. Check TEXAS install.")
        else:
            with st.spinner("Running TEXAS.predict_T_from_proxyObs..."):
                predictors = {}
                if opt_gdgt != "<none>":
                    predictors["gdgt23ratio"] = df_in[opt_gdgt].astype(float).tolist()
                if opt_no3 != "<none>":
                    predictors["no3"] = df_in[opt_no3].astype(float).tolist()

                try:
                    res = predict_fn(
                        proxyObs=df_in[col_scaledRI].astype(float).tolist(),
                        prior_mu_t=float(prior_mu_t),
                        prior_sigma_t=float(prior_sigma_t),
                        fwd_posterior_name=fwd_posterior_name,
                        predictors=predictors or None,
                        no3_cutoff=float(no3_cutoff),
                        site_name=site_name,
                        save_results=False,
                    )
                    
                    t_arr = extract_t_est_from_result(res)
                    if t_arr is None:
                        st.error("Couldn't find `t_est` in the result. Adjust extractor or check return type.")
                    else:
                        summary = summarize_t_est(t_arr)
                        out_df = df_in.copy().reset_index(drop=True).join(summary)
                        st.success("Done!")
                        st.dataframe(out_df.head(20))

                        fig, ax = plt.subplots(figsize=(6, 4))
                        ax.scatter(np.arange(len(summary)), summary["t_est_mean"])
                        ax.set_xlabel("Observation index")
                        ax.set_title("Predicted temperature (mean)")
                        st.pyplot(fig, clear_figure=True)

                        st.download_button("Download results as CSV", 
                                         data=out_df.to_csv(index=False).encode("utf-8"),
                                         file_name="texas_t_est_results.csv", 
                                         mime="text/csv")
                        
                except Exception as e:
                    st.error(f"Prediction failed: {e}")