"""Read-only EDI adapter for preregistered magnetotelluric training members."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

import numpy as np

from .observation import DatasetAdapter, ObservationSet


_NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?")


def _section(text: str, name: str) -> np.ndarray:
    match = re.search(
        rf"^\s*>{re.escape(name)}(?:\s+[^/\r\n]*)?\s*//\s*\d+\s*$([\s\S]*?)(?=^\s*>)",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"required EDI section missing: {name}")
    return np.asarray([float(value) for value in _NUMBER.findall(match.group(1))])


def _head_value(text: str, name: str) -> str:
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*\"?([^\"\r\n]+)", text, re.MULTILINE)
    if not match:
        raise ValueError(f"required EDI header missing: {name}")
    return match.group(1).strip()


def _dms(value: str) -> float:
    parts = value.split(":")
    if len(parts) != 3:
        return float(value)
    sign = -1.0 if parts[0].startswith("-") else 1.0
    degree = abs(float(parts[0]))
    return sign * (degree + float(parts[1]) / 60 + float(parts[2]) / 3600)


class MTEDIAdapter(DatasetAdapter):
    """Normalize EDI impedance tensors and documented component variances.

    EDI ``Z*.VAR`` values are retained as diagonal real-stack covariance.
    EDI does not encode cross-component covariance; zero off-diagonals are
    therefore an explicit format limitation, not an inferred independence
    claim.
    """

    components = ("Zxx", "Zxy", "Zyx", "Zyy")

    def parse(
        self, raw_member_hashes: Mapping[str, str], raw_snapshots: Mapping[str, bytes]
    ) -> ObservationSet:
        data_parts: list[np.ndarray] = []
        variance_parts: list[np.ndarray] = []
        frequency_parts: list[np.ndarray] = []
        coordinate_parts: list[np.ndarray] = []
        cluster_parts: list[np.ndarray] = []
        lineage = []
        for path in self.raw_paths:
            text = raw_snapshots[str(path)].decode("ascii", errors="strict")
            frequencies = _section(text, "FREQ")
            lat = _dms(_head_value(text, "LAT"))
            lon = _dms(_head_value(text, "LONG"))
            elev = float(_head_value(text, "ELEV"))
            station = _head_value(text, "DATAID")
            for component in self.components:
                real = _section(text, f"{component}R")
                imag = _section(text, f"{component}I")
                variance = _section(text, f"{component}.VAR")
                if not (len(real) == len(imag) == len(variance) == len(frequencies)):
                    raise ValueError(f"inconsistent EDI section lengths: {path.name}/{component}")
                data_parts.append(real + 1j * imag)
                variance_parts.append(variance)
                frequency_parts.append(frequencies)
                coordinate_parts.append(np.tile([lon, lat, elev], (len(frequencies), 1)))
                cluster_parts.append(np.full(len(frequencies), station, dtype=object))
            lineage.append(
                {
                    "operation": "parse_edi_training_member",
                    "path": str(path),
                    "station": station,
                    "variance_contract": "EDI Z*.VAR duplicated onto real/imag diagonal; cross-covariance unavailable",
                }
            )
        data = np.concatenate(data_parts)
        variances = np.concatenate(variance_parts)
        n = len(data)
        covariance = np.zeros((2 * n, 2 * n), dtype=float)
        covariance[np.arange(n), np.arange(n)] = variances
        covariance[n + np.arange(n), n + np.arange(n)] = variances
        return ObservationSet(
            data=data,
            coordinates=np.vstack(coordinate_parts),
            cluster=np.concatenate(cluster_parts),
            units="mV/km/nT",
            crs="EPSG:4326 with elevation metres",
            data_mode="complex",
            covariance=covariance,
            frequencies=np.concatenate(frequency_parts),
            raw_member_hashes=raw_member_hashes,
            lineage=lineage,
            complex_layout="real_then_imag",
            source_receiver_geometry={
                "source": "natural plane wave",
                "components": self.components,
                "sign_convention": "exp(+ i omega t)",
                "covariance_limit": "EDI component variances only",
            },
        )
