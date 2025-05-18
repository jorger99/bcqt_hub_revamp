from BaseAnalysis import BaseAnalysis
from QubitConfiguration import Importer
from QubitProcessor import QubitProcessor
from Analyses.QubitAnalyzer import QubitAnalyzer

class T1_Analysis(BaseAnalysis):
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
