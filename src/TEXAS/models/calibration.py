"""
TEX86-SST calibration models
"""

import numpy as np
from typing import Union, Literal, Optional, Sequence, Dict

class TEX86Calibration:
    """
    TEX86-SST calibration model with forward and inverse predictions.
    
    Supports multiple transformation types:
    - 'linear': SST = a*TEX86 + b
    - 'log10': SST = a*log10(TEX86) + b (kim2010)
    - 'ln': SST = a*ln(TEX86) + b (low23_lnTEX)
    - 'inverse': SST = a*(1/TEX86) + b (liu2009)
    """
    
    def __init__(
        self,
        name: str,
        slope: float,
        intercept: float,
        transform: Literal['linear', 'log10', 'ln', 'inverse'] = 'linear'
    ):
        """
        Parameters
        ----------
        name : str
            Calibration name (e.g., 'kim2010_tex86H')
        slope : float
            Slope parameter (a)
        intercept : float
            Intercept parameter (b)
        transform : str
            Transformation type: 'linear', 'log10', 'ln', 'inverse'
        """
        self.name = name
        self.slope = slope
        self.intercept = intercept
        self.transform = transform
        
    def predict_sst(self, tex86: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Predict SST from TEX86.
        
        Parameters
        ----------
        tex86 : float or array
            TEX86 values
            
        Returns
        -------
        sst : float or array
            Predicted SST (°C)
        """
        if self.transform == 'linear':
            predictor = tex86
        elif self.transform == 'log10':
            predictor = np.log10(tex86)
        elif self.transform == 'ln':
            predictor = np.log(tex86)
        elif self.transform == 'inverse':
            predictor = 1 / tex86
        else:
            raise ValueError(f"Unknown transform: {self.transform}")
        
        sst = self.slope * predictor + self.intercept
        return sst
    
    def predict_tex86(self, sst: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Predict TEX86 from SST (inverse calibration).
        
        Parameters
        ----------
        sst : float or array
            Sea surface temperature (°C)
            
        Returns
        -------
        tex86 : float or array
            Predicted TEX86 values
        """
        if self.transform == 'linear':
            tex86 = (sst - self.intercept) / self.slope
            
        elif self.transform == 'log10':
            # SST = a*log10(TEX) + b → log10(TEX) = (SST - b)/a → TEX = 10^((SST-b)/a)
            tex86 = 10 ** ((sst - self.intercept) / self.slope)
            
        elif self.transform == 'ln':
            # SST = a*ln(TEX) + b → ln(TEX) = (SST - b)/a → TEX = e^((SST-b)/a)
            tex86 = np.exp((sst - self.intercept) / self.slope)
            
        elif self.transform == 'inverse':
            # SST = a*(1/TEX) + b → 1/TEX = (SST - b)/a → TEX = a/(SST - b)
            tex86 = self.slope / (sst - self.intercept)
        else:
            raise ValueError(f"Unknown transform: {self.transform}")
        
        return tex86
    
    def __repr__(self):
        return f"TEX86Calibration(name='{self.name}', transform='{self.transform}')"


class BAYSPARCalibration:
    """
    Wrapper around baysparpy (Tierney & Tingley) for Bayesian TEX86->SST/subT
    reconstruction.

    Unlike TEX86Calibration (a fixed slope/intercept transform), BAYSPAR is
    itself an inverse Bayesian method: prediction returns a posterior
    ensemble, not a point value. Requires the optional `baysparpy` package
    (`pip install baysparpy`; bundled under the `dev` extra).

    Two prediction modes, matched to baysparpy's own split:
    - 'standard': spatial regression at the nearest calibration grid cell.
      Requires lon/lat. Appropriate when tex86 is within the modern range
      at that location.
    - 'analog': searches the core-top database for locations with similar
      tex86 values and pools their regression parameters. Requires
      prior_mean (a prior SST/subT estimate); use for out-of-modern-range
      values (e.g. hyperthermal samples).
    """

    def __init__(self, mode: Literal['standard', 'analog'] = 'standard'):
        if mode not in ('standard', 'analog'):
            raise ValueError(f"mode must be 'standard' or 'analog', got {mode!r}")
        self.mode = mode
        self._bsr = self._import_bayspar()

    @staticmethod
    def _import_bayspar():
        try:
            import bayspar as bsr
        except ImportError as exc:
            raise ImportError(
                "BAYSPARCalibration requires the optional 'baysparpy' package. "
                "Install with: pip install baysparpy"
            ) from exc
        return bsr

    @staticmethod
    def _percentile(pred, q, method: str = 'nearest') -> np.ndarray:
        """
        numpy-2-safe replacement for baysparpy's Prediction.percentile().

        baysparpy <=0.0.3 calls np.percentile(..., interpolation=...), a kwarg
        removed in numpy 2.0 (renamed to method=). Reimplemented directly
        against pred.ensemble instead of relying on the library's own call.
        Handles both the 2D ensemble from predict_seatemp (n_obs, n_draws)
        and the 3D ensemble from predict_seatemp_analog
        (n_obs, n_analogs, n_draws), pooling over every non-observation axis.
        Returns shape (n_obs, len(q)).
        """
        q = np.asarray(q, dtype=np.float64)
        axes = tuple(range(1, pred.ensemble.ndim))
        return np.percentile(pred.ensemble, q=q, axis=axes, method=method).T

    def predict_sst(
        self,
        tex86: Union[np.ndarray, list],
        *,
        lon: Optional[float] = None,
        lat: Optional[float] = None,
        prior_mean: Optional[Union[float, np.ndarray]] = None,
        prior_std: float = 10.0,
        search_tolerance: Optional[float] = None,
        temptype: Literal['sst', 'subt'] = 'sst',
        percentiles: Sequence[float] = (16, 50, 84),
        nens: int = 1000,
    ) -> Dict[str, np.ndarray]:
        """
        Predict SST/subT from TEX86 via BAYSPAR.

        Parameters
        ----------
        tex86 : array-like
            TEX86 values.
        lon, lat : float, required for mode='standard'
            Site location, used to select the nearest spatial calibration
            parameters.
        prior_mean, prior_std : float, required (prior_mean) for mode='analog'
            Prior temperature mean/SD (degC) used for the analog search.
        search_tolerance : float, optional (analog mode only)
            TEX86 tolerance for the analog search. None -> baysparpy's
            internal default.
        temptype : 'sst' or 'subt'
            Target temperature type.
        percentiles : sequence of float
            Percentiles to summarize the posterior ensemble at.
        nens : int
            Ensemble draws per analog (analog mode only).

        Returns
        -------
        dict with keys:
            'ensemble' : ndarray -- raw BAYSPAR posterior draws
            'percentiles' : ndarray, shape (n_obs, len(percentiles))
            'percentile_labels' : the `percentiles` argument, for column labeling
        """
        tex86 = np.asarray(tex86, dtype=float)

        if self.mode == 'standard':
            if lon is None or lat is None:
                raise ValueError("mode='standard' requires lon and lat.")
            pred = self._bsr.predict_seatemp(
                tex86, lon=lon, lat=lat, prior_std=prior_std, temptype=temptype,
            )
        else:  # analog
            if prior_mean is None:
                raise ValueError("mode='analog' requires prior_mean.")
            kwargs = dict(
                prior_mean=prior_mean, prior_std=prior_std,
                temptype=temptype, nens=nens,
            )
            if search_tolerance is not None:
                kwargs['search_tol'] = search_tolerance
            pred = self._bsr.predict_seatemp_analog(tex86, **kwargs)

        if pred.ensemble.size == 0:
            raise RuntimeError(
                f"BAYSPAR ({self.mode}) returned an empty ensemble"
                + (" -- no analogs within the given search tolerance."
                   if self.mode == 'analog' else ".")
            )

        return {
            'ensemble': pred.ensemble,
            'percentiles': self._percentile(pred, percentiles),
            'percentile_labels': list(percentiles),
        }

    def __repr__(self):
        return f"BAYSPARCalibration(mode='{self.mode}')"


class CalibrationRegistry:
    """Registry of available TEX86-SST calibrations."""
    
    # Define all available calibrations
    _CALIBRATIONS = {
        # Linear calibrations
        'schouten02': TEX86Calibration('schouten02', 66.6667, -18.6667, 'linear'),
        'schouten03': TEX86Calibration('schouten03', 37.0370, 0.5926, 'linear'),
        'kim2008': TEX86Calibration('kim2008', 56.2000, -10.7800, 'linear'),
        'OBrien17': TEX86Calibration('OBrien17', 58.8235, -11.1765, 'linear'),
        
        # Non-linear calibrations
        'liu2009': TEX86Calibration('liu2009', -16.3000, 50.4750, 'inverse'),
        'kim2010_tex86H': TEX86Calibration('kim2010_tex86H', 68.4, 38.6, 'log10'),
        'kim2010_tex86L': TEX86Calibration('kim2010_tex86L', 67.5, 46.9, 'log10'),
        
        # Coretop calibrations
        'allCoretop_linear_exclRS_above5degC': TEX86Calibration(
            'allCoretop_linear_exclRS_above5degC', 67.63154335, -17.85292574, 'linear'
        ),

        # Low et al. 2023 calibrations
        'low23_crtp_lnTEX': TEX86Calibration('low23_crtp_lnTEX', 35.5891263830379, 41.3154356803057, 'ln'),
        'low23_crtp_linear': TEX86Calibration('low23_crtp_linear', 69.61698822, -16.73443208, 'linear'),
        'low23_crtp_cultureAllAOA_lnTEX': TEX86Calibration(
            'low23_crtp_cultureAllAOA_lnTEX', 37.32224813, 44.59294303, 'ln'
        ),
        'low23_crtp_cultureAllAOA_linear': TEX86Calibration(
            'low23_crtp_cultureAllAOA_linear', 65.2193, -14.8708, 'linear'
        ),
        'low23_crtp_cultureMarineAOA_lnTEX': TEX86Calibration(
            'low23_crtp_cultureMarineAOA_lnTEX', 32.39639713, 40.83593007, 'ln'
        ),
        'low23_crtp_cultureMarineAOA_linear': TEX86Calibration(
            'low23_crtp_cultureMarineAOA_linear', 62.32280847, -13.4871, 'linear'
        ),
    }
    
    @classmethod
    def get(cls, name: str) -> TEX86Calibration:
        """
        Get calibration by name.
        
        Parameters
        ----------
        name : str
            Calibration name
            
        Returns
        -------
        calibration : TEX86Calibration
            Calibration object
        """
        if name not in cls._CALIBRATIONS:
            available = ', '.join(cls._CALIBRATIONS.keys())
            raise ValueError(f"Unknown calibration '{name}'. Available: {available}")
        return cls._CALIBRATIONS[name]
    
    @classmethod
    def list_calibrations(cls) -> list[str]:
        """List all available calibration names."""
        return list(cls._CALIBRATIONS.keys())
    
    @classmethod
    def add_calibration(cls, name: str, slope: float, intercept: float, 
                       transform: str = 'linear'):
        """
        Add a custom calibration to the registry.
        
        Parameters
        ----------
        name : str
            Calibration name
        slope : float
            Slope parameter
        intercept : float
            Intercept parameter
        transform : str
            Transformation type: 'linear', 'log10', 'ln', 'inverse'
        """
        if name in cls._CALIBRATIONS:
            raise ValueError(f"Calibration '{name}' already exists")
        cls._CALIBRATIONS[name] = TEX86Calibration(name, slope, intercept, transform)


# Convenience functions for backward compatibility
def predict_sst_from_tex86(
    tex86: Union[float, np.ndarray],
    method: str = 'kim2010_tex86H'
) -> Union[float, np.ndarray]:
    """
    Predict SST from TEX86 using a specific calibration.
    
    Parameters
    ----------
    tex86 : float or array
        TEX86 values
    method : str
        Calibration method name
        
    Returns
    -------
    sst : float or array
        Predicted SST (°C)
    """
    calibration = CalibrationRegistry.get(method)
    return calibration.predict_sst(tex86)


def predict_tex86_from_sst(
    sst: Union[float, np.ndarray],
    method: str = 'kim2010_tex86H'
) -> Union[float, np.ndarray]:
    """
    Predict TEX86 from SST using a specific calibration.
    
    Parameters
    ----------
    sst : float or array
        Sea surface temperature (°C)
    method : str
        Calibration method name
        
    Returns
    -------
    tex86 : float or array
        Predicted TEX86 values
    """
    calibration = CalibrationRegistry.get(method)
    return calibration.predict_tex86(sst)