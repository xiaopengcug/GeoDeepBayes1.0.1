"""Read-only adapter for paired Reykjanes TDIP acquisition dates."""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

GATE_COLUMNS = tuple(f"M{i} (mV/V)" for i in range(1, 21))
TIME_COLUMNS = tuple(f"TM{i} (ms)" for i in range(1, 21))
CORE_COLUMNS = ("Rho (Ohm.m)", "M (mV/V)", "VMN (mV)", "IAB (mA)", "A", "B", "M", "N")


@dataclass(frozen=True)
class TDIPDate:
    date: str
    normal: tuple[dict[str, float], ...]
    reciprocal: tuple[dict[str, float], ...]


def _read_member(archive: zipfile.ZipFile, name: str) -> tuple[dict[str, float], ...]:
    with archive.open(name, "r") as raw:
        stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="strict", newline="")
        reader = csv.DictReader(stream)
        fields = tuple(reader.fieldnames or ())
        required = set(CORE_COLUMNS + GATE_COLUMNS + ("Mdly (ms)",) + TIME_COLUMNS)
        missing = sorted(required - set(fields))
        if missing:
            raise ValueError(f"{name}: missing TDIP fields {missing}")
        rows = []
        for source in reader:
            row = {column: float(source[column]) for column in required}
            if not all(np.isfinite(value) for value in row.values()):
                raise ValueError(f"{name}: non-finite observation")
            rows.append(row)
    if not rows:
        raise ValueError(f"{name}: no observations")
    return tuple(rows)


def read_training_dates(
    archive_path: str | Path,
    *,
    dates: list[str] | tuple[str, ...],
    members: dict[str, dict[str, dict[str, object]]],
) -> tuple[TDIPDate, ...]:
    """Read exactly the caller-supplied dates; partition policy stays external."""
    result = []
    with zipfile.ZipFile(archive_path) as archive:
        for date in dates:
            registered = members.get(date, {})
            if set(registered) != {"N", "R"}:
                raise ValueError(f"{date}: normal/reciprocal pair required")
            result.append(
                TDIPDate(
                    date=date,
                    normal=_read_member(archive, str(registered["N"]["path"])),
                    reciprocal=_read_member(archive, str(registered["R"]["path"])),
                )
            )
    return tuple(result)


def reciprocal_key(row: dict[str, float]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Canonical ABMN quadrupole key; N/R are repeat measurements, not clusters."""
    current = tuple(sorted((int(row["A"]), int(row["B"]))))
    potential = tuple(sorted((int(row["M"]), int(row["N"]))))
    return tuple(sorted((current, potential)))  # type: ignore[return-value]


def paired_discrepancies(day: TDIPDate) -> dict[str, np.ndarray]:
    normal = {reciprocal_key(row): row for row in day.normal}
    reciprocal = {reciprocal_key(row): row for row in day.reciprocal}
    keys = sorted(set(normal) & set(reciprocal))
    if not keys:
        raise ValueError(f"{day.date}: no reciprocal ABMN matches")
    columns = ("Rho (Ohm.m)", "M (mV/V)") + GATE_COLUMNS
    return {
        column: np.asarray([normal[key][column] - reciprocal[key][column] for key in keys])
        for column in columns
    }
