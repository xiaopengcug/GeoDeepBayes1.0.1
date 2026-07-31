import csv
import io
import zipfile

import pytest

from geodeepbayes.data.tdip_reykjanes import GATE_COLUMNS, TIME_COLUMNS, paired_discrepancies, read_training_dates


def _csv(a, b, m, n, offset=0.0):
    fields = ["Rho (Ohm.m)", "M (mV/V)", "VMN (mV)", "IAB (mA)", "A", "B", "M", "N", *GATE_COLUMNS, "Mdly (ms)", *TIME_COLUMNS]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    row = {"Rho (Ohm.m)": 10 + offset, "M (mV/V)": 2 + offset, "VMN (mV)": 1, "IAB (mA)": 100, "A": a, "B": b, "M": m, "N": n, "Mdly (ms)": 40}
    row.update({name: i + offset for i, name in enumerate(GATE_COLUMNS, 1)})
    row.update({name: 20 for name in TIME_COLUMNS})
    writer.writerow(row)
    return stream.getvalue()


def test_adapter_reads_only_requested_pair_and_matches_reciprocal(tmp_path):
    archive = tmp_path / "tdip.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("x/N_20230101.csv", _csv(1, 2, 3, 4))
        out.writestr("x/R_20230101.csv", _csv(3, 4, 1, 2, 1))
        out.writestr("x/N_20230102.csv", "sealed-test-marker")
    members = {"20230101": {"N": {"path": "x/N_20230101.csv"}, "R": {"path": "x/R_20230101.csv"}}}
    days = read_training_dates(archive, dates=["20230101"], members=members)
    differences = paired_discrepancies(days[0])
    assert differences["M (mV/V)"].tolist() == [-1.0]
    assert len([name for name in differences if name.startswith("M")]) == 21


def test_adapter_rejects_unpaired_date(tmp_path):
    archive = tmp_path / "tdip.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("x/N_20230101.csv", _csv(1, 2, 3, 4))
    with pytest.raises(ValueError, match="pair required"):
        read_training_dates(archive, dates=["20230101"], members={"20230101": {"N": {"path": "x/N_20230101.csv"}}})
