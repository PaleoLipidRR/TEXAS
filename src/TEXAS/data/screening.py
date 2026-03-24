"""
Data quality control and outlier screening tools.
"""

from scipy.spatial.distance import mahalanobis
from scipy.linalg import inv, pinv, LinAlgError
from scipy.stats import chi2
import numpy as np
import pandas as pd
from typing import Optional, Literal

from matplotlib.patches import Ellipse
import matplotlib.pyplot as plt
from matplotlib.transforms import Affine2D

class MahalanobisOutlierDetector:
    """
    Fit Mahalanobis distance parameters on training data, apply to any dataset.
    
    Examples
    --------
    >>> # Fit on coretop data
    >>> detector = MahalanobisOutlierDetector(['TEX86', 'ringIndex'], confidence=0.99)
    >>> detector.fit(coretop_df)
    >>> coretop_df['mahal_dist'] = detector.transform(coretop_df)
    >>> coretop_df['outliers'] = detector.detect_outliers(coretop_df)
    >>> 
    >>> # Apply to downcore data
    >>> downcore_df['mahal_dist'] = detector.transform(downcore_df)
    >>> downcore_df['outliers'] = detector.detect_outliers(downcore_df)
    """
    
    def __init__(
        self,
        features: list[str],
        confidence: float = 0.99,
        method: Literal['chi2', 'chi2_rounddown'] = 'chi2',
        use_pinv_if_singular: bool = True
    ):
        """
        Parameters
        ----------
        features : list[str]
            Feature column names to use for distance calculation
        confidence : float, default=0.99
            Confidence level for outlier threshold (0-1)
        method : {'chi2', 'chi2_rounddown'}, default='chi2'
            Method for threshold calculation
        use_pinv_if_singular : bool, default=True
            Use pseudo-inverse if covariance matrix is singular
        """
        self.features = features
        self.confidence = confidence
        self.method = method
        self.use_pinv_if_singular = use_pinv_if_singular
        
        # Fitted parameters (set during fit())
        self.mean_vec = None
        self.inv_cov = None
        self.threshold = None
        self.is_fitted = False
        
    def fit(self, df: pd.DataFrame) -> 'MahalanobisOutlierDetector':
        """
        Fit mean, covariance, and threshold on training data.
        
        Parameters
        ----------
        df : pd.DataFrame
            Training data
            
        Returns
        -------
        self : MahalanobisOutlierDetector
            Fitted detector instance
        """
        # Clean & get valid rows
        X = df[self.features].replace([np.inf, -np.inf], np.nan)
        X_valid = X.dropna().to_numpy(dtype=float)
        
        if len(X_valid) == 0:
            raise ValueError("No valid data rows after removing NaN/Inf values")
        
        # Compute mean and inverse covariance
        self.mean_vec = np.mean(X_valid, axis=0)
        cov = np.cov(X_valid, rowvar=False)
        
        try:
            self.inv_cov = inv(cov)
        except LinAlgError:
            if not self.use_pinv_if_singular:
                raise
            self.inv_cov = pinv(cov)
        
        # Compute threshold from chi-square distribution
        dof = len(self.features)
        if self.method == 'chi2':
            thr_squared = chi2.ppf(self.confidence, df=dof)
        elif self.method == 'chi2_rounddown':
            thr_squared = self._round_down_to_nearest_5(
                np.round(chi2.ppf(self.confidence, df=dof), 2)
            )
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        self.threshold = np.sqrt(thr_squared)
        self.is_fitted = True
        
        return self
    
    @staticmethod
    def _round_down_to_nearest_5(x: float) -> float:
        """Round down to nearest 0.05."""
        return np.floor(x * 20) / 20
    
    def _compute_distances(self, df: pd.DataFrame) -> pd.Series:
        """
        Internal method to compute Mahalanobis distances.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to compute distances for
            
        Returns
        -------
        distances : pd.Series
            Mahalanobis distances (NaN for invalid rows)
        """
        if not self.is_fitted:
            raise ValueError("Must call fit() before computing distances")
        
        X = df[self.features].replace([np.inf, -np.inf], np.nan)
        valid_idx = X.dropna().index
        X_valid = X.loc[valid_idx].to_numpy(dtype=float)
        
        # Compute distances
        dists = [mahalanobis(x, self.mean_vec, self.inv_cov) for x in X_valid]
        
        # Aligned output
        out = pd.Series(np.nan, index=df.index, dtype=float, name='mahalanobis_distance')
        out.loc[valid_idx] = dists
        
        return out
    
    def transform(
        self,
        df: pd.DataFrame,
        col_name: Optional[str] = None
    ) -> pd.Series:
        """
        Compute Mahalanobis distances using fitted parameters.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to transform
        col_name : str, optional
            If provided, add distances to df as this column
            
        Returns
        -------
        distances : pd.Series
            Mahalanobis distances
        """
        distances = self._compute_distances(df)
        
        if col_name:
            df[col_name] = distances
        
        return distances
    
    def detect_outliers(
        self,
        df: pd.DataFrame,
        col_name: Optional[str] = None
    ) -> pd.Series:
        """
        Detect outliers using fitted threshold.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to screen
        col_name : str, optional
            If provided, add outlier flags to df as this column
            
        Returns
        -------
        outliers : pd.Series
            Boolean series (True=outlier, False=inlier, NaN=invalid)
        """
        distances = self._compute_distances(df)
        
        # Flag outliers
        flags = pd.Series(np.nan, index=df.index, dtype="float", name='outlier_flag')
        valid = distances.notna()
        flags.loc[valid] = (distances.loc[valid] ** 2) > (self.threshold ** 2)
        flags = flags.astype("boolean")
        
        if col_name:
            df[col_name] = flags
        
        return flags
    
    def detect_outliers_manual(
        self,
        df: pd.DataFrame,
        col_name: Optional[str] = None,
        exclude_condition: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Detect outliers with manual exception rules.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to screen
        col_name : str, optional
            If provided, add manual outlier flags to df as this column
        exclude_condition : pd.Series, optional
            Boolean series indicating samples to exclude from outlier detection.
            If None, applies default: (ringIndex > 3) & (TEX86 > 0.7)
            
        Returns
        -------
        manual_outliers : pd.Series
            Boolean series with manual exceptions applied
            
        Examples
        --------
        >>> # Use default exception
        >>> outliers = detector.detect_outliers_manual(df)
        >>> 
        >>> # Custom exception
        >>> custom_exclude = (df['SST'] > 30) & (df['TEX86'] > 0.8)
        >>> outliers = detector.detect_outliers_manual(df, exclude_condition=custom_exclude)
        """
        outliers = self.detect_outliers(df)
        
        # Apply manual exception
        if exclude_condition is None:
            # Default: exclude high RI + high TEX86 samples
            if 'ringIndex' in self.features and 'TEX86' in self.features:
                exclude_condition = (df['ringIndex'] > (0.75*4)) & (df['TEX86'] > 0.75)
            elif 'proxyObs' in self.features and 'TEX86' in self.features:
                exclude_condition = (df['proxyObs'] > 0.75) & (df['TEX86'] > 0.75)
            elif 'scaledRI' in self.features and 'TEX86' in self.features:  # backward compat
                exclude_condition = (df['scaledRI'] > 0.75) & (df['TEX86'] > 0.75)
            else:
                exclude_condition = pd.Series(False, index=df.index)
        
        manual_outliers = outliers & ~exclude_condition
        
        if col_name:
            df[col_name] = manual_outliers
        
        return manual_outliers
    
    def fit_transform(
        self,
        df: pd.DataFrame,
        dist_col: Optional[str] = None,
        outlier_col: Optional[str] = None,
        manual_outlier_col: Optional[str] = None
    ) -> dict:
        """
        Fit and transform in one step.
        
        Parameters
        ----------
        df : pd.DataFrame
            Training data
        dist_col : str, optional
            Column name for distances
        outlier_col : str, optional
            Column name for outlier flags
        manual_outlier_col : str, optional
            Column name for manual outlier flags
            
        Returns
        -------
        results : dict
            Dictionary containing:
            - 'distances': Mahalanobis distances
            - 'outliers': Outlier flags
            - 'manual_outliers': Manual outlier flags
            - 'threshold': Computed threshold
        """
        self.fit(df)
        
        distances = self.transform(df, dist_col)
        outliers = self.detect_outliers(df, outlier_col)
        manual_outliers = self.detect_outliers_manual(df, manual_outlier_col)
        
        return {
            'distances': distances,
            'outliers': outliers,
            'manual_outliers': manual_outliers,
            'threshold': self.threshold
        }
    
    def get_params(self) -> dict:
        """
        Get fitted parameters.
        
        Returns
        -------
        params : dict
            Dictionary of fitted parameters
        """
        if not self.is_fitted:
            raise ValueError("Detector has not been fitted yet")
        
        return {
            'mean_vec': self.mean_vec,
            'inv_cov': self.inv_cov,
            'threshold': self.threshold,
            'features': self.features,
            'confidence': self.confidence,
            'method': self.method
        }
    
    def __repr__(self):
        fitted_str = "fitted" if self.is_fitted else "not fitted"
        return (f"MahalanobisOutlierDetector(features={self.features}, "
                f"confidence={self.confidence}, {fitted_str})")
        
        
    def get_confidence_ellipse_params(self, n_std: float = None) -> dict:
        """
        Get parameters for drawing confidence ellipse (2D only).
        
        Parameters
        ----------
        n_std : float, optional
            Number of standard deviations for ellipse.
            If None, uses fitted threshold.
            
        Returns
        -------
        params : dict
            Dictionary with 'center', 'width', 'height', 'angle'
            
        Raises
        ------
        ValueError
            If detector is not fitted or has != 2 features
        """
        if not self.is_fitted:
            raise ValueError("Must call fit() before getting ellipse parameters")
        
        if len(self.features) != 2:
            raise ValueError(f"Ellipse visualization only works for 2D data, got {len(self.features)} features")
        
        # Use threshold if n_std not provided
        if n_std is None:
            n_std = self.threshold
        
        # Get covariance matrix (inverse of inv_cov)
        cov = inv(self.inv_cov)
        
        # Eigendecomposition to get ellipse parameters
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        
        # Calculate ellipse parameters
        angle = np.degrees(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0]))
        width = 2 * n_std * np.sqrt(eigenvalues[0])
        height = 2 * n_std * np.sqrt(eigenvalues[1])
        
        return {
            'center': self.mean_vec,
            'width': width,
            'height': height,
            'angle': angle,
            'eigenvalues': eigenvalues,
            'eigenvectors': eigenvectors
        }
    
    def plot_ellipse(
        self,
        ax: plt.Axes = None,
        n_std: float = None,
        **kwargs
    ) -> Ellipse:
        """
        Plot confidence ellipse on matplotlib axes (2D only).
        
        Parameters
        ----------
        ax : matplotlib.axes.Axes, optional
            Axes to plot on. If None, uses current axes.
        n_std : float, optional
            Number of standard deviations. If None, uses fitted threshold.
        **kwargs
            Additional arguments passed to matplotlib.patches.Ellipse
            
        Returns
        -------
        ellipse : matplotlib.patches.Ellipse
            The ellipse patch object
            
        Examples
        --------
        >>> fig, ax = plt.subplots()
        >>> ax.scatter(df['TEX86'], df['ringIndex'])
        >>> detector.plot_ellipse(ax, facecolor='none', edgecolor='red', linewidth=2)
        """
        if ax is None:
            ax = plt.gca()
        
        params = self.get_confidence_ellipse_params(n_std)
        
        # Default styling
        ellipse_kwargs = {
            'facecolor': 'none',
            'edgecolor': 'red',
            'linewidth': 2,
            'linestyle': '--',
            'alpha': 0.8
        }
        ellipse_kwargs.update(kwargs)
        
        ellipse = Ellipse(
            xy=params['center'],
            width=params['width'],
            height=params['height'],
            angle=params['angle'],
            **ellipse_kwargs
        )
        
        ax.add_patch(ellipse)
        
        return ellipse
    
    def plot_decision_boundary(
        self,
        df: pd.DataFrame,
        ax: plt.Axes = None,
        plot_data: bool = True,
        show_outliers: bool = True,
        ellipse_kwargs: dict = None,
        scatter_kwargs: dict = None,
        outlier_kwargs: dict = None
    ) -> tuple:
        """
        Complete visualization with data points and decision boundary.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to visualize
        ax : matplotlib.axes.Axes, optional
            Axes to plot on
        plot_data : bool, default=True
            Whether to plot data points
        show_outliers : bool, default=True
            Whether to highlight outliers differently
        ellipse_kwargs : dict, optional
            Keyword arguments for ellipse
        scatter_kwargs : dict, optional
            Keyword arguments for inlier scatter plot
        outlier_kwargs : dict, optional
            Keyword arguments for outlier scatter plot
            
        Returns
        -------
        ax : matplotlib.axes.Axes
            The axes object
        ellipse : matplotlib.patches.Ellipse
            The ellipse patch
            
        Examples
        --------
        >>> detector = MahalanobisOutlierDetector(['TEX86', 'ringIndex'])
        >>> detector.fit(df)
        >>> fig, ax = plt.subplots()
        >>> detector.plot_decision_boundary(df, ax=ax)
        """
        if len(self.features) != 2:
            raise ValueError(f"Decision boundary plot only works for 2D data, got {len(self.features)} features")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        # Default kwargs
        if ellipse_kwargs is None:
            ellipse_kwargs = {}
        if scatter_kwargs is None:
            scatter_kwargs = {'c': 'gray6', 's': 30, 'alpha': 0.6, 'label': 'Inliers'}
        if outlier_kwargs is None:
            outlier_kwargs = {'c': 'red', 's': 50, 'alpha': 0.8, 'marker': 'x', 'label': 'Outliers'}
        
        # Plot data points
        if plot_data:
            x_data = df[self.features[0]]
            y_data = df[self.features[1]]
            
            if show_outliers:
                outliers = self.detect_outliers(df)
                
                # Plot inliers
                inlier_mask = ~outliers.fillna(False)
                ax.scatter(x_data[inlier_mask], y_data[inlier_mask], **scatter_kwargs)
                
                # Plot outliers
                outlier_mask = outliers.fillna(False)
                if outlier_mask.any():
                    ax.scatter(x_data[outlier_mask], y_data[outlier_mask], **outlier_kwargs)
            else:
                ax.scatter(x_data, y_data, **scatter_kwargs)
        
        # Plot ellipse
        ellipse = self.plot_ellipse(ax, **ellipse_kwargs)
        
        # Labels
        ax.set_xlabel(self.features[0])
        ax.set_ylabel(self.features[1])
        ax.legend()
        
        return ax, ellipse
    
    def plot_multiple_ellipses(
        self,
        df: pd.DataFrame,
        ax: plt.Axes = None,
        n_std_levels: list = None,
        colors: list = None,
        **kwargs
    ):
        """
        Plot multiple confidence ellipses at different threshold levels.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to visualize
        ax : matplotlib.axes.Axes, optional
            Axes to plot on
        n_std_levels : list, optional
            List of standard deviation levels. Default: [1, 2, 3, threshold]
        colors : list, optional
            Colors for each ellipse level
        **kwargs
            Additional arguments passed to scatter plot
            
        Examples
        --------
        >>> detector.plot_multiple_ellipses(df, n_std_levels=[1, 2, 2.5, 3])
        """
        if len(self.features) != 2:
            raise ValueError(f"Ellipse plot only works for 2D data, got {len(self.features)} features")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        if n_std_levels is None:
            n_std_levels = [1, 2, 3, self.threshold]
        
        if colors is None:
            colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(n_std_levels)))
        
        # Plot data
        x_data = df[self.features[0]]
        y_data = df[self.features[1]]
        scatter_kwargs = {'c': 'gray6', 's': 20, 'alpha': 0.4, 'zorder': 1}
        scatter_kwargs.update(kwargs)
        ax.scatter(x_data, y_data, **scatter_kwargs)
        
        # Plot ellipses
        for n_std, color in zip(n_std_levels, colors):
            label = f'{n_std:.2f}σ' if n_std != self.threshold else f'Threshold ({self.threshold:.2f})'
            self.plot_ellipse(
                ax,
                n_std=n_std,
                edgecolor=color,
                linewidth=2 if n_std == self.threshold else 1,
                linestyle='--',
                label=label,
                zorder=2
            )
        
        ax.set_xlabel(self.features[0])
        ax.set_ylabel(self.features[1])
        ax.legend()
        
        return ax
    
    def plot_pairwise_ellipses(
        self,
        df: pd.DataFrame,
        figsize: tuple = None,
        show_outliers: bool = True,
        ellipse_kwargs: dict = None,
        scatter_kwargs: dict = None,
        outlier_kwargs: dict = None
    ):
        """
        Plot pairwise 2D projections with confidence ellipses for high-dimensional data.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to visualize
        figsize : tuple, optional
            Figure size. Auto-calculated if None.
        show_outliers : bool, default=True
            Whether to highlight outliers
        ellipse_kwargs : dict, optional
            Keyword arguments for ellipses
        scatter_kwargs : dict, optional
            Keyword arguments for inlier scatter
        outlier_kwargs : dict, optional
            Keyword arguments for outlier scatter
            
        Returns
        -------
        fig : matplotlib.figure.Figure
            Figure object
        axs : array of matplotlib.axes.Axes
            Array of axes objects
            
        Examples
        --------
        >>> detector = MahalanobisOutlierDetector(['TEX86', 'ringIndex', 'fGDGT_0', 'fGDGT_cren'])
        >>> detector.fit(coretop_df)
        >>> fig, axs = detector.plot_pairwise_ellipses(coretop_df)
        """
        if not self.is_fitted:
            raise ValueError("Must call fit() before plotting")
        
        n_features = len(self.features)
        feature_pairs = list(combinations(range(n_features), 2))
        n_pairs = len(feature_pairs)
        
        # Calculate grid dimensions
        n_cols = int(np.ceil(np.sqrt(n_pairs)))
        n_rows = int(np.ceil(n_pairs / n_cols))
        
        if figsize is None:
            figsize = (4 * n_cols, 3.5 * n_rows)
        
        fig, axs = plt.subplots(n_rows, n_cols, figsize=figsize)
        axs = np.atleast_1d(axs).flatten()
        
        # Default styling
        if ellipse_kwargs is None:
            ellipse_kwargs = {'facecolor': 'red', 'alpha': 0.1, 'edgecolor': 'red', 'linewidth': 2}
        if scatter_kwargs is None:
            scatter_kwargs = {'c': 'gray6', 's': 20, 'alpha': 0.5}
        if outlier_kwargs is None:
            outlier_kwargs = {'c': 'red', 's': 40, 'marker': 'x', 'alpha': 0.8}
        
        # Get outlier flags once
        if show_outliers:
            outliers = self.detect_outliers(df).fillna(False)
            inliers = ~outliers
        
        # Plot each pair
        for idx, (i, j) in enumerate(feature_pairs):
            ax = axs[idx]
            
            feat_i = self.features[i]
            feat_j = self.features[j]
            
            # Create marginal 2D detector for this pair
            pair_detector = MahalanobisOutlierDetector(
                [feat_i, feat_j],
                confidence=self.confidence,
                method=self.method
            )
            
            # Fit on the same data (marginal distribution)
            pair_detector.fit(df)
            
            # Plot data
            if show_outliers:
                ax.scatter(df.loc[inliers, feat_i], df.loc[inliers, feat_j], 
                          **scatter_kwargs, label='Inliers')
                if outliers.any():
                    ax.scatter(df.loc[outliers, feat_i], df.loc[outliers, feat_j], 
                              **outlier_kwargs, label='Outliers')
            else:
                ax.scatter(df[feat_i], df[feat_j], **scatter_kwargs)
            
            # Plot ellipse for this marginal distribution
            pair_detector.plot_ellipse(ax, **ellipse_kwargs)
            
            ax.set_xlabel(feat_i)
            ax.set_ylabel(feat_j)
            
            if idx == 0:
                ax.legend(fontsize=8)
        
        # Hide unused subplots
        for idx in range(n_pairs, len(axs)):
            axs[idx].set_visible(False)
        
        fig.tight_layout()
        return fig, axs
    
    def plot_pca_projection(
        self,
        df: pd.DataFrame,
        n_components: int = 2,
        ax: plt.Axes = None,
        show_outliers: bool = True,
        show_variance: bool = True,
        ellipse_kwargs: dict = None,
        scatter_kwargs: dict = None,
        outlier_kwargs: dict = None
    ):
        """
        Project high-dimensional data to 2D/3D using PCA and plot with ellipse.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to visualize
        n_components : int, default=2
            Number of PCA components (2 or 3)
        ax : matplotlib.axes.Axes, optional
            Axes to plot on
        show_outliers : bool, default=True
            Whether to highlight outliers
        show_variance : bool, default=True
            Whether to show explained variance in labels
        ellipse_kwargs : dict, optional
            Keyword arguments for ellipse
        scatter_kwargs : dict, optional
            Keyword arguments for inlier scatter
        outlier_kwargs : dict, optional
            Keyword arguments for outlier scatter
            
        Returns
        -------
        ax : matplotlib.axes.Axes
            Axes object
        pca : sklearn.decomposition.PCA
            Fitted PCA object
            
        Examples
        --------
        >>> detector = MahalanobisOutlierDetector(['TEX86', 'ringIndex', 'fGDGT_0', 'fGDGT_cren'])
        >>> detector.fit(coretop_df)
        >>> ax, pca = detector.plot_pca_projection(coretop_df)
        >>> print(f"Variance explained: {pca.explained_variance_ratio_}")
        """
        if not self.is_fitted:
            raise ValueError("Must call fit() before plotting")
        
        if n_components not in [2, 3]:
            raise ValueError("n_components must be 2 or 3")
        
        # Get valid data
        X = df[self.features].replace([np.inf, -np.inf], np.nan)
        valid_idx = X.dropna().index
        X_valid = X.loc[valid_idx].to_numpy(dtype=float)
        
        # Fit PCA
        pca = PCA(n_components=n_components)
        X_pca = pca.fit_transform(X_valid)
        
        # Create axes
        if ax is None:
            if n_components == 2:
                fig, ax = plt.subplots(figsize=(8, 6))
            else:
                fig = plt.figure(figsize=(10, 8))
                ax = fig.add_subplot(111, projection='3d')
        
        # Default styling
        if ellipse_kwargs is None:
            ellipse_kwargs = {'facecolor': 'red', 'alpha': 0.1, 'edgecolor': 'red', 'linewidth': 2}
        if scatter_kwargs is None:
            scatter_kwargs = {'c': 'gray6', 's': 20, 'alpha': 0.5}
        if outlier_kwargs is None:
            outlier_kwargs = {'c': 'red', 's': 40, 'marker': 'x', 'alpha': 0.8}
        
        # Get outliers
        outliers = self.detect_outliers(df)
        outliers_valid = outliers.loc[valid_idx].fillna(False)
        inliers_valid = ~outliers_valid
        
        # Plot data
        if n_components == 2:
            if show_outliers:
                ax.scatter(X_pca[inliers_valid, 0], X_pca[inliers_valid, 1], 
                          **scatter_kwargs, label='Inliers')
                if outliers_valid.any():
                    ax.scatter(X_pca[outliers_valid, 0], X_pca[outliers_valid, 1], 
                              **outlier_kwargs, label='Outliers')
            else:
                ax.scatter(X_pca[:, 0], X_pca[:, 1], **scatter_kwargs)
            
            # Create temporary dataframe for PCA space
            pca_df = pd.DataFrame(X_pca, columns=['PC1', 'PC2'], index=valid_idx)
            
            # Fit detector in PCA space
            pca_detector = MahalanobisOutlierDetector(['PC1', 'PC2'], 
                                                      confidence=self.confidence,
                                                      method=self.method)
            pca_detector.fit(pca_df)
            pca_detector.plot_ellipse(ax, **ellipse_kwargs)
            
            # Labels
            var1, var2 = pca.explained_variance_ratio_
            if show_variance:
                ax.set_xlabel(f'PC1 ({var1:.1%} variance)')
                ax.set_ylabel(f'PC2 ({var2:.1%} variance)')
            else:
                ax.set_xlabel('PC1')
                ax.set_ylabel('PC2')
            
        else:  # 3D
            if show_outliers:
                ax.scatter(X_pca[inliers_valid, 0], X_pca[inliers_valid, 1], 
                          X_pca[inliers_valid, 2], **scatter_kwargs, label='Inliers')
                if outliers_valid.any():
                    ax.scatter(X_pca[outliers_valid, 0], X_pca[outliers_valid, 1], 
                              X_pca[outliers_valid, 2], **outlier_kwargs, label='Outliers')
            else:
                ax.scatter(X_pca[:, 0], X_pca[:, 1], X_pca[:, 2], **scatter_kwargs)
            
            # Labels
            var1, var2, var3 = pca.explained_variance_ratio_
            if show_variance:
                ax.set_xlabel(f'PC1 ({var1:.1%} variance)')
                ax.set_ylabel(f'PC2 ({var2:.1%} variance)')
                ax.set_zlabel(f'PC3 ({var3:.1%} variance)')
            else:
                ax.set_xlabel('PC1')
                ax.set_ylabel('PC2')
                ax.set_zlabel('PC3')
        
        ax.legend()
        return ax, pca
    
    def plot_corner(
        self,
        df: pd.DataFrame,
        figsize: tuple = None,
        show_outliers: bool = True,
        **kwargs
    ):
        """
        Create corner plot (lower triangle pairwise plots with marginals).
        Similar to corner.py but integrated with Mahalanobis detection.
        
        Parameters
        ----------
        df : pd.DataFrame
            Data to visualize
        figsize : tuple, optional
            Figure size
        show_outliers : bool, default=True
            Whether to highlight outliers
        **kwargs
            Additional styling arguments
            
        Returns
        -------
        fig : matplotlib.figure.Figure
            Figure object
        axs : array of matplotlib.axes.Axes
            Grid of axes
        """
        if not self.is_fitted:
            raise ValueError("Must call fit() before plotting")
        
        n_features = len(self.features)
        
        if figsize is None:
            figsize = (2.5 * n_features, 2.5 * n_features)
        
        fig, axs = plt.subplots(n_features, n_features, figsize=figsize)
        
        # Get outliers
        if show_outliers:
            outliers = self.detect_outliers(df).fillna(False)
            inliers = ~outliers
        
        for i in range(n_features):
            for j in range(n_features):
                ax = axs[i, j]
                
                if j > i:
                    # Upper triangle - hide
                    ax.set_visible(False)
                    
                elif i == j:
                    # Diagonal - histogram
                    feat = self.features[i]
                    if show_outliers:
                        ax.hist(df.loc[inliers, feat], bins=30, alpha=0.5, 
                               color='gray', label='Inliers')
                        if outliers.any():
                            ax.hist(df.loc[outliers, feat], bins=30, alpha=0.7, 
                                   color='red', label='Outliers')
                    else:
                        ax.hist(df[feat], bins=30, alpha=0.5, color='gray')
                    
                    ax.set_ylabel('Count')
                    if i == n_features - 1:
                        ax.set_xlabel(feat)
                    
                else:
                    # Lower triangle - scatter + ellipse
                    feat_x = self.features[j]
                    feat_y = self.features[i]
                    
                    # Create marginal detector
                    pair_detector = MahalanobisOutlierDetector(
                        [feat_x, feat_y],
                        confidence=self.confidence,
                        method=self.method
                    )
                    pair_detector.fit(df)
                    
                    # Plot
                    if show_outliers:
                        ax.scatter(df.loc[inliers, feat_x], df.loc[inliers, feat_y], 
                                  s=10, alpha=0.5, c='gray')
                        if outliers.any():
                            ax.scatter(df.loc[outliers, feat_x], df.loc[outliers, feat_y], 
                                      s=20, marker='x', c='red')
                    else:
                        ax.scatter(df[feat_x], df[feat_y], s=10, alpha=0.5, c='gray')
                    
                    pair_detector.plot_ellipse(ax, facecolor='red', alpha=0.1, 
                                              edgecolor='red', linewidth=1.5)
                    
                    if j == 0:
                        ax.set_ylabel(feat_y)
                    if i == n_features - 1:
                        ax.set_xlabel(feat_x)
        
        fig.tight_layout()
        return fig, axs