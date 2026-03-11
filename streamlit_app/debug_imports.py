import sys
sys.path.insert(0, '.')

print('1. config...', flush=True)
from config import INV_CACHE_DIR, FWD_CACHE_DIR
print('   OK -', FWD_CACHE_DIR, flush=True)

print('2. TEXAS.stan.invT...', flush=True)
try:
    from TEXAS.stan.invT import predict_temperature_from_RI
    print('   OK', flush=True)
except Exception as e:
    print('   skipped:', e, flush=True)

print('3. TEXAS.stan.sampler...', flush=True)
try:
    from TEXAS.stan.sampler import get_posterior
    print('   OK', flush=True)
except Exception as e:
    print('   skipped:', e, flush=True)

print('4. plotly...', flush=True)
import plotly.graph_objects as go
print('   OK', flush=True)

print('5. calibration_data page...', flush=True)
from pages.calibration_data import render_calibration_tab
print('   OK', flush=True)

print('All done.', flush=True)
