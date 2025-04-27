from setuptools import setup, find_packages

setup(
    name="culRIBayesian",
    version="0.1.0",
    description="Bayesian GDGT–temperature utilities",
    author="Ronnakrit Rattanasriampaipong (paleolipidrr)",
    packages=find_packages(),
    install_requires=[
        "cmdstanpy>=1.0",
        "xarray>=0.20",
        "numpy>=1.20",
    ],
    package_data={
        # Include all the .stan files you moved under your_pkg/stan_models/
        "culRIBayesian": ["stan_models/*.stan"],
    },
    include_package_data=True,
    python_requires=">=3.7",
)
