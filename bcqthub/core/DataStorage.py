import json
import numpy as np
import h5py
import warnings
from pathlib import Path
from dataclasses import dataclass
from tabulate import tabulate


class IOHelper:
    """
    Mixin providing low‑level I/O helpers for saving JSON, NPZ, and figures.
    Expects a `self.base_path: Path` attribute.
    """
    def save_json(self, obj, fname: str):
        out = self.base_path / fname
        with open(out, "w") as f:
            json.dump(obj, f, default=str, indent=2)

    def save_npz(self, data_dict: dict, fname: str):
        out = self.base_path / fname
        np.savez(out, **data_dict)

    def save_figure(self, fig, fname: str):
        out = self.base_path / fname
        fig.savefig(out)


@dataclass
class Importer(IOHelper):
    """
    Loads raw experiment data (HDF5 + side‑cars) into .data and .metadata,
    provides axis aliasing, metadata loading, and summaries.
    """
    data: dict
    metadata: dict
    base_path: Path

    @classmethod
    def load_hdf5_directory(cls, path, keys=None, verbose=False):
        path = Path(path)
        if path.is_dir():
            run_dir = path
            files = list(run_dir.glob("*.hdf5"))
            if not files:
                raise FileNotFoundError(f"No HDF5 in {run_dir}")
            h5_path = files[0]
        else:
            h5_path = path
            run_dir = h5_path.parent

        data, metadata = {}, {}
        with h5py.File(h5_path, "r") as f:
            for k, v in f.attrs.items():
                metadata[k] = v
            def collect(name, obj):
                if isinstance(obj, h5py.Dataset):
                    key = name.rsplit("/", 1)[-1]
                    if keys is None or key in keys:
                        grp = name.split("/", 1)[0]
                        data[f"{grp}/{key}"] = obj[()]
            f.visititems(collect)
            # dimscales
            dimscales = {}
            if "data/signal" in f:
                for dim in f["data/signal"].dims:
                    for scale in dim.values():
                        sn = scale.name.rsplit("/",1)[-1]
                        dimscales[sn] = scale[()]
            metadata["dimscales"] = dimscales

        raw = cls(data, metadata, run_dir)

        misc_fp = run_dir / "misc.npz"
        if misc_fp.exists():
            raw.load_misc_npz(misc_fp)
        fit_fp = run_dir / "fitting_res.npz"
        if fit_fp.exists():
            raw.load_fit_npz(fit_fp)

        if verbose:
             # use class method to make a cool box
            cls._print_verbose_header(h5_path) 
            print(f"HDF5 File Structure -> ")
            raw.print_summary(include_aliases=False)
            
        return raw
    
    
    @staticmethod
    def _print_verbose_header(filepath: Path):
        """
        Prints a 3‑line boxed header showing:
          • "HDF5 File Loaded!"
          • "Found at (<last_two_path_parts>)"
        with perfectly aligned dashes.
        """
        # 1) Take only the last two path components
        parts = Path(filepath).parts
        short = "/".join(parts[-4:]) 

        # 2) Messages, each wrapped by single spaces
        msg1 = "----#  HDF5 File Loaded!  #----"
        msg2 = f"----#  Found at '{short}'  #----"

        # 3) Compute the width of the inner box
        max_len = max(len(msg1), len(msg2))

        # 4) Helper to build one line
        def make_line(msg: str) -> str:
            total_dashes = max_len - len(msg)
            left  = total_dashes // 2
            right = total_dashes - left
            return "#" + "-"*left + msg + "-"*right + "#"

        # 5) Print top, middle, and bottom
        print(make_line(msg1))
        print(make_line(msg2))
        print("#" + "-"*max_len + "#\n")


    def load_misc_npz(self, npz_path):
        arr = np.load(npz_path, allow_pickle=True)
        misc = {}
        for k, v in arr.items():
            misc[k] = v.item() if v.shape == () else v
        self.metadata["misc"] = misc
        

    def load_fit_npz(self, npz_path):
        arr = np.load(npz_path, allow_pickle=True)
        self.metadata["fit"] = {
            "p0":   arr["p0"],
            "popt": arr["popt"],
            "perr": arr["perr"],
            "func": arr["func"].item().strip()
        }
        

    def standardize_variables(self, overrides=None, verbose=False):
        """
        Alias existing data keys into:
          - 'idx' for the run index
          - 'y'   for the measured signal
          - 'x1','x2',... for sweep axes

        Leaves all original keys untouched, and records the mapping
        in self.metadata['alias_mapping'].
        """
        rules = {"idx": ["index","idx"], "y": ["signal","counts"]}
        suffixes = ["time","delay","frequency","freq","amplitude","power"]
        if overrides:
            for std, key in overrides.items():
                rules[std] = [key]

        def pick(cands):
            for c in cands:
                if c in self.data:
                    return c
            for k in self.data:
                for s in cands:
                    if k.endswith(s):
                        return k
            return None

        mapping = {}
        for std in ("idx","y"):
            orig = pick(rules[std])
            if orig:
                mapping[std] = orig

        used = set(mapping.values())
        sweeps = [k for k in self.data
                  if k not in used and any(k.endswith(s) for s in suffixes)]
        for i, orig in enumerate(sorted(sweeps), start=1):
            mapping[f"x{i}"] = orig

        for alias, orig in mapping.items():
            if alias not in self.data:
                self.data[alias] = self.data[orig]

        self.metadata['alias_mapping'] = mapping

        if verbose:
            print("Standardized alias mapping:")
            for alias, orig in mapping.items():
                print(f"  {alias} → {orig}")
            print()
            self.print_summary(include_aliases=True)


    def print_summary(self, include_metadata=False, include_aliases=False):
        """
        Print table of original data arrays and dim‑scales,
        optionally listing their aliases.
        """
        src = self.base_path.name
        alias_map = self.metadata.get("alias_mapping", {})
        rev = {}
        for alias, orig in alias_map.items():
            rev.setdefault(orig, []).append(alias)

        headers = ["Name", "Shape", "Dtype/Value", "Category", "Source"]
        if include_aliases:
            headers.insert(1, "Aliases")

        originals = [k for k in self.data if k not in alias_map]

        rows = []
        for name in originals:
            arr = self.data[name]
            dt = arr.dtype.name if hasattr(arr, "dtype") else type(arr).__name__
            alias_list = rev.get(name, [])
            row = [name, arr.shape, dt, "data"]
            if include_aliases:
                row.insert(1, ", ".join(alias_list))
            row.append(src)
            rows.append(row)

        for name, arr in self.metadata.get("dimscales", {}).items():
            dt = arr.dtype.name
            alias_list = rev.get(name, [])
            row = [f"dimscale/{name}", arr.shape, dt, "scale"]
            if include_aliases:
                row.insert(1, ", ".join(alias_list))
            row.append(src)
            rows.append(row)

        if include_metadata:
            for cat in ("misc", "fit"):
                for k, v in self.metadata.get(cat, {}).items():
                    alias_list = rev.get(k, [])
                    row = [f"{cat}/{k}", "", repr(v), "meta"]
                    if include_aliases:
                        row.insert(1, ", ".join(alias_list))
                    row.append(src)
                    rows.append(row)

        table_str = tabulate(rows, headers=headers, tablefmt="github")
        border = "-" * len(table_str.split("\n",1)[0])
        print(border)
        print(table_str)
        print(border)
        print()


class Exporter(IOHelper):
    """
    Uses IOHelper to write out raw data, metadata, processed results, and figures.
    """
    def __init__(self, out_dir):
        self.base_path = Path(out_dir)
        self.base_path.mkdir(exist_ok=True, parents=True)

    def export_all(self, raw: Importer, processed: dict, fig, prefix: str):
        self.save_npz(raw.data,        f"{prefix}_raw.npz")
        self.save_json(raw.metadata,   f"{prefix}_meta.json")
        self.save_json(processed,      f"{prefix}_proc.json")
        self.save_figure(fig,          f"{prefix}.png")




def select_xy(data_dict, x_key=None, y_key=None):
    """
    Choose sweep (x) and signal (y) keys from a data dict.
    """
    sweeps = sorted(k for k in data_dict if k.startswith("x"))
    if x_key is None:
        if not sweeps:
            raise KeyError(f"No sweep axes in {list(data_dict)}")
        x_key = sweeps[0]
    elif x_key not in data_dict:
        raise KeyError(f"x_key={x_key!r} not in {sweeps}")

    if y_key is None:
        if "y" not in data_dict:
            raise KeyError(f"No default 'y' in {list(data_dict)}")
        y_key = "y"
    elif y_key not in data_dict:
        raise KeyError(f"y_key={y_key!r} not in {list(data_dict)}")

    return x_key, y_key

