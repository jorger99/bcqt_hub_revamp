import numpy as np
from scipy.optimize import curve_fit
from DataStorage import select_xy
from FitFunctions import exponential_decay


class BaseHandler:
    """
    Handles raw→numeric preprocessing and fitting logic.
    """

    def prepare_1d(
        self,
        raw_data,
        x_key=None,
        y_key=None,
        use_index=False
    ):
        """
        Standardize, pick axes, abs→float→mean collapse → 1D arrays.

        Returns dict: {'x','y','xlabel','ylabel'}.
        """
        raw_data.standardize_variables()
        if use_index:
            yk = y_key or "y"
            if yk not in raw_data.data:
                raise KeyError(f"y_key={yk!r} not found")
            x = np.arange(raw_data.data[yk].shape[0], dtype=float)
            xlabel = "Index"
        else:
            xk, yk = select_xy(raw_data.data, x_key=x_key, y_key=y_key)
            x = np.asarray(raw_data.data[xk], dtype=float)
            xlabel = xk

        y_raw  = raw_data.data[yk]
        y_mag  = np.asarray(np.abs(y_raw), dtype=float)
        y      = np.mean(y_mag, axis=0)
        ylabel = yk

        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError(f"x/y length mismatch: {x.shape} vs {y.shape}")

        return {"x": x, "y": y, "xlabel": xlabel, "ylabel": ylabel}
    

    def prepare_2d(self, raw_data):
        """
        Take your raw data object, pick out the first two sweep axes
        (whatever they’re actually named, e.g. 'amps','freqs','time',…),
        and build a 2D data array.

        Returns a dict with:
        - the two real sweep‑axis names → their 1D numpy arrays
        - 'data2d' → the 2D numpy array (shape: len(axis1)×len(axis2))
        """
        # Make sure variables are standardized, so your raw_data has keys like 'x…'
        raw_data.standardize_variables()

        # Find the two sweep axes by name
        sweeps = sorted(k for k in raw_data.data if k.startswith("x"))
        if len(sweeps) < 2:
            raise KeyError(f"Need ≥2 sweep axes; found {sweeps}")

        name1, name2 = sweeps[:2]
        arr1 = np.asarray(raw_data.data[name1], dtype=float)
        arr2 = np.asarray(raw_data.data[name2], dtype=float)

        y_raw = raw_data.data["y"]
        mag = np.abs(y_raw).astype(float)
        data2d = np.mean(mag, axis=0)
        if data2d.shape != (arr1.size, arr2.size):
            raise ValueError(
                f"Shape mismatch: data2d {data2d.shape} vs "
                f"({arr1.size},{arr2.size})"
            )

        return {
            name1:   arr1,
            name2:   arr2,
            "data2d": data2d,
        }
