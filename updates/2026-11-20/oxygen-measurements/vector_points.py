"""Read Valsecchi et al.'s green measured marker paths in supplementary S6/S7."""
import struct

import numpy as np


CONDITIONS = (10, 20, 50, 70, 90)
COUNTS = (65, 77, 61, 64, 79)
DONORS = (("BO", "BP", "LV"), ("MG", "TL", "ZF"))


def records(blob):
    offset = 0
    while offset < len(blob):
        kind, size = struct.unpack_from("<II", blob, offset)
        if not 8 <= size <= len(blob) - offset:
            raise ValueError("Malformed EMF record")
        block = blob[offset:offset + size]
        offset += size
        if kind != 70 or block[12:16] != b"EMF+":
            continue
        cursor = 16
        while cursor + 12 <= size:
            kind, flags, total, count = struct.unpack_from("<HHII", block, cursor)
            if total < 12 or count > total - 12 or cursor + total > size:
                raise ValueError("Malformed EMF+ record")
            yield kind, flags, block[cursor + 12:cursor + 12 + count]
            cursor += total


def painted_paths(blob):
    paths = {}
    transform = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for kind, flags, data in records(blob):
        if kind == 0x402A:
            transform = struct.unpack_from("<6f", data)
        elif kind == 0x402B:
            transform = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        elif kind == 0x4008 and flags >> 8 == 3:
            paths[flags & 255] = data
        elif kind in (0x4014, 0x4015):
            path = paths[flags & 255]
            _, count, flags_path = struct.unpack_from("<III", path)
            if flags_path or transform[:4] != (1.0, 0.0, 0.0, 1.0):
                raise ValueError("Unexpected source vector transform or point encoding")
            points = np.frombuffer(path, dtype="<f4", count=2 * count, offset=12).reshape(count, 2)
            yield kind, data, points + transform[-2:], transform[-2:]


def calibration(ticks, labels):
    coefficients = np.polyfit(ticks, labels, 1)
    if np.max(np.abs(np.polyval(coefficients, ticks) - labels)) >= 0.001:
        raise ValueError("Axis calibration residual exceeds its limit")
    return coefficients


def observed_symbols(blob, donor_panels):
    horizontal, vertical, points = [], [], []
    legend = 0
    for kind, color, path, shift in painted_paths(blob):
        if kind == 0x4015 and len(path) == 2:
            (x, y), (x2, y2) = path
            if x == x2 and 2 < y2 - y < 10:
                horizontal.append(x)
            if y == y2 and 2 < x - x2 < 10:
                vertical.append(y)
        elif kind == 0x4014 and color == bytes.fromhex("006400ff"):
            if shift in ((32.0, 452.0), (291.0, 352.0)):
                legend += 1
                continue
            size = [6, 6.268] if donor_panels else [10, 10.447]
            if len(path) != 19 or not np.allclose(np.ptp(path, axis=0), size, atol=0.002):
                raise ValueError("Unexpected green marker geometry")
            points.append(((path.min(axis=0) + path.max(axis=0)) / 2, shift))
    if legend != 1:
        raise ValueError("Source legend could not be separated from observations")
    if donor_panels:
        if (len(horizontal), len(vertical)) != (21, 16):
            raise ValueError("Unexpected number of donor-panel axis ticks")
        xmaps = [calibration(t, np.arange(0, 721, 120)) for t in np.split(np.sort(horizontal), 3)]
        ymaps = [calibration(t[::-1], np.arange(0, 106, 15)) for t in np.split(np.sort(vertical), 2)]
    else:
        if (len(horizontal), len(vertical)) != (19, 12):
            raise ValueError("Unexpected number of combined-panel axis ticks")
        xmaps = [calibration(np.sort(horizontal), np.arange(0, 721, 40))]
        ymaps = [calibration(np.sort(vertical)[::-1], np.arange(0, 111, 10))]
    observations = []
    for (x, y), (dx, dy) in points:
        left = (69.0, 255.0, 441.0).index(dx) if donor_panels else 0
        top = (52.0, 230.0).index(dy) if donor_panels else 0
        donor = DONORS[top][left] if donor_panels else None
        observations.append((donor, float(np.polyval(xmaps[left], x)), float(np.polyval(ymaps[top], y))))
    return observations
