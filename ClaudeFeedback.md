  Project Feedback                                                                                                                                   
                                                                                                
  What's Working Well                                                                                                                                
                                                                                                                                                     
  - The two-stage Bayesian architecture (forward → inverse) is clean and well-separated                                                              
  - Posterior metadata (stan_diag_* attrs, prior strings, run provenance) is thorough — important for reproducibility reviewers will check           
  - Stan model naming convention is systematic, making it possible to understand model structure without reading the file                            
  - StanCompiler caching is smart and avoids redundant recompilation
  - The Streamlit app's modular architecture (pages/, components/, utils/) is publication-quality                                                    
                                                                                                                                                     
  ---                                                                                                                                                
  Things to Remove                                                                                                                                   
                                                                                                                                                     
  ┌─────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────────┐                 
  │                          Item                           │                                Reason                                │
  ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤                 
  │ notebooks/manuscripts/SI_code2_data_processing.ipynb    │ Empty file — will confuse readers                                    │                 
  ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤                 
  │ legacy_TEXAS_20250822.tar.gz                            │ 50+ MB archive in git, should not be in a public repo                │                 
  ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤                 
  │ phylo service in docker-compose.yml + Dockerfile.phylo  │ Genomics pipeline is unrelated to the TEXAS paper; distracts readers │                 
  ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤                 
  │ data/phylo/ directory                                   │ Same reason — scope creep from an unrelated project                  │                 
  ├─────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤                 
  │ Commented-out COPY and pip install blocks in Dockerfile │ Confusing — either use them or delete them                           │                 
  └─────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────┘                 
                                                                                                                                                     
  ---                                                                                                                                                
  Things to Add / Fix                                                                                                                                
                                                                                                                                                     
  For reproducibility (reviewers will check this):                                                                                                   
                                                                                                                                                     
  1. Fix hardcoded /opt/cmdstan/cmdstan-2.36.0 in the notebooks — replace with:                                                                      
  from TEXAS.utils.paths import CMDSTAN_DIR                                                                                                          
  cmdstanpy.set_cmdstan_path(str(CMDSTAN_DIR))                                                                                                       
  2. Move SI_code2_TEXAS_analysis.ipynb from notebooks/current/ to notebooks/manuscripts/ so both SI codes are co-located for journal reviewers.     
  3. Add a data availability statement / download script — specify that external data (data/external/ncfiles/, WOA23, Zhu19, Tierney22) must be      
  downloaded from their original sources, and provide exact DOIs or wget commands. A scripts/download_data.sh stub would suffice.                    
  4. Add a CITATION.cff at the repo root — GitHub renders it as a "Cite this repository" button, and AGU requires software citation.                 
  5. Add a Zenodo release and include the DOI badge in the README — AGU Paleoceanography and Paleoclimatology now requires or strongly recommends    
  citable software/data archives.                                                                                                                    
  6. Add a minimal test suite — even 3–5 tests that run without Stan (unit tests on the pure-Python logistic functions and auto_detect_predictors)   
  make a major difference for reviewer confidence. Put them in tests/.                                                                               
  7. Fix the empty SI_code2_data_processing.ipynb — delete it or rename the actual analysis notebook to match the SI numbering exactly as it will    
  appear in the paper.                                                                                                                               
  8. Add a root README.md with: what TEXAS is, how to cite it, quickstart, links to the SI notebooks and Zenodo. The current docs/index.md exists but
   GitHub shows the root README.                                                                                                                     
                                                                                                                                                     
  ---                                                                                                                                                
  Docker — For Coders                                                                                                                                
                                                                                                                                                     
  The current Dockerfile setup is good but requires users to build locally (slow, ~20 min due to CmdStan compilation). For readers of the paper,     
  publish a pre-built image:                                                                                                                         
                                                                                                                                                     
  1. Push to GitHub Container Registry (GHCR) — free, tied to your GitHub account:                                                                   
  docker build -t ghcr.io/paleolipidRR/texas:latest -f docker/Dockerfile .                                                                           
  docker push ghcr.io/paleolipidRR/texas:latest                                                                                                      
  1. Readers then just run:                                                                                                                          
  docker run -it -p 8888:8888 -v $(pwd)/data:/home/micromamba/app/data ghcr.io/paleolipidRR/texas:latest jupyter lab --ip=0.0.0.0                    
  2. Fix the Dockerfile — uncomment the TEXAS package installation steps so the image is self-contained (no PYTHONPATH workaround needed).           
  3. Add a run.sh or Makefile at the repo root:                                                                                                      
  # run.sh                                                                                                                                           
  docker run -it \
    -p 8888:8888 \
    -v "$(pwd)/data":/home/micromamba/app/data \
    ghcr.io/paleolipidRR/texas:latest \
    jupyter lab --ip=0.0.0.0 --no-browser
  3. This is what non-programmers who "can run a terminal command" will copy-paste from the README.
  4. Tag releases (v0.1.0) and push versioned Docker tags alongside the paper so the exact computational environment is frozen.

  ---
  Non-Coders — Interactive Webpage

  The best option for a journal publication is Streamlit Community Cloud (free, no server needed):

  Why it's ideal here:
  - Your Streamlit app already exists and has a drag-and-drop CSV upload
  - Deployment takes ~10 minutes
  - The URL is permanent and shareable in the paper (e.g., https://texas-psm.streamlit.app)
  - No infrastructure to maintain

  What needs to happen first:
  1. The Streamlit app currently loads pre-computed posteriors from data/cache/. For a public deployment, you need to either:
    - Bundle the pre-computed forward posteriors into the Streamlit image (the .nc files in TEXAS_posterior_cache/ are small enough), or
    - Host them on Zenodo and have the app download them on first run
  2. The Predict tab (CSV → temperature) is the key feature for non-coders — it should be the landing page
  3. Add a sample CSV download button so users can try it immediately without their own data

  Deployment steps:
  1. Push repo to GitHub (already done)
  2. Go to share.streamlit.io → "New app" → point to streamlit_app/main.py
  3. Set TEXAS_FWD_CACHE and TEXAS_INV_CACHE env vars in the Streamlit Cloud dashboard
  4. Done — permanent URL you can put in the paper

  Alternative: Hugging Face Spaces — also free, slightly more configuration but supports heavier compute. Good if you want the full Stan sampling to
  run in the browser (though this is slow and not recommended for non-coders).

  ---
  Summary Priority List

  Priority: Before submission
  Action: Delete empty notebook, fix hardcoded paths in notebooks, move SI_code2 to manuscripts/, add CITATION.cff, remove
    legacy_TEXAS_20250822.tar.gz
  ────────────────────────────────────────
  Priority: Before submission
  Action: Add data download instructions / Zenodo for data
  ────────────────────────────────────────
  Priority: For coders
  Action: Push pre-built Docker image to GHCR, add run.sh, fix commented-out Dockerfile lines
  ────────────────────────────────────────
  Priority: For non-coders
  Action: Deploy Streamlit app to Community Cloud, bundle forward posteriors, add sample CSV
  ────────────────────────────────────────
  Priority: Nice to have
  Action: Add a minimal test suite, Zenodo DOI for the software itself
