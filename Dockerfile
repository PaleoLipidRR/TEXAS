# Use official Python 3.10 slim image as base
FROM python:3.10-slim

# Install system dependencies needed by scientific/plotting Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy your package code into the image
COPY TEXAS /app/TEXAS

# Copy requirements.txt into the image
COPY requirements.txt /app/

# Install Python packages
RUN pip install --upgrade pip && pip install -r requirements.txt

# (Optional) Copy any main script or entry point
# COPY streamlit_app.py /app/
# Or copy notebooks/scripts as needed

# Default: start Python interactive shell
# (Change this to run your script, start Jupyter, or Streamlit as desired)
CMD ["python"]
