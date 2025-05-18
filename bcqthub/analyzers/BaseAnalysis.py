from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, Dict, Any
import matplotlib.pyplot as plt


class BaseAnalysis(ABC):
    """
    Generic template for qubit analysis routines.
    Defines a run_all() template method around load→prepare→fit→plot→export.
    """
    def __init__(
        self,
        input_path: Union[str, Path],
        out_dir: Union[str, Path],
        verbose: bool = False,
    ):
        self.input_path = Path(input_path)
        self.out_dir = Path(out_dir)
        self.verbose = verbose
        self.raw = None              # raw data object
        self.processed = None        # after preprocessing
        self.fit_results = None      # after fitting
        self.figs = None             # list of matplotlib Figure(s)

    def run_all(self) -> Dict[str, Any]:
        """
        Execute the full analysis pipeline:
          1. load   → populate self.raw
          2. prepare→ populate self.processed
          3. fit    → populate self.fit_results
          4. plot   → populate self.fig
          5. export → save outputs
        Returns a summary dict with keys raw, processed, fit, fig.
        """
        self.load()
        self.prepare()
        self.fit()
        self.plot()
        self.export()
        return self.result()

    @abstractmethod
    def load(self) -> None:
        """Load data from self.input_path into self.raw."""
        ...

    @abstractmethod
    def prepare(self) -> None:
        """Preprocess self.raw into self.processed."""
        ...

    @abstractmethod
    def fit(self) -> None:
        """Compute fits on self.processed, store in self.fit_results."""
        ...

    @abstractmethod
    def plot(self) -> None:
        """Generate matplotlib Figure for self.processed + fits, store in self.fig."""
        ...

    def export(self) -> None:
        """
        Default export: save figure and fit results to self.out_dir.
        Override in subclasses for custom behavior.
        """
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if self.figs:
            fig_path = self.out_dir / "plot.png"
            self.figs.savefig(fig_path)
        if self.fit_results is not None:
            save_path = self.out_dir / "fit_results.npz"
            # assumes fit_results is a dict of arrays
            np.savez(save_path, **self.fit_results)

    def result(self) -> Dict[str, Any]:
        """Assemble and return the analysis results."""
        return {
            "raw": self.raw,
            "processed": self.processed,
            "fit": self.fit_results,
            "fig": self.figs,
        }


# Example subclass for T1 analysis:
from QubitConfiguration import Importer
from QubitProcessor import QubitProcessor
from Analyses.QubitAnalyzer import QubitAnalyzer

class T1Analysis(BaseAnalysis):
    def load(self) -> None:
        # load raw T1 HDF5 data
        self.raw = Importer.load_t1(self.input_path, verbose=self.verbose)

    def prepare(self) -> None:
        # extract decay curve arrays
        arrs = QubitProcessor.prepare_t1(self.raw)
        self.processed = arrs

    def fit(self) -> None:
        # perform the T1 exponential fit
        popt, pcov = QubitAnalyzer.fit_t1(self.processed)
        self.fit_results = {"popt": popt, "pcov": pcov}

    def plot(self) -> None:
        # generate decay curve plot
        self.fig = QubitAnalyzer.plot_t1(
            self.processed, self.fit_results, verbose=self.verbose
        )
