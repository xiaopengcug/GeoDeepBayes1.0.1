"""Read-only EMTF XML adapter with full within-period complex covariance."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping

import numpy as np

from .observation import DatasetAdapter, ObservationSet


_COMPONENTS = (
    ("Zxx", "Ex", "Hx"),
    ("Zxy", "Ex", "Hy"),
    ("Zyx", "Ey", "Hx"),
    ("Zyy", "Ey", "Hy"),
)
_OUTPUT_INDEX = {"Ex": 0, "Ey": 1}
_INPUT_INDEX = {"Hx": 0, "Hy": 1}


def _complex_value(element: ET.Element) -> complex:
    values = [float(value) for value in (element.text or "").split()]
    if len(values) != 2:
        raise ValueError("EMTF complex value must contain real and imaginary parts")
    return complex(values[0], values[1])


def _matrix(period: ET.Element, tag: str, axes: tuple[str, str]) -> np.ndarray:
    element = period.find(tag)
    if element is None:
        raise ValueError(f"required EMTF XML estimate missing: {tag}")
    index = {name: position for position, name in enumerate(axes)}
    matrix = np.full((2, 2), np.nan + 1j * np.nan, dtype=complex)
    for value in element.findall("value"):
        output = value.attrib.get("output")
        input_ = value.attrib.get("input")
        if output not in index or input_ not in index:
            raise ValueError(f"unexpected {tag} axes: {output}/{input_}")
        matrix[index[output], index[input_]] = _complex_value(value)
    if np.any(~np.isfinite(matrix)):
        raise ValueError(f"incomplete EMTF XML estimate: {tag}")
    return matrix


def _real_covariance(complex_covariance: np.ndarray) -> np.ndarray:
    """Map a proper complex covariance to the declared real-then-imag stack."""
    real = 0.5 * complex_covariance.real
    imaginary = 0.5 * complex_covariance.imag
    covariance = np.block([[real, -imaginary], [imaginary, real]])
    return 0.5 * (covariance + covariance.T)


class MTXMLAdapter(DatasetAdapter):
    """Normalize one or more EMTF XML members without discarding covariance.

    For each period, EMTF provides residual output covariance ``N`` and
    inverse-signal input covariance ``S``.  The transfer-function covariance is
    reconstructed as ``Cov(Z_ij, Z_kl) = N_ik S_jl``.  Period blocks remain
    independent because the public product does not encode cross-period terms.
    """

    components = tuple(component[0] for component in _COMPONENTS)

    def parse(
        self, raw_member_hashes: Mapping[str, str], raw_snapshots: Mapping[str, bytes]
    ) -> ObservationSet:
        data_parts = []
        covariance_parts = []
        frequency_parts = []
        coordinate_parts = []
        cluster_parts = []
        lineage = []
        for path in self.raw_paths:
            root = ET.fromstring(raw_snapshots[str(path)])
            station = root.findtext(".//Site/Id")
            latitude = root.findtext(".//Site/Location/Latitude")
            longitude = root.findtext(".//Site/Location/Longitude")
            elevation = root.findtext(".//Site/Location/Elevation")
            if None in {station, latitude, longitude, elevation}:
                raise ValueError(f"incomplete EMTF site metadata: {path.name}")
            station_data = []
            station_covariance = []
            station_frequency = []
            for period in root.iter("Period"):
                seconds = float(period.attrib["value"])
                if not np.isfinite(seconds) or seconds <= 0:
                    raise ValueError(f"invalid EMTF period: {path.name}")
                z_element = period.find("Z")
                if z_element is None:
                    raise ValueError(f"required EMTF impedance missing: {path.name}")
                by_name = {
                    value.attrib.get("name", "").lower(): _complex_value(value)
                    for value in z_element.findall("value")
                }
                try:
                    impedance = np.asarray(
                        [by_name[name.lower()] for name in self.components], dtype=complex
                    )
                except KeyError as exc:
                    raise ValueError(f"incomplete EMTF impedance tensor: {path.name}") from exc
                inverse_signal = _matrix(period, "Z.INVSIGCOV", ("Hx", "Hy"))
                residual = _matrix(period, "Z.RESIDCOV", ("Ex", "Ey"))
                complex_covariance = np.empty((4, 4), dtype=complex)
                for left, (_, out_left, in_left) in enumerate(_COMPONENTS):
                    for right, (_, out_right, in_right) in enumerate(_COMPONENTS):
                        complex_covariance[left, right] = (
                            residual[_OUTPUT_INDEX[out_left], _OUTPUT_INDEX[out_right]]
                            * inverse_signal[_INPUT_INDEX[in_left], _INPUT_INDEX[in_right]]
                        )
                if not np.allclose(complex_covariance, complex_covariance.T.conj(), rtol=1e-5):
                    raise ValueError(f"non-Hermitian EMTF covariance: {path.name}")
                complex_covariance = 0.5 * (
                    complex_covariance + complex_covariance.T.conj()
                )
                station_data.append(impedance)
                station_covariance.append(_real_covariance(complex_covariance))
                station_frequency.extend([1.0 / seconds] * 4)
            if not station_data:
                raise ValueError(f"EMTF member has no periods: {path.name}")
            values = np.concatenate(station_data)
            blocks = station_covariance
            covariance = np.zeros((2 * len(values), 2 * len(values)), dtype=float)
            for index, block in enumerate(blocks):
                # Each block is ordered Re(Z4), Im(Z4); place into the
                # station-wide Re(all), Im(all) declaration.
                data_slice = slice(4 * index, 4 * (index + 1))
                imag_slice = slice(len(values) + 4 * index, len(values) + 4 * (index + 1))
                covariance[data_slice, data_slice] = block[:4, :4]
                covariance[data_slice, imag_slice] = block[:4, 4:]
                covariance[imag_slice, data_slice] = block[4:, :4]
                covariance[imag_slice, imag_slice] = block[4:, 4:]
            data_parts.append(values)
            covariance_parts.append(covariance)
            frequency_parts.append(np.asarray(station_frequency))
            coordinate_parts.append(
                np.tile(
                    [float(longitude), float(latitude), float(elevation)],
                    (len(values), 1),
                )
            )
            cluster_parts.append(np.full(len(values), station, dtype=object))
            lineage.append(
                {
                    "operation": "parse_emtf_xml_training_member",
                    "path": str(path),
                    "station": station,
                    "covariance_contract": (
                        "within-period full complex covariance from residual and "
                        "inverse-signal matrices; cross-period covariance unavailable"
                    ),
                }
            )
        total = sum(len(values) for values in data_parts)
        covariance = np.zeros((2 * total, 2 * total), dtype=float)
        offset = 0
        for values, block in zip(data_parts, covariance_parts):
            count = len(values)
            source_real = slice(0, count)
            source_imag = slice(count, 2 * count)
            target_real = slice(offset, offset + count)
            target_imag = slice(total + offset, total + offset + count)
            covariance[target_real, target_real] = block[source_real, source_real]
            covariance[target_real, target_imag] = block[source_real, source_imag]
            covariance[target_imag, target_real] = block[source_imag, source_real]
            covariance[target_imag, target_imag] = block[source_imag, source_imag]
            offset += count
        return ObservationSet(
            data=np.concatenate(data_parts),
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
                "covariance": "EMTF XML residual covariance x inverse signal covariance",
                "covariance_limit": "no cross-period or cross-station terms",
            },
        )
