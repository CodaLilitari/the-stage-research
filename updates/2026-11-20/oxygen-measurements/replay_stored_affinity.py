"""Reconstruct one external day-42 P50 forecast from the Chen figure and Kassa table."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
from PIL import Image
import pymupdf
from scipy.optimize import least_squares


def verified(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Source hash differs from the published edition used for this analysis")
    return data


def source_means(pdf):
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        embedded = doc.extract_image(709)["image"]
    image = np.asarray(Image.open(BytesIO(embedded)).convert("RGB"), dtype=float)
    if image.shape != (774, 1898, 3):
        raise ValueError("Unexpected dimensions of original Figure 2")
    dark = image.max(axis=2) < 85
    ticks = []
    for y in (685, 558, 431, 304, 177):
        pixels = np.arange(y - 3, y + 4)
        ticks.append(np.average(pixels, weights=dark[pixels, 95:103].sum(axis=1)))
    transform = np.polyfit(ticks, (15, 20, 25, 30, 35), 1)
    r, g, b = image.transpose(2, 0, 1)
    yy, xx = np.where((r > 145) & (r-g > 62) & (r-b > 60))
    estimates = []
    for markers in ([(134,478), (134,521)], [(824,615), (834,650), (813,653)]):
        values = []
        for x0, y0 in markers:
            keep = (abs(xx-x0) <= 7) & (abs(yy-y0) <= 6.9) & (abs(xx-x0) >= 2.8)
            if keep.sum() < 25:
                raise ValueError("Insufficient red points in stated marker window")
            fit = least_squares(lambda q: np.hypot(xx[keep]-q[0], yy[keep]-q[1])-q[2],
                                [x0, y0, 5.4], loss="soft_l1")
            if not fit.success or not 4 < fit.x[2] < 7 or abs(fit.x[1]-y0) >= 1.5:
                raise ValueError("Original red marker cannot be reliably located")
            values.append(float(np.polyval(transform, fit.x[1])))
        estimates.append(float(np.mean(values)))
    return estimates


def table_cells(xml):
    def text(node):
        return " ".join("".join(node.itertext()).split())
    table = next(t for t in ElementTree.fromstring(xml).iter("table-wrap")
                 if text(t.find("label")).upper() == "TABLE 1")
    if [text(x) for x in table.find(".//thead/tr")] != ["Sample", "Day-0 (control)", "Day-42"]:
        raise ValueError("Unexpected Table 1 column headers")
    row = next(row for row in table.findall(".//tbody/tr") if text(row[0]).lower() == "p50 (mmhg)")
    return [float(text(cell).split("±")[0]) for cell in row[1:]]


def replay(pdf_path, xml_path):
    pdf = verified(pdf_path, "37baaec81c6940eb2b5f46ff91fa9812687108ddd0cec2a3d14c70fcb1b21451")
    xml = verified(xml_path, "df6481912e698ecfc98eae37dbd54da646f571343d0063c096d538bc7316eeae")
    early, late = source_means(pdf)
    baseline, observed = table_cells(xml)
    forecast = baseline * late / early
    if not abs(forecast-22.604386) < 1e-5 or observed != 22.1:
        raise ValueError("Source replay differs from the registered forecast or target")
    return dict(source_day3_mmHg=early, source_day42_mmHg=late, external_baseline_mmHg=baseline,
                external_day42_mmHg=observed, forecast_mmHg=forecast,
                forecast_abs_error_mmHg=abs(forecast-observed),
                baseline_abs_error_mmHg=abs(baseline-observed),
                source_endpoint_abs_error_mmHg=abs(late-observed))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chen_pdf", type=Path)
    parser.add_argument("kassa_xml", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.chen_pdf, args.kassa_xml), indent=2))
