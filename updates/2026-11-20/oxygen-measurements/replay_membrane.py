"""Recalculate Menzel et al.'s mean transfer rates from the original S1 PDF."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from statistics import mean

import pymupdf


def replay(path):
    expected = "fb8e6b7853357afc7544e9a6fef474be7f387dbe13dd687b66d02af58bc78c94"
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Table PDF hash mismatch")
    with pymupdf.open(path) as document:
        s1 = document[0].get_text()
        s2 = document[1].get_text()
    result = []
    for flow in (0.4, 0.8, 1.2, 1.6):
        section = s1.split(f"\n{flow} ", 1)[1]
        # Inlet and outlet rows each contain six printed mean and SD pairs.
        cells = re.findall(r"(?m)^([±]?\d+\.\d{2})\s*?$", section)[:24]
        if len(cells) != 24:
            raise ValueError("Unexpected S1 layout")
        inlet = [float(x) for x in cells[0:12:2]]
        outlet = [float(x) for x in cells[12:24:2]]
        factor = (flow / 60) * 0.028 / 760 * 1_000_000
        rates = [(outgoing - incoming) * factor for incoming, outgoing in zip(inlet, outlet)]
        section2 = s2.split(f"\n{flow} ", 1)[1]
        printed = re.findall(r"(?m)^(\d+\.\d)±\d+\.\d\*?\s*?$", section2)[:3]
        if len(printed) != 3:
            raise ValueError("Unexpected S2 layout")
        result.append({
            "flow_mL_min": flow,
            "S1_blank_mean_nL_s": mean(rates[:3]),
            "S1_cell_lined_mean_nL_s": mean(rates[3:]),
            "S1_paired_gain_mean_nL_s": mean(rates[j + 3] - rates[j] for j in range(3)),
            "S2_printed_blank_lined_gain_nL_s": [float(x) for x in printed],
        })
    last = result[-1]
    for name, target in [("S1_blank_mean_nL_s", 46.614), ("S1_cell_lined_mean_nL_s", 78.603),
                         ("S1_paired_gain_mean_nL_s", 31.989)]:
        if abs(last[name] - target) > 0.00051:
            raise ValueError("Different S1 aggregate")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tables", type=Path)
    print(json.dumps(replay(parser.parse_args().tables), indent=2))
