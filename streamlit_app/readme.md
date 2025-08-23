# TEXAS GUI - Refactored Component Architecture

A modular, component-based Streamlit application for exploring TEXAS temperature reconstructions and posterior distributions.

## Directory Structure

```
streamlit_app/
├── main.py                 # Entry point - run with `streamlit run main.py`
├── config.py              # Configuration constants and settings
├── README.md              # This file
├── utils/                 # Core utilities
│   ├── __init__.py
│   ├── data_processing.py # Data transformation functions
│   ├── file_handling.py   # File I/O operations
│   └── plotting.py        # Matplotlib plotting utilities
├── components/            # Reusable UI components
│   ├── __init__.py
│   ├── file_selector.py   # File upload/selection widgets
│   ├── plot_controls.py   # Plot configuration controls
│   └── data_info.py       # Dataset information displays
└── pages/                 # Tab content modules
    ├── __init__.py
    ├── prediction.py      # Temperature prediction tab
    ├── exploration.py     # Posterior exploration tab
    └── computation.py     # Advanced computation tab
```

## Features

### 🎯 **Temperature Prediction Tab**
- CSV upload or repository file selection
- Flexible column mapping for RI data
- Integration with TEXAS prediction functions
- Results visualization and download

### 📊 **Posterior Exploration Tab**
- **Multi-file NetCDF support** (from cache or upload)
- **Multi-parameter plotting** with subplot grids
- **Flexible data processing**: flatten, mean, median, std, min, max over any axis
- **Histogram ↔ KDE toggle** with bandwidth control
- **Multiple plot types**: histograms, time series, 2D heatmaps
- **Comprehensive dataset information**: dimensions, coordinates, attributes
- **Smart MCMC handling**: automatic detection of (chains, draws) structures

### ⚙️ **Advanced Computation Tab**
- Direct interface to TEXAS sampling functions
- JSON parameter input with examples
- NetCDF result download

## Key Improvements Over Monolithic Version

### 🧩 **Modular Architecture**
- **Separation of concerns**: Data processing, UI components, and business logic are cleanly separated
- **Reusable components**: File selectors, plot controls, and data displays can be used across tabs
- **Easy maintenance**: Individual modules can be updated without affecting others

### 📈 **Enhanced Functionality**
- **Smart data handling**: Automatic detection and processing of (chains, draws) MCMC structures
- **Flexible visualization**: Multiple plot types with user-controlled processing options
- **Professional plots**: KDE smoothing, subplot grids, and comprehensive statistical summaries

### 🛠️ **Developer Benefits**
- **Testable code**: Individual functions can be unit tested
- **Clear interfaces**: Well-defined function signatures and documentation
- **Extensible design**: Easy to add new plot types, data sources, or processing methods

## Running the Application

1. Ensure TEXAS is installed and importable
2. Install required dependencies:
   ```bash
   pip install streamlit pandas numpy xarray matplotlib scipy
   ```
3. Run the application:
   ```bash
   streamlit run main.py
   ```

## Configuration

Edit `config.py` to customize:
- Cache directory paths
- Default CSV directories
- Plot settings and defaults
- UI behavior parameters

## Adding New Features

### New Plot Types
1. Add plotting function to `utils/plotting.py`
2. Add plot type to `config.PLOT_TYPES`
3. Update `pages/exploration.py` to handle the new type

### New Data Processing Methods
1. Add method to `utils/data_processing.py`
2. Update `config.DATA_REDUCTION_METHODS`
3. Method will automatically appear in UI controls

### New UI Components
1. Create reusable component in `components/`
2. Import and use in relevant pages
3. Components automatically inherit Streamlit caching and state management

## Architecture Benefits

- **Maintainable**: Clear module boundaries make debugging easier
- **Scalable**: New features can be added without touching existing code
- **Testable**: Individual components can be tested in isolation
- **Collaborative**: Multiple developers can work on different modules simultaneously