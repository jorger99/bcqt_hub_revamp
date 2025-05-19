import numpy as np
import matplotlib.pyplot as plt
from DataStorage import Importer, Exporter, select_xy
from FitFunctions import exponential_decay, denser
from QubitProcessor import QubitProcessor


class QubitAnalyzer:
    """
        Contains all "process" methods, whose associated "measure" methods are in QubitMeasurer
    """
    def __init__(self, importer: Importer, out_dir: str = None):
        self.raw       = importer
        self.processor = QubitProcessor()
        self.fit       = {}
        self.fig       = None
        self.exporter  = Exporter(out_dir) if out_dir else None

    def process_t1_measurement(
        self,
        x_key: str = None,
        y_key: str = None,
        num_dense: int = 5000,
        plot_err: bool = False,
        use_index: bool = False,
        print_summary: bool = True,
    ):
        # Prepare data
        arrs = self.processor.prepare_1d(
            self.raw,
            x_key=x_key,
            y_key=y_key,
            use_index=use_index
        )
        x, y = arrs["x"], arrs["y"]

        # Fit
        p0 = [y.max() - y.min(), np.median(x), y.min()]
        res = self.processor.process_t1(arrs, fit_fn=exponential_decay, p0=p0)
        popt, pcov = res["popt"], res["pcov"]
        perr = np.sqrt(np.diag(pcov))
        A, T1, C = popt
        A_err, T1_err, C_err = perr

        self.fit = {
            "A":     float(A),      "A_err":  float(A_err),
            "T1":    float(T1),     "T1_err": float(T1_err),
            "C":     float(C),      "C_err":  float(C_err),
            "cov":   pcov
        }

        # Plot
        fig, ax = plt.subplots()
        ax.plot(x, y, "o", label="data")
        x_dense = denser(x, num_points=num_dense)
        ax.plot(
            x_dense,
            exponential_decay(x_dense, *popt),
            "--",
            label=f"$T_1$={T1:.2f}±{T1_err:.2f} μs"
        )
        if plot_err:
            ax.errorbar(x, y, yerr=T1_err, fmt=".", label="errorbars")
        ax.set_xlabel(arrs["xlabel"])
        ax.set_ylabel(arrs["ylabel"])
        ax.set_title(f"T1 Relaxation (Qubit {self.raw.base_path.name})")
        ax.legend()

        self.fig = fig

        # Export
        if self.exporter:
            self.exporter.export_all(self.raw, self.fit, self.fig, prefix="t1")

        return self.fit, self.fig
    
    def process_punchout(
        self,
        cmap: str       = "viridis",
        export_name: str= "punchout.png",
        verbose: bool   = False,
    ):
        # 1) get the arrays + data
        arrs = self.processor.prepare_2d(self.raw)

        # 2) pull out the real names
        axes_names = [k for k in arrs if k != "data2d"]
        name1, name2 = axes_names[:2]
        x1, x2      = arrs[name1], arrs[name2]
        data2d      = arrs["data2d"]

        # 3) plotting
        fig, ax = plt.subplots()
        pcm = ax.pcolormesh(
            x1, x2, data2d.T,
            shading="auto",
            cmap=cmap
        )
        ax.set_xlabel(name1)
        ax.set_ylabel(name2)
        plt.colorbar(pcm, ax=ax)

        # 4) package into one dict
        self.processed = {
            "sweep_axes": {
                name1: x1,
                name2: x2,
            },
            "data2d": data2d,
        }

        # 5) optional export
        if self.exporter:
            self.exporter.export_all(
                self.raw,
                self.processed,
                fig,
                prefix="punchout"
            )

        # 6) return everything
        return self.processed, fig
