#!/usr/bin/env python
"""Independent, fail-closed validator for WP8 evidence phases."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import subprocess
import os
import queue
import threading
import json
import os
import platform
import sys
import time
import tracemalloc
import importlib.util
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import numpy as np
from scipy import stats

from geodeepbayes.validation.wp8_method_synthetic import (
    ADVERSARIAL_SCENARIOS,
    CONVERGENCE_IDS,
    REFERENCE_IDS,
    REQUIRED_METHOD_CHECKS,
    run_method_synthetic_validation,
)

from geodeepbayes.validation.feasibility import (
    METHOD_NAMES, REQUIRED_GATES, bind_gate_evidence, evaluate_feasibility,
)
from geodeepbayes.validation.field_scaffold import validate_field_preregistration
from geodeepbayes.validation.sbc import normal_conjugate_reference_sbc

ROOT = Path(__file__).resolve().parents[2]
WP8 = Path(__file__).resolve().parent
OPEN_DATA = ROOT / "_bmad-output/planning-artifacts/research/open-data"
MANIFEST = OPEN_DATA / "00_catalog/open_geophysics_data_manifest.json"
EVIDENCE = WP8 / "evidence/feasibility-v1"
FIELD_CONTRACT_AUDIT = EVIDENCE / "field-contract-audit.json"
SYNTHETIC_SUPPLEMENTS = WP8 / "synthetic/supplements-v1"
SYNTHETIC_MANIFEST = SYNTHETIC_SUPPLEMENTS / "manifest.json"
METHOD_SYNTHETIC_EVIDENCE = EVIDENCE / "wp8-1-method-synthetic-validation-v1.json"

# Clean-checkout inputs that are authoritative repository assets rather than
# outputs of a WP8 generator.  Keep paths repo-root-relative so persistence and
# validation consumers share one canonical inventory.
_REQUIRED_REPOSITORY_ASSETS = {
    "datasets": "validation/wp8/datasets.json",
    "field_preregistration_payload": (
        "validation/wp8/field/preregistration-scaffold-v1.json"
    ),
    "field_preregistration_schema": (
        "validation/wp8/contracts/field-preregistration-scaffold.schema.json"
    ),
    "preregistration": "validation/wp8/preregistration/wp8-0-v1.json",
    "registration_schema": "validation/wp8/contracts/wp8-feasibility.schema.json",
    "synthetic_policy": "validation/wp8/synthetic/method-validation-policy-v1.json",
    "synthetic_readiness": "validation/wp8/synthetic/readiness.json",
    "wp8_1_start": "validation/wp8/evidence/wp8-1-start.json",
}


def required_repository_assets() -> tuple[str, ...]:
    """Return canonical non-generated WP8 assets required by a clean checkout."""
    return tuple(sorted(_REQUIRED_REPOSITORY_ASSETS.values()))


def _required_repository_asset(name: str) -> Path:
    return ROOT / _REQUIRED_REPOSITORY_ASSETS[name]


DATASETS = _required_repository_asset("datasets")
PREREG = _required_repository_asset("preregistration")
REGISTRATION_SCHEMA = _required_repository_asset("registration_schema")
WP8_1_START = _required_repository_asset("wp8_1_start")
SYNTHETIC_READINESS = _required_repository_asset("synthetic_readiness")
METHOD_VALIDATION_POLICY = _required_repository_asset("synthetic_policy")
FIELD_PREREGISTRATION_SCAFFOLD = _required_repository_asset(
    "field_preregistration_payload"
)
FIELD_PREREGISTRATION_SCHEMA = _required_repository_asset(
    "field_preregistration_schema"
)
EXPECTED_FIELD_PREREGISTRATION_SCHEMA_SHA256 = (
    "b91b25e676a50a526b48ed6792626e963df9aadbec81bd9753347b4a39d9b75f"
)
EXPECTED_FIELD_PREREGISTRATION_PAYLOAD_SHA256 = (
    "1e338b547e24116ac8b44bb64e2edb03545fd46d392dcbd196fec84a61d7f227"
)
EXPECTED_METHOD_VALIDATION_POLICY_SHA256 = (
    "346603951998a4038781905a155a35f3822993bc036bcf7ae1b859b01ca179b5"
)
SYNTHETIC_EXPECTED_SEEDS = {"sip_fdip": 8101, "csamt": 8102, "wfem": 8103}
METHOD_SBC_SEEDS = {
    method: [18095 + index, 28095 + index]
    for index, method in enumerate(
        ("gravity", "magnetic", "dc", "tdip", "tem", "mt_amt", "sip_fdip", "csamt", "wfem")
    )
}
SYNTHETIC_MAX_FILE_BYTES = 10 * 1024 * 1024
SYNTHETIC_MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
SYNTHETIC_MAX_COMPRESSION_RATIO = 100.0
MT_RAW = WP8 / "data/usarray-ta-emtf-v1"
MT_FREEZE = EVIDENCE / "mt-usarray-raw-freeze.json"
MT_DIAGNOSTICS = EVIDENCE / "mt-usarray-train-diagnostics.json"
MT_XML_MANIFEST = MT_RAW / "xml-raw-manifest.json"
MT_XML_COVARIANCE = EVIDENCE / "mt-xml-covariance-readiness.json"
EAST_RIVER_RAW = WP8 / "data/east-river-aem-v1"
EAST_RIVER_MANIFEST = EAST_RIVER_RAW / "raw-manifest.json"
EAST_RIVER_SPLIT = EVIDENCE / "east-river-aem-design-split.json"
EAST_RIVER_CONTRACT = EVIDENCE / "east-river-aem-contract-readiness.json"
EAST_RIVER_DIAGNOSTICS = EVIDENCE / "east-river-aem-train-diagnostics.json"
TEM_CONSORTIUM_RAW = WP8 / "data/tem-aem-consortium-v1"
TEM_CONSORTIUM_MANIFEST = TEM_CONSORTIUM_RAW / "raw-manifest.json"
TEM_CONSORTIUM_SPLIT = EVIDENCE / "tem-aem-consortium-design-split.json"
TEM_CONSORTIUM_CONTRACT = EVIDENCE / "tem-aem-consortium-contract-readiness.json"
TEM_CONSORTIUM_DIAGNOSTICS = EVIDENCE / "tem-aem-consortium-train-diagnostics.json"
MARICOPA_RAW = WP8 / "data/maricopa-aem-v1"
MARICOPA_MANIFEST = MARICOPA_RAW / "raw-manifest.json"
MARICOPA_SPLIT = EVIDENCE / "maricopa-aem-design-split.json"
MARICOPA_CONTRACT = EVIDENCE / "maricopa-aem-contract-readiness.json"
MARICOPA_DIAGNOSTICS = EVIDENCE / "maricopa-aem-train-diagnostics.json"
GA_AEM_CATALOG_RAW = WP8 / "data/geoscience-australia-aem-catalog-v1"
GA_AEM_CATALOG_MANIFEST = GA_AEM_CATALOG_RAW / "raw-manifest.json"
GA_AEM_DESIGN = EVIDENCE / "geoscience-australia-aem-design.json"
GA_AEM_PROBE_RAW = WP8 / "data/geoscience-australia-aem-training-probe-v1"
GA_AEM_PROBE_MANIFEST = GA_AEM_PROBE_RAW / "raw-manifest.json"
GA_AEM_PROBE_INVENTORY = EVIDENCE / "geoscience-australia-aem-training-probe-inventory.json"
GA_AEM_PROBE_CONTRACT = EVIDENCE / "geoscience-australia-aem-training-probe-contract.json"
GA_AEM_MULTISYSTEM_RAW = WP8 / "data/geoscience-australia-aem-multisystem-v1"
GA_AEM_MULTISYSTEM_MANIFEST = GA_AEM_MULTISYSTEM_RAW / "raw-manifest.json"
GA_AEM_MULTISYSTEM_SELECTION = EVIDENCE / "geoscience-australia-aem-multisystem-training-sample.json"
GA_AEM_MULTISYSTEM_INVENTORY = EVIDENCE / "geoscience-australia-aem-multisystem-inventory.json"
GA_AEM_MULTISYSTEM_CONTRACT = EVIDENCE / "geoscience-australia-aem-multisystem-contract.json"
GA_AEM_MULTISYSTEM_SPLIT = EVIDENCE / "geoscience-australia-aem-multisystem-spatial-split.json"
GA_AEM_MULTISYSTEM_DIAGNOSTICS = EVIDENCE / "geoscience-australia-aem-multisystem-train-diagnostics.json"
USGS_AEM_EXPANSION_DESIGN = EVIDENCE / "usgs-aem-training-expansion-design-v1.json"
USGS_AEM_SCHEMA_AUDIT = EVIDENCE / "usgs-aem-training-schema-audit-v1.json"
USGS_AEM_RESPONSE_AUDIT = EVIDENCE / "usgs-aem-training-response-diagnostics-v1.json"
USGS_TEMPEST_2022_AUDIT = EVIDENCE / "usgs-tempest-2022-training-diagnostics-v1.json"
USGS_FLOATEM_TRAINING_DESIGN_POWER = (
    EVIDENCE / "usgs-floatem-training-design-power-v1.json"
)
USGS_LOWER_DELAWARE_FLOATEM = (
    WP8 / "data/usgs-lower-delaware-floatem-sealed/FloaTEM.zip"
)
USGS_AEM_2026_METADATA_AUDIT = (
    EVIDENCE / "usgs-aem-2026-unexposed-metadata-audit-v1.json"
)
KRAUSE_ERT_CONTRACT = EVIDENCE / "usgs-krause-ert-contract.json"
PO_RIVER_DC_DESIGN = EVIDENCE / "po-river-dc-streamer-design-v2.json"
PO_RIVER_DC_TRAINING = EVIDENCE / "po-river-dc-streamer-training-audit-v2.json"
TAIWAN_ERI_METADATA = EVIDENCE / "taiwan-eri-metadata-audit-v1.json"
TAIWAN_ERI_DESIGN = EVIDENCE / "taiwan-eri-design-v1.json"
TAIWAN_ERI_POWER = EVIDENCE / "taiwan-eri-training-power-v1.json"
MOUNT_ST_HELENS_CSAMT_CONTRACT = EVIDENCE / "usgs-mount-st-helens-csamt-contract.json"
HUALAPAI_CSAMT_CONTRACT = EVIDENCE / "usgs-hualapai-csamt-contract.json"
HUALAPAI_CSAMT_RECONCILIATION = EVIDENCE / "hualapai-csamt-role-reconciliation-v1.json"
NTGS_ANGULARLI_CSAMT = EVIDENCE / "ntgs-angularli-csamt-contract-v1.json"
FINAL_AUDIT = EVIDENCE / "final-requirement-audit.json"
TDIP_SPLIT = EVIDENCE / "tdip-date-split.json"
TDIP_DIAGNOSTICS = EVIDENCE / "tdip-train-diagnostics.json"
NTGS_TDIP_COORDINATE_DESIGN = (
    EVIDENCE / "ntgs-pine-creek-tdip-coordinate-design-v1.json"
)
NTGS_TDIP_TRAINING_POWER = (
    EVIDENCE / "ntgs-pine-creek-tdip-training-power-v1.json"
)
TDIP_PATH_READINESS = EVIDENCE / "tdip-path-readiness.json"
POTENTIAL_PATH_READINESS = EVIDENCE / "potential-path-readiness.json"
WISCONSIN_GRAVITY_RAW = WP8 / "data/wisconsin-gravity-v1"
WISCONSIN_GRAVITY_MANIFEST = WISCONSIN_GRAVITY_RAW / "raw-manifest.json"
WISCONSIN_GRAVITY_SPLIT = EVIDENCE / "wisconsin-gravity-design-split.json"
WISCONSIN_GRAVITY_DIAGNOSTICS = EVIDENCE / "wisconsin-gravity-train-diagnostics.json"
NGS99_GRAVITY_RAW = WP8 / "data/ngs99-gravity-v1"
NGS99_GRAVITY_MANIFEST = NGS99_GRAVITY_RAW / "raw-manifest.json"
NGS99_GRAVITY_SPLIT = EVIDENCE / "ngs99-gravity-design-split.json"
NGS99_GRAVITY_DIAGNOSTICS = EVIDENCE / "ngs99-gravity-train-diagnostics.json"
SIERRA_GRAVITY_RAW = WP8 / "data/sierra-nevada-gravity-v1"
SIERRA_GRAVITY_MANIFEST = SIERRA_GRAVITY_RAW / "raw-manifest.json"
SIERRA_GRAVITY_DESIGN = EVIDENCE / "sierra-nevada-gravity-design.json"
SIERRA_GRAVITY_DIAGNOSTICS = EVIDENCE / "sierra-nevada-gravity-train-diagnostics.json"
GA_GRAVITY_RAW = WP8 / "data/ga-national-ground-gravity-catalogue-v1"
GA_GRAVITY_CATALOG_MANIFEST = GA_GRAVITY_RAW / "raw-manifest.json"
GA_GRAVITY_POOL_MANIFEST = GA_GRAVITY_RAW / "pool-manifest.json"
GA_GRAVITY_DESIGN = EVIDENCE / "ga-national-ground-gravity-design.json"
GA_GRAVITY_GEOMETRY = EVIDENCE / "ga-national-ground-gravity-geometry.json"
GA_GRAVITY_UNCERTAINTY = EVIDENCE / "ga-national-ground-gravity-uncertainty.json"
GA_GRAVITY_TRAINING = EVIDENCE / "ga-national-ground-gravity-training.json"
GA_GRAVITY_POWER = EVIDENCE / "ga-national-ground-gravity-power.json"
GA_GRAVITY_SEPARATION = EVIDENCE / "ga-national-ground-gravity-separation.json"
MOUNTAIN_PASS_MAGNETIC_SPLIT = EVIDENCE / "mountain-pass-magnetic-design-split.json"
MOUNTAIN_PASS_MAGNETIC_DIAGNOSTICS = (
    EVIDENCE / "mountain-pass-magnetic-train-diagnostics.json"
)
WESTERN_ARKANSAS_MAGNETIC_RAW = WP8 / "data/western-arkansas-magnetic-v1"
WESTERN_ARKANSAS_MAGNETIC_MANIFEST = WESTERN_ARKANSAS_MAGNETIC_RAW / "raw-manifest.json"
WESTERN_ARKANSAS_MAGNETIC_SPLIT = EVIDENCE / "western-arkansas-magnetic-design-split.json"
WESTERN_ARKANSAS_MAGNETIC_CONTRACT = EVIDENCE / "western-arkansas-magnetic-contract-readiness.json"
WESTERN_ARKANSAS_MAGNETIC_DIAGNOSTICS = (
    EVIDENCE / "western-arkansas-magnetic-train-diagnostics.json"
)
GA_MAGNETIC_CATALOG_RAW = WP8 / "data/geoscience-australia-magnetic-catalog-v1"
GA_MAGNETIC_CATALOG_MANIFEST = GA_MAGNETIC_CATALOG_RAW / "raw-manifest.json"
GA_MAGNETIC_DESIGN = EVIDENCE / "geoscience-australia-magnetic-design.json"
GA_MAGNETIC_DDS_RAW = WP8 / "data/geoscience-australia-magnetic-dds-v1"
GA_MAGNETIC_DDS_MANIFEST = GA_MAGNETIC_DDS_RAW / "raw-manifest.json"
GA_MAGNETIC_DDS_CONTRACT = EVIDENCE / "geoscience-australia-magnetic-dds-contract.json"
GA_MAGNETIC_TRAINING_RAW = WP8 / "data/geoscience-australia-magnetic-training-survey-v1"
GA_MAGNETIC_TRAINING_MANIFEST = GA_MAGNETIC_TRAINING_RAW / "raw-manifest.json"
GA_MAGNETIC_TRAINING_AUDIT = EVIDENCE / "geoscience-australia-magnetic-training-survey.json"
GA_MAGNETIC_CONSORTIUM_RAW = WP8 / "data/geoscience-australia-magnetic-training-consortium-v1"
GA_MAGNETIC_CONSORTIUM_MANIFEST = GA_MAGNETIC_CONSORTIUM_RAW / "raw-manifest.json"
GA_MAGNETIC_CONSORTIUM_AUDIT = EVIDENCE / "geoscience-australia-magnetic-training-consortium.json"
GA_MAGNETIC_EXPANSION_RAW = WP8 / "data/geoscience-australia-magnetic-training-expansion-v1"
GA_MAGNETIC_EXPANSION_MANIFEST = GA_MAGNETIC_EXPANSION_RAW / "raw-manifest.json"
GA_MAGNETIC_EXPANSION_AUDIT = EVIDENCE / "geoscience-australia-magnetic-training-expansion.json"
GA_MAGNETIC_PROBABILITY_RAW = WP8 / "data/geoscience-australia-magnetic-probability-sample-v1"
GA_MAGNETIC_PROBABILITY_MANIFEST = GA_MAGNETIC_PROBABILITY_RAW / "raw-manifest.json"
GA_MAGNETIC_PROBABILITY_SAMPLE = EVIDENCE / "geoscience-australia-magnetic-probability-sample.json"
GA_MAGNETIC_PROBABILITY_AUDIT = EVIDENCE / "geoscience-australia-magnetic-probability-audit.json"
COMBINED_MAGNETIC_DESIGN_V3 = (
    EVIDENCE / "combined-magnetic-provider-survey-design-v3.json"
)
GA_MAGNETIC_COORDINATES_V3 = EVIDENCE / "ga-magnetic-coordinate-only-v3.json"
COMBINED_MAGNETIC_SEPARATION_V3 = (
    EVIDENCE / "combined-magnetic-provider-separation-v3.json"
)
MAGIC_RAW = WP8 / "data/magic-contributions-v1"
MAGIC_ARCHIVE = MAGIC_RAW / "magic-latest-100.zip"
MAGIC_MANIFEST = MAGIC_RAW / "raw-manifest.json"
MAGIC_SPLIT = EVIDENCE / "magic-contribution-design-split.json"
MAGIC_PRIOR = EVIDENCE / "magic-training-remanence-prior.json"
STATIC_PATH_READINESS = EVIDENCE / "static-path-readiness.json"
LITTLE_COLORADO_DC_GEOMETRY = EVIDENCE / "little-colorado-dc-geometry.json"
SERPENTINITE_SIP_GEOMETRY = EVIDENCE / "serpentinite-sip-geometry.json"
GUIDEL_SIP_TRAINING = EVIDENCE / "guidel-sip-training-diagnostics.json"
GUIDEL_SIP_REPEATABILITY = EVIDENCE / "guidel-sip-repeatability.json"
MARTIN2020_FIELD_SIP_TRAINING = (
    EVIDENCE / "zenodo-martin2020-field-sip-training-audit-v1.json"
)
SIP_FDIP_PUBLIC_DATA_AUDIT = EVIDENCE / "sip-fdip-public-data-audit.json"
BC_ARIS_IP_CATALOGUE = EVIDENCE / "bc-aris-ip-digital-catalogue-v1.json"
BC_ARIS_IP_DISCOVERY_SPLIT = EVIDENCE / "bc-aris-ip-discovery-split-v1.json"
BC_ARIS_IP_TRAINING_CLASSIFICATION = (
    EVIDENCE / "bc-aris-ip-training-classification-v1.json"
)
VINEYARD_FIELD_SIP_AUDIT = (
    EVIDENCE / "zenodo-vineyard-field-sip-audit-v1.json"
)
STREAMBED_FIELD_SIP_AUDIT = EVIDENCE / "zenodo-streambed-sip-audit-v1.json"
MENDELEY_HEAVY_METAL_SIP_CONTRACT = (
    Path(__file__).resolve().parent
    / "data/mendeley-heavy-metal-sip-v2/training-only/contract-audit.json"
)
CSAMT_PUBLIC_SEARCH_AUDIT = (
    EVIDENCE / "zenodo-csamt-public-search-audit-v1.json"
)
SEVIER_CSAMT_RAW_AUDIT = (
    EVIDENCE / "usgs-sevier-fault-csamt-raw-audit-v2.json"
)
SAN_ANTONIO_CONTROLLED_SOURCE_AMT_AUDIT = (
    EVIDENCE / "usgs-san-antonio-controlled-source-amt-audit-v1.json"
)
CSAMT_FULL_WAVEFORM_ACCESS_AUDIT = (
    EVIDENCE / "csamt-full-waveform-current-recorder-access-audit-v1.json"
)
NTGS_CR20100883_INVENTORY = (
    EVIDENCE / "ntgs-cr20100883-response-blind-inventory-v1.json"
)
NTGS_CR20100883_CSAMT_DESIGN = (
    EVIDENCE / "ntgs-cr20100883-csamt-design-audit-v1.json"
)
NTGS_CR20130857_CSAMT_DESIGN = (
    EVIDENCE / "ntgs-cr20130857-csamt-design-audit-v1.json"
)
NTGS_CR20130857_CSAMT_TRAINING = (
    EVIDENCE / "ntgs-cr20130857-csamt-training-header-audit-v1.json"
)
CONTROLLED_SOURCE_PATH_READINESS = EVIDENCE / "controlled-source-path-readiness.json"
CSAMT_GEOMETRY = EVIDENCE / "csamt-geometry.json"
CSAMT_LINE_SPLIT_V2 = EVIDENCE / "csamt-line-split-v2.json"
CSAMT_TRAINING_MANIFEST_V2 = (
    WP8 / "data/csamt-consortium-line-split-v2/training-only/training-manifest.json"
)
CSAMT_TRAINING_CONTRACT_V2 = EVIDENCE / "csamt-training-line-contract-v2.json"
WUXI_CSAMT_DESIGN = (
    EVIDENCE / "geodoi-wuxi-csamt-outcome-blind-design-v1.json"
)
WUXI_CSAMT_TRAINING = EVIDENCE / "geodoi-wuxi-csamt-training-audit-v1.json"
BAOTU_WFEM_LINE_SPLIT = EVIDENCE / "baotu-wfem-line-split-v1.json"
BAOTU_WFEM_TRAINING = EVIDENCE / "baotu-wfem-training-audit-v1.json"
BIG_CHINO_CSAMT_DESIGN = EVIDENCE / "usgs-big-chino-csamt-design-v1.json"
BIG_CHINO_CSAMT_TRAINING = EVIDENCE / "usgs-big-chino-csamt-training-audit-v1.json"
BIG_CHINO_CSAMT_POWER_READINESS = (
    EVIDENCE / "usgs-big-chino-csamt-training-power-readiness-v1.json"
)
EXPECTED_BIG_CHINO_CSAMT_POWER_READINESS_SHA256 = (
    "4859487876b7db448d6f599158c07a1bee5a1e550e9dd54d9680b9991aa10840"
)
BIG_CHINO_CSAMT_RAW = Path(__file__).resolve().parent / "data/usgs-big-chino-raw.zip"
BIG_CHINO_CSAMT_INVERSION = (
    Path(__file__).resolve().parent / "data/usgs-big-chino-inversion.zip"
)
GEODATA_CN_LOCKED_METHODS = (
    EVIDENCE / "geodata-cn-locked-methods-metadata-audit-v1.json"
)
TEM1D_PATH_READINESS = EVIDENCE / "tem1d-path-readiness.json"
MT3D_PATH_READINESS = EVIDENCE / "mt3d-path-readiness.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merkle_root(leaves: list[dict[str, Any]]) -> str:
    nodes = [hashlib.sha256(canonical(leaf)).digest() for leaf in leaves]
    if not nodes:
        return hashlib.sha256(b"").hexdigest()
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])
        nodes = [
            hashlib.sha256(nodes[i] + nodes[i + 1]).digest()
            for i in range(0, len(nodes), 2)
        ]
    return nodes[0].hex()


def audit_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    for dataset in manifest["datasets"]:
        for entry in dataset.get("files", []):
            path = OPEN_DATA / entry["path"]
            actual_size = path.stat().st_size if path.is_file() else None
            actual_hash = sha256_file(path) if path.is_file() else None
            members.append(
                {
                    "dataset_slug": dataset["slug"],
                    "path": entry["path"].replace("\\", "/"),
                    "exists": path.is_file(),
                    "expected_bytes": entry.get("expected_bytes"),
                    "manifest_bytes": entry.get("bytes"),
                    "actual_bytes": actual_size,
                    "expected_sha256": entry.get("sha256"),
                    "actual_sha256": actual_hash,
                    "size_matches_manifest": actual_size == entry.get("bytes"),
                    "size_matches_upstream": actual_size == entry.get("expected_bytes"),
                    "hash_matches_manifest": actual_hash == entry.get("sha256"),
                }
            )
    mismatch_count = sum(
        not member["exists"]
        or not member["size_matches_manifest"]
        or not member["hash_matches_manifest"]
        for member in members
    )
    upstream_size_differences = [
        member for member in members if not member["size_matches_upstream"]
    ]
    return {
        "schema_version": "wp8-member-audit-v1",
        "member_count": len(members),
        "member_merkle_root": merkle_root(members),
        "mismatch_count": mismatch_count,
        "upstream_size_difference_count": len(upstream_size_differences),
        "upstream_size_differences": upstream_size_differences,
        "members": members,
    }


CONTRACT_CONCEPTS = {
    "gravity": {"coordinates": ("x", "y", "latitude", "longitude"), "anomaly": ("cba", "gravity"), "crs": ("datum", "projection", "epsg")},
    "magnetic": {"line_id": ("line", "flight"), "height": ("height", "elevation"), "field_correction": ("igrf", "diurnal", "magnetic"), "direction": ("inclination", "declination", "remanence")},
    "dc": {"electrodes": ("abmn", "electrode", "resistivity"), "topography": ("topography", "elevation"), "error": ("error", "accuracy", "precision")},
    "tdip": {"date": ("date", "time"), "electrodes": ("abmn", "electrode"), "windows": ("window", "chargeability"), "error": ("error", "deviation")},
    "sip_fdip": {"complex_response": ("complex", "real", "imaginary", "conductivity"), "profile_link": ("profile", "location", "coordinate"), "frequency": ("frequency", "hz")},
    "tem": {"transmitter": ("transmitter", "loop"), "waveform": ("waveform", "current"), "receiver": ("receiver", "station"), "channels": ("channel", "gate", "time")},
    "mt_amt": {"station": ("station", "site"), "impedance": ("impedance", "zxx", "zxy"), "error": ("error", "variance"), "frequency": ("frequency", "freq")},
    "csamt": {"transmitter": ("transmitter", "source", "gdp32"), "receiver": ("receiver", "station"), "components": ("component", "electric", "magnetic"), "frequency": ("frequency", "freq"), "near_field": ("source distance", "near field", "finite source")},
    "wfem": {"source_geometry": ("source", "transmitter", "geometry"), "receiver": ("receiver", "station"), "phase_component": ("phase", "component"), "apparent_resistivity": ("rho_mn", "apparent resistivity")},
}

SOLVER_PATHS = {
    "gravity": ("simpeg.potential_fields.gravity", "geodeepbayes.forward.gravity"),
    "magnetic": ("simpeg.potential_fields.magnetics", "geodeepbayes.forward.magnetic_vector"),
    "dc": ("simpeg.electromagnetics.static.resistivity", "geodeepbayes.forward.static"),
    "tdip": ("simpeg.electromagnetics.static.spectral_induced_polarization", "geodeepbayes.forward.static"),
    "sip_fdip": ("simpeg.electromagnetics.static.spectral_induced_polarization", "geodeepbayes.forward.static"),
    "tem": ("simpeg.electromagnetics.time_domain", "geodeepbayes.forward.em1d"),
    "mt_amt": ("simpeg.electromagnetics.natural_source", "geodeepbayes.forward.em1d"),
    "csamt": ("simpeg.electromagnetics.frequency_domain", "geodeepbayes.forward.controlled_source"),
    "wfem": ("simpeg.electromagnetics.frequency_domain", "geodeepbayes.forward.controlled_source"),
}

SOLVER_LIMITATIONS = {
    "dc": "research-scale SolverLU path; production resource budget not frozen",
    "tdip": (
        "SimPEG 0.25.2 multi-time Jtvec is not adjoint-consistent; project path "
        "forms an explicit matrix from verified Jvec and is research-scale only"
    ),
    "sip_fdip": (
        "2-D profile/2.5-D finite-volume complex Cole-Cole path is implemented; "
        "explicit finite-difference transpose remains research-scale only"
    ),
    "tem": (
        "Simulation1DLayered is verified; installed 3-D TDEM dependencies remain "
        "unverified without a frozen mesh/time-step resource budget"
    ),
    "mt_amt": (
        "Simulation1DRecursive is verified only when skew/ellipticity/tipper "
        "diagnostics pass; required 2-D/3-D path is not yet verified"
    ),
    "csamt": (
        "finite-line 3-D synthetic solver verified against Geoana Ex only; "
        "Hualapai field metadata still lacks a validated near-field/source-distance contract"
    ),
    "wfem": (
        "finite-line 3-D synthetic solver verified by independent mesh refinement; "
        "Baotu field package lacks receiver/phase/component/geometric-factor contract"
    ),
}


def audit_solver_paths() -> dict[str, Any]:
    methods = {}
    for method, (dependency, implementation) in SOLVER_PATHS.items():
        dependency_found = importlib.util.find_spec(dependency) is not None
        implementation_found = importlib.util.find_spec(implementation) is not None
        methods[method] = {
            "dependency_module": dependency,
            "dependency_found": dependency_found,
            "implementation_module": implementation,
            "implementation_found": implementation_found,
            "status": "candidate" if dependency_found and implementation_found else "blocked",
            "reason": (
                "modules present; method-specific physics verification still required"
                if dependency_found and implementation_found
                else "dependency or project implementation module absent"
            ),
            "known_limitation": SOLVER_LIMITATIONS.get(method),
        }
    return {
        "schema_version": "wp8-solver-inventory-v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "logical_cpu_count": os.cpu_count(),
        "methods": methods,
        "resource_budget_status": "blocked",
        "resource_budget_reason": "no frozen per-method wall-time, memory and abort-limit benchmark",
        "independent_reference_status": "blocked",
        "independent_reference_reason": "no independent codebase/discretization evidence registered",
    }


def audit_observation_contracts(
    manifest: dict[str, Any], datasets: dict[str, Any]
) -> dict[str, Any]:
    """Inventory metadata and archive names without reading observation values."""
    by_slug = {dataset["slug"]: dataset for dataset in manifest["datasets"]}
    results = {}
    for method, choice in datasets["methods"].items():
        source = by_slug[choice["primary_slug"]]
        corpus_parts = [source.get("title", ""), source.get("source_url", "")]
        member_names = []
        for entry in source.get("files", []):
            path = OPEN_DATA / entry["path"]
            member_names.append(entry["path"].replace("\\", "/"))
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    member_names.extend(info.filename for info in archive.infolist())
        dataset_dir = (OPEN_DATA / source["category"] / source["slug"])
        metadata_paths = sorted(
            p for p in dataset_dir.glob("*")
            if p.is_file()
            and (
                p.name.startswith("source_record.")
                or p.suffix.lower() in {".xml", ".md", ".txt"}
                and p.stat().st_size <= 5_000_000
            )
        )
        for path in metadata_paths:
            corpus_parts.append(path.read_text(encoding="utf-8", errors="replace"))
        corpus_parts.extend(member_names)
        corpus = "\n".join(corpus_parts).lower()
        concepts = {}
        for concept, cues in CONTRACT_CONCEPTS[method].items():
            matches = [cue for cue in cues if cue in corpus]
            concepts[concept] = {"observed_cues": matches, "candidate_present": bool(matches)}
        missing = [name for name, value in concepts.items() if not value["candidate_present"]]
        # Token inventory is a design-feasibility check only. A contract becomes
        # passed only after a read-only adapter parses and validates every field.
        results[method] = {
            "dataset_slug": source["slug"],
            "top_level_member_count": len(source.get("files", [])),
            "archive_member_name_count": len(member_names) - len(source.get("files", [])),
            "metadata_paths": [str(p.relative_to(OPEN_DATA)).replace("\\", "/") for p in metadata_paths],
            "concepts": concepts,
            "missing_concepts": missing,
            "status": "blocked",
            "reason": "metadata inventory is not a validated read-only adapter contract",
        }
    return {
        "schema_version": "wp8-observation-contract-inventory-v1",
        "observation_values_read": False,
        "methods": results,
    }


def gate(status: str, reason: str) -> dict[str, str]:
    return {"status": status, "reason": reason}


def license_evidence(choice: dict[str, Any], source: dict[str, Any] | None) -> dict[str, Any]:
    """Read an explicit license/constraints statement from an authoritative record."""
    if source and source.get("rights"):
        return {
            "passed": True,
            "statement": str(source["rights"]),
            "evidence_path": "00_catalog/open_geophysics_data_manifest.json",
            "evidence_sha256": sha256_file(MANIFEST),
        }
    relative = choice.get("license_evidence_path")
    evidence_type = choice.get("license_evidence_type")
    if not relative or not evidence_type:
        return {"passed": False, "statement": "no explicit license evidence registered"}
    path = OPEN_DATA / relative
    if not path.is_file():
        return {"passed": False, "statement": "registered license evidence is missing"}
    if evidence_type == "zenodo_license":
        record = json.loads(path.read_text(encoding="utf-8"))
        license_id = record.get("metadata", {}).get("license", {}).get("id")
        access = record.get("metadata", {}).get("access_right")
        passed = bool(license_id) and access == "open"
        statement = f"Zenodo access_right={access}; license={license_id}"
    elif evidence_type == "fgdc_constraints":
        root = ET.parse(path).getroot()
        access = " ".join((root.findtext(".//accconst") or "").split())
        use = " ".join((root.findtext(".//useconst") or "").split())
        # This is not a policy inference: both declarations are embedded in
        # the dataset's own authoritative FGDC record.
        passed = access.lower().startswith("none") and use.lower().startswith("none")
        statement = f"FGDC access_constraints={access}; use_constraints={use}"
    else:
        return {"passed": False, "statement": f"unsupported evidence type: {evidence_type}"}
    return {
        "passed": passed,
        "statement": statement,
        "evidence_path": relative,
        "evidence_sha256": sha256_file(path),
    }


def make_registration(
    manifest: dict[str, Any],
    datasets: dict[str, Any],
    audit: dict[str, Any],
    field_audit: dict[str, Any],
) -> dict[str, Any]:
    by_slug = {dataset["slug"]: dataset for dataset in manifest["datasets"]}
    audited = {}
    for member in audit["members"]:
        audited.setdefault(member["dataset_slug"], []).append(member)
    methods = {}
    for method in METHOD_NAMES:
        choice = datasets["methods"][method]
        slug = choice["primary_slug"]
        source = by_slug.get(slug)
        members = audited.get(slug, [])
        integrity_ok = bool(members) and all(
            m["exists"] and m["size_matches_manifest"] and m["hash_matches_manifest"]
            for m in members
        )
        rights = license_evidence(choice, source)
        field = field_audit["methods"][method]
        cluster_count = field.get("available_clusters")
        missing = field.get("missing", [])
        gates = {
            "license": gate(
                "passed" if rights["passed"] else "blocked",
                rights["statement"],
            ),
            "integrity": gate(
                "passed" if integrity_ok else "failed",
                "all selected top-level members match manifest"
                if integrity_ok
                else "selected member missing or size/hash mismatch",
            ),
            "observation_contract": gate(
                "blocked",
                "; ".join(missing)
                if missing
                else "structural field audit remains candidate-only",
            ),
            "clusters": gate(
                "blocked",
                f"design-only cluster candidates={cluster_count}; correlation length and buffered split not frozen",
            ),
            "power": gate(
                "blocked",
                "coverage cluster count alone is insufficient; training-only paired-CRPS effect size is unavailable",
            ),
            "dimensionality": gate(
                "blocked",
                "preregistered method-specific dimensionality diagnostic not executed",
            ),
            "solver": gate(
                "blocked",
                "versioned solver path has not passed method-specific readiness checks",
            ),
            "independent_reference": gate(
                "blocked",
                "independent reference implementation/discretization not evidenced",
            ),
            "resource_budget": gate(
                "blocked",
                "frozen local CPU resource estimate and abort limits not evidenced",
            ),
        }
        methods[method] = {
            "dataset_slug": slug,
            "license_evidence": rights,
            "gates": gates,
        }
    # The selected external MT backup is the authoritative MT state.  Recompute
    # its gates from the protected raw/split/training evidence rather than
    # leaking the superseded Parkfield inventory into the decision.
    mt_evidence = audit_selected_usarray_mt()
    methods["mt_amt"] = {
        "dataset_slug": "EarthScope_USArray_TA_EMTF",
        "license_evidence": mt_evidence["license_evidence"],
        "gates": mt_evidence["gates"],
    }
    tdip_evidence = audit_selected_tdip()
    methods["tdip"]["gates"].update(tdip_evidence["gates"])
    potential_evidence = audit_potential_paths()
    for method in ("gravity", "magnetic"):
        methods[method]["gates"].update(potential_evidence[method]["gates"])
    methods["gravity"]["gates"].update(audit_selected_gravity()["gates"])
    methods["magnetic"]["gates"].update(audit_selected_magnetic()["gates"])
    static_evidence = audit_static_paths()
    for method in ("dc", "sip_fdip"):
        methods[method]["gates"].update(static_evidence[method]["gates"])
    controlled_evidence = audit_controlled_source_paths()
    for method in ("csamt", "wfem"):
        methods[method]["gates"].update(controlled_evidence[method]["gates"])
    tem_evidence = audit_selected_east_river_tem()
    methods["tem"]["dataset_slug"] = "USGS_UpperEastRiver_VTEM_ET_2017"
    methods["tem"]["license_evidence"] = tem_evidence["license_evidence"]
    methods["tem"]["gates"].update(tem_evidence["gates"])
    methods["tem"]["gates"].update(audit_tem1d_path()["gates"])
    gate_producer_path = Path(bind_gate_evidence.__code__.co_filename)
    producer_sha256 = sha256_file(gate_producer_path)
    for method, method_payload in methods.items():
        dataset_slug = method_payload["dataset_slug"]
        for gate_name, gate_payload in tuple(method_payload["gates"].items()):
            method_payload["gates"][gate_name] = bind_gate_evidence(
                method=method,
                dataset_slug=dataset_slug,
                gate_name=gate_name,
                status=gate_payload["status"],
                reason=gate_payload["reason"],
                producer="src/geodeepbayes/validation/feasibility.py",
                producer_sha256=producer_sha256,
                measurements={"affirmative_gate": gate_payload["status"] == "passed"},
                thresholds={"required_status": "passed"},
            )
    return {
        "schema_version": "wp8-feasibility-registration-v1",
        "manifest_sha256": sha256_file(MANIFEST),
        "dataset_selection_sha256": sha256_file(DATASETS),
        "preregistration_sha256": sha256_file(PREREG),
        "methods": methods,
    }


def audit_selected_gravity() -> dict[str, Any]:
    required = (
        WISCONSIN_GRAVITY_MANIFEST,
        WISCONSIN_GRAVITY_SPLIT,
        WISCONSIN_GRAVITY_DIAGNOSTICS,
        NGS99_GRAVITY_MANIFEST,
        NGS99_GRAVITY_SPLIT,
        NGS99_GRAVITY_DIAGNOSTICS,
        SIERRA_GRAVITY_MANIFEST,
        SIERRA_GRAVITY_DESIGN,
        SIERRA_GRAVITY_DIAGNOSTICS,
        GA_GRAVITY_CATALOG_MANIFEST,
        GA_GRAVITY_POOL_MANIFEST,
        GA_GRAVITY_DESIGN,
        GA_GRAVITY_GEOMETRY,
        GA_GRAVITY_UNCERTAINTY,
        GA_GRAVITY_TRAINING,
        GA_GRAVITY_POWER,
        GA_GRAVITY_SEPARATION,
    )
    if any(not path.is_file() for path in required):
        raise RuntimeError("gravity expansion evidence chain is incomplete")
    wisconsin_manifest = json.loads(
        WISCONSIN_GRAVITY_MANIFEST.read_text(encoding="utf-8")
    )
    wisconsin_split = json.loads(WISCONSIN_GRAVITY_SPLIT.read_text(encoding="utf-8"))
    wisconsin_train = json.loads(
        WISCONSIN_GRAVITY_DIAGNOSTICS.read_text(encoding="utf-8")
    )
    ngs_manifest = json.loads(NGS99_GRAVITY_MANIFEST.read_text(encoding="utf-8"))
    ngs_split = json.loads(NGS99_GRAVITY_SPLIT.read_text(encoding="utf-8"))
    ngs_train = json.loads(NGS99_GRAVITY_DIAGNOSTICS.read_text(encoding="utf-8"))
    sierra_manifest = json.loads(SIERRA_GRAVITY_MANIFEST.read_text(encoding="utf-8"))
    sierra_design = json.loads(SIERRA_GRAVITY_DESIGN.read_text(encoding="utf-8"))
    sierra_train = json.loads(
        SIERRA_GRAVITY_DIAGNOSTICS.read_text(encoding="utf-8")
    )
    ga_catalog = json.loads(GA_GRAVITY_CATALOG_MANIFEST.read_text(encoding="utf-8"))
    ga_pool = json.loads(GA_GRAVITY_POOL_MANIFEST.read_text(encoding="utf-8"))
    ga_design = json.loads(GA_GRAVITY_DESIGN.read_text(encoding="utf-8"))
    ga_geometry = json.loads(GA_GRAVITY_GEOMETRY.read_text(encoding="utf-8"))
    ga_uncertainty = json.loads(GA_GRAVITY_UNCERTAINTY.read_text(encoding="utf-8"))
    ga_training = json.loads(GA_GRAVITY_TRAINING.read_text(encoding="utf-8"))
    ga_power = json.loads(GA_GRAVITY_POWER.read_text(encoding="utf-8"))
    ga_separation = json.loads(GA_GRAVITY_SEPARATION.read_text(encoding="utf-8"))
    errors = []
    wisconsin_archive = Path(wisconsin_manifest.get("archive", {}).get("path", ""))
    if not wisconsin_archive.is_absolute():
        wisconsin_archive = ROOT / wisconsin_archive
    if (
        wisconsin_manifest.get("schema_version")
        != "wp8-wisconsin-gravity-raw-manifest-v1"
        or wisconsin_manifest.get("response_values_interpreted") is not False
        or not wisconsin_archive.is_file()
        or wisconsin_archive.stat().st_size
        != wisconsin_manifest.get("archive", {}).get("bytes")
        or sha256_file(wisconsin_archive)
        != wisconsin_manifest.get("archive", {}).get("sha256")
        or wisconsin_split.get("schema_version")
        != "wp8-wisconsin-gravity-design-split-v1"
        or wisconsin_split.get("source", {}).get("archive_sha256")
        != sha256_file(wisconsin_archive)
        or wisconsin_split.get("format_contract", {}).get("response_fields_values_parsed")
        is not False
        or wisconsin_train.get("schema_version")
        != "wp8-wisconsin-gravity-training-diagnostics-v1"
        or wisconsin_train.get("split_sha256")
        != wisconsin_split.get("design_sha256")
        or wisconsin_train.get("response_policy", {}).get("buffer_rows_interpreted") != 0
        or wisconsin_train.get("response_policy", {}).get("calibration_rows_interpreted")
        != 0
        or wisconsin_train.get("response_policy", {}).get("test_rows_interpreted") != 0
        or wisconsin_train.get("correlation_adjusted_test_cluster_upper_bound") != 1
        or wisconsin_train.get("dimensionality", {}).get("passed") is not True
    ):
        errors.append("wisconsin")
    ngs_files = {item["name"]: item for item in ngs_manifest.get("files", [])}
    for name, member in ngs_files.items():
        path = NGS99_GRAVITY_RAW / name
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"ngs99-member:{name}")
            break
    if (
        ngs_manifest.get("schema_version") != "wp8-ngs99-gravity-raw-manifest-v1"
        or ngs_manifest.get("response_values_interpreted") is not False
        or ngs_split.get("schema_version") != "wp8-ngs99-gravity-design-split-v1"
        or ngs_split.get("format_contract", {}).get("response_fields_values_parsed")
        is not False
        or ngs_train.get("schema_version")
        != "wp8-ngs99-gravity-training-diagnostics-v1"
        or ngs_train.get("response_policy", {}).get("buffer_rows_interpreted") != 0
        or ngs_train.get("response_policy", {}).get("calibration_rows_interpreted") != 0
        or ngs_train.get("response_policy", {}).get("test_rows_interpreted") != 0
        or ngs_train.get("conservative_spatial_correlation_range_km") != 2000.0
        or ngs_train.get("dimensionality", {}).get("passed") is not True
    ):
        errors.append("ngs99")
    for member in sierra_manifest.get("members", []):
        path = SIERRA_GRAVITY_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"sierra-member:{member['path']}")
            break
    if (
        sierra_manifest.get("schema_version")
        != "wp8-sierra-nevada-gravity-raw-freeze-v1"
        or sierra_manifest.get("license") != "CC0 1.0 Universal"
        or sierra_manifest.get("response_values_interpreted_during_acquisition") != 0
        or sierra_design.get("schema_version")
        != "wp8-sierra-nevada-gravity-design-v1"
        or sierra_design.get("raw_manifest_sha256")
        != sha256_file(SIERRA_GRAVITY_MANIFEST)
        or sierra_design.get("formal_excluded_ids") != ["CH75"]
        or sierra_design.get("response_fields_interpreted") != 0
        or sierra_design.get("partition_block_counts")
        != {"train": 107, "buffer": 48, "calibration": 59, "test": 320}
        or sierra_design.get("test_unseal_count") != 0
        or sierra_train.get("schema_version")
        != "wp8-sierra-nevada-gravity-train-diagnostics-v1"
        or sierra_train.get("raw_manifest_sha256")
        != sha256_file(SIERRA_GRAVITY_MANIFEST)
        or sierra_train.get("design_sha256")
        != sha256_file(SIERRA_GRAVITY_DESIGN)
        or sierra_train.get("training_response_rows_interpreted") != 5585
        or sierra_train.get("response_rows_interpreted")
        != {"train": 5585, "buffer": 0, "calibration": 0, "test": 0}
        or sierra_train.get("correlation_range_km") != 62.5
        or sierra_train.get("correlation_adjusted_test_cluster_upper_bound") != 42
        or sierra_train.get("cluster_power_gate_passes") is not False
        or sierra_train.get("per_observation_uncertainty_contract_ready") is not False
        or sierra_train.get("test_unseal_count") != 0
    ):
        errors.append("sierra-nevada")
    if (
        ga_catalog.get("schema_version")
        != "wp8-ga-national-ground-gravity-catalogue-v1"
        or ga_catalog.get("dataset_count") != 1634
        or ga_catalog.get("declared_station_total") != 1840331
        or ga_catalog.get("response_values_interpreted_during_acquisition") != 0
        or ga_pool.get("schema_version")
        != "wp8-ga-national-ground-gravity-pool-v1"
        or ga_pool.get("member_count") != 1633
        or ga_pool.get("formal_excluded_surveys") != ["P199964"]
        or ga_pool.get("response_values_interpreted_during_acquisition") != 0
        or ga_design.get("formal_excluded_surveys") != ["P199964"]
        or ga_design.get("partition_block_counts")
        != {"train": 144, "buffer": 94, "calibration": 106, "test": 491}
        or ga_design.get("test_unseal_count") != 0
        or ga_geometry.get("survey_status_counts")
        != {"excluded_cross_role_footprint": 1108, "retained": 525}
        or ga_geometry.get("retained_unique_block_counts")
        != {"train": 48, "buffer": 27, "calibration": 29, "test": 302}
        or ga_geometry.get("response_fields_read") != []
        or ga_uncertainty.get("uncertainty_qualified_test_cluster_upper_bound")
        != 301
        or ga_uncertainty.get("response_fields_read") != []
        or ga_training.get("response_policy", {}).get("train_rows_interpreted")
        != 53066
        or ga_training.get("response_policy", {}).get("buffer_rows_interpreted")
        != 0
        or ga_training.get("response_policy", {}).get(
            "calibration_rows_interpreted"
        )
        != 0
        or ga_training.get("response_policy", {}).get("test_rows_interpreted")
        != 0
        or ga_training.get("correlation_range_km") != 12.5
        or ga_training.get("complete_bouguer_contract") is not True
        or ga_training.get("per_observation_uncertainty_contract") is not True
        or ga_power.get("paired_training_blocks") != 48
        or ga_power.get("required_paired_crps_clusters") != 153
        or ga_power.get("required_clusters_all_metrics") != 223
        or ga_power.get("wp8_0_power_gate_passes") is not True
        or ga_power.get("test_responses_interpreted") != 0
        or ga_separation.get("accepted_independent_test_surveys") != 261
        or ga_separation.get("required_clusters_all_metrics") != 223
        or ga_separation.get("provider_spatial_power_gate_passes") is not True
        or ga_separation.get("response_fields_read") != []
        or ga_separation.get("test_responses_interpreted") != 0
        or ga_separation.get("test_unseal_count") != 0
    ):
        errors.append("ga-national-ground-gravity")
    if errors:
        raise RuntimeError("gravity evidence-chain failure: " + ", ".join(errors))
    return {
        "gates": {
            "observation_contract": gate(
                "passed",
                "GA national pool supplies spherical-cap Bouguer plus Bullard-C "
                "terrain correction and pointwise propagated uncertainty; all 53,066 "
                "interpreted training rows satisfy the frozen contract",
            ),
            "clusters": gate(
                "passed",
                "GA training-only range is 12.5 km; one-unit-per-provider and "
                "train/calibration plus pairwise spatial separation retain 261 sealed "
                "independent test surveys",
            ),
            "power": gate(
                "passed",
                "training-block paired-CRPS dispersion requires 153 clusters for a "
                "10% improvement; coverage equivalence requires 223 and 261 remain",
            ),
            "dimensionality": gate(
                "passed",
                "training-only regional detrending and variograms select mandatory 3-D for both statewide and continental station coverage",
            ),
        }
    }


def audit_selected_magnetic() -> dict[str, Any]:
    required = (
        MOUNTAIN_PASS_MAGNETIC_SPLIT,
        MOUNTAIN_PASS_MAGNETIC_DIAGNOSTICS,
        WESTERN_ARKANSAS_MAGNETIC_MANIFEST,
        WESTERN_ARKANSAS_MAGNETIC_SPLIT,
        WESTERN_ARKANSAS_MAGNETIC_CONTRACT,
        WESTERN_ARKANSAS_MAGNETIC_DIAGNOSTICS,
        GA_MAGNETIC_CATALOG_MANIFEST,
        GA_MAGNETIC_DESIGN,
        GA_MAGNETIC_DDS_MANIFEST,
        GA_MAGNETIC_DDS_CONTRACT,
        GA_MAGNETIC_TRAINING_MANIFEST,
        GA_MAGNETIC_TRAINING_AUDIT,
        GA_MAGNETIC_CONSORTIUM_MANIFEST,
        GA_MAGNETIC_CONSORTIUM_AUDIT,
        GA_MAGNETIC_EXPANSION_MANIFEST,
        GA_MAGNETIC_EXPANSION_AUDIT,
        GA_MAGNETIC_PROBABILITY_MANIFEST,
        GA_MAGNETIC_PROBABILITY_SAMPLE,
        GA_MAGNETIC_PROBABILITY_AUDIT,
        COMBINED_MAGNETIC_DESIGN_V3,
        GA_MAGNETIC_COORDINATES_V3,
        COMBINED_MAGNETIC_SEPARATION_V3,
        MAGIC_ARCHIVE,
        MAGIC_MANIFEST,
        MAGIC_SPLIT,
        MAGIC_PRIOR,
    )
    if any(not path.is_file() for path in required):
        raise RuntimeError("selected magnetic evidence chain is incomplete")
    survey_split = json.loads(
        MOUNTAIN_PASS_MAGNETIC_SPLIT.read_text(encoding="utf-8")
    )
    survey_diagnostic = json.loads(
        MOUNTAIN_PASS_MAGNETIC_DIAGNOSTICS.read_text(encoding="utf-8")
    )
    arkansas_manifest = json.loads(
        WESTERN_ARKANSAS_MAGNETIC_MANIFEST.read_text(encoding="utf-8")
    )
    arkansas_split = json.loads(
        WESTERN_ARKANSAS_MAGNETIC_SPLIT.read_text(encoding="utf-8")
    )
    arkansas_contract = json.loads(
        WESTERN_ARKANSAS_MAGNETIC_CONTRACT.read_text(encoding="utf-8")
    )
    arkansas_diagnostic = json.loads(
        WESTERN_ARKANSAS_MAGNETIC_DIAGNOSTICS.read_text(encoding="utf-8")
    )
    ga_catalog_manifest = json.loads(
        GA_MAGNETIC_CATALOG_MANIFEST.read_text(encoding="utf-8")
    )
    ga_design = json.loads(GA_MAGNETIC_DESIGN.read_text(encoding="utf-8"))
    ga_dds_manifest = json.loads(
        GA_MAGNETIC_DDS_MANIFEST.read_text(encoding="utf-8")
    )
    ga_contract = json.loads(
        GA_MAGNETIC_DDS_CONTRACT.read_text(encoding="utf-8")
    )
    ga_training_manifest = json.loads(
        GA_MAGNETIC_TRAINING_MANIFEST.read_text(encoding="utf-8")
    )
    ga_training = json.loads(
        GA_MAGNETIC_TRAINING_AUDIT.read_text(encoding="utf-8")
    )
    ga_consortium_manifest = json.loads(
        GA_MAGNETIC_CONSORTIUM_MANIFEST.read_text(encoding="utf-8")
    )
    ga_consortium = json.loads(
        GA_MAGNETIC_CONSORTIUM_AUDIT.read_text(encoding="utf-8")
    )
    ga_expansion_manifest = json.loads(
        GA_MAGNETIC_EXPANSION_MANIFEST.read_text(encoding="utf-8")
    )
    ga_expansion = json.loads(
        GA_MAGNETIC_EXPANSION_AUDIT.read_text(encoding="utf-8")
    )
    ga_probability_manifest = json.loads(
        GA_MAGNETIC_PROBABILITY_MANIFEST.read_text(encoding="utf-8")
    )
    ga_probability_sample = json.loads(
        GA_MAGNETIC_PROBABILITY_SAMPLE.read_text(encoding="utf-8")
    )
    ga_probability = json.loads(
        GA_MAGNETIC_PROBABILITY_AUDIT.read_text(encoding="utf-8")
    )
    combined_design_v3 = json.loads(
        COMBINED_MAGNETIC_DESIGN_V3.read_text(encoding="utf-8")
    )
    ga_coordinates_v3 = json.loads(
        GA_MAGNETIC_COORDINATES_V3.read_text(encoding="utf-8")
    )
    combined_separation_v3 = json.loads(
        COMBINED_MAGNETIC_SEPARATION_V3.read_text(encoding="utf-8")
    )
    raw_manifest = json.loads(MAGIC_MANIFEST.read_text(encoding="utf-8"))
    prior_split = json.loads(MAGIC_SPLIT.read_text(encoding="utf-8"))
    prior = json.loads(MAGIC_PRIOR.read_text(encoding="utf-8"))
    errors = []
    archive = raw_manifest.get("archive", {})
    if (
        raw_manifest.get("schema_version") != "wp8-magic-raw-manifest-v1"
        or archive.get("bytes") != MAGIC_ARCHIVE.stat().st_size
        or archive.get("sha256") != sha256_file(MAGIC_ARCHIVE)
        or raw_manifest.get("response_values_interpreted") is not False
        or raw_manifest.get("excluded_contribution_ids") != [20710]
    ):
        errors.append("magic-raw-manifest")
    if (
        survey_split.get("schema_version")
        != "wp8-mountain-pass-magnetic-design-split-v1"
        or survey_split.get("created_before_response_interpretation") is not True
        or survey_split.get("design_contract", {}).get(
            "response_fields_values_parsed"
        )
        is not False
        or any(survey_split.get("cell_overlap_counts", {}).values())
        or survey_split.get("counts", {}).get("test", {}).get(
            "spatial_cells_1km"
        )
        != 43
    ):
        errors.append("mountain-pass-design-split")
    if (
        prior_split.get("schema_version")
        != "wp8-magic-contribution-design-split-v1"
        or prior_split.get("archive_sha256") != archive.get("sha256")
        or prior_split.get("excluded_contribution_ids") != [20710]
        or prior_split.get("counts")
        != {"buffer": 10, "calibration": 16, "test": 9, "train": 64}
        or prior_split.get("contribution_overlap") is not False
        or prior_split.get("response_values_interpreted") is not False
    ):
        errors.append("magic-design-split")
    if (
        prior.get("schema_version")
        != "wp8-magic-training-remanence-prior-v1"
        or prior.get("raw_archive_sha256") != archive.get("sha256")
        or prior.get("design_split_sha256") != sha256_file(MAGIC_SPLIT)
        or prior.get("training_contributions_interpreted") != 64
        or prior.get("buffer_contributions_interpreted") != 0
        or prior.get("calibration_contributions_interpreted") != 0
        or prior.get("test_contributions_interpreted") != 0
        or prior.get("excluded_contribution_ids") != [20710]
        or prior.get("complete_vector_rows") != 5905
        or prior.get("complete_vector_contributions") != 21
        or prior.get("prior_gate_passed") is not True
        or prior.get("held_out_response_values_read") is not False
    ):
        errors.append("magic-training-prior")
    if (
        survey_diagnostic.get("schema_version")
        != "wp8-mountain-pass-magnetic-train-diagnostics-v1"
        or survey_diagnostic.get("split_sha256")
        != sha256_file(MOUNTAIN_PASS_MAGNETIC_SPLIT)
        or survey_diagnostic.get("remanence_prior_sha256") != sha256_file(MAGIC_PRIOR)
        or survey_diagnostic.get("training_rows_interpreted") != 23661
        or survey_diagnostic.get("sealed_response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or survey_diagnostic.get("training_cells_1km") != 113
        or survey_diagnostic.get("conservative_spatial_correlation_range_m") != 1500.0
        or survey_diagnostic.get("correlation_adjusted_test_cluster_upper_bound") != 15
        or survey_diagnostic.get("flight_line_spectrum", {}).get("passed") is not True
        or survey_diagnostic.get("height_sensitivity", {}).get("passed") is not True
        or survey_diagnostic.get("remanence_sensitivity", {}).get("passed") is not True
        or survey_diagnostic.get("dimensionality", {}).get("passed") is not True
    ):
        errors.append("mountain-pass-training-diagnostics")
    arkansas_members = {
        item["path"]: item for item in arkansas_manifest.get("members", [])
    }
    for name, member in arkansas_members.items():
        path = WESTERN_ARKANSAS_MAGNETIC_RAW / name
        if (
            not path.is_file()
            or path.stat().st_size != member.get("bytes")
            or sha256_file(path) != member.get("sha256")
        ):
            errors.append(f"western-arkansas-member:{name}")
            break
    if (
        arkansas_manifest.get("schema_version")
        != "wp8-western-arkansas-magnetic-raw-freeze-v1"
        or arkansas_manifest.get("response_values_interpreted_during_acquisition") != 0
        or arkansas_split.get("schema_version")
        != "wp8-western-arkansas-magnetic-design-split-v1"
        or arkansas_split.get("magnetic_response_values_interpreted") != 0
        or arkansas_split.get("calibration_responses_interpreted") != 0
        or arkansas_split.get("test_responses_interpreted") != 0
        or arkansas_contract.get("schema_version")
        != "wp8-western-arkansas-magnetic-contract-readiness-v1"
        or arkansas_contract.get("raw_manifest_sha256")
        != sha256_file(WESTERN_ARKANSAS_MAGNETIC_MANIFEST)
        or arkansas_contract.get("design_split_sha256")
        != sha256_file(WESTERN_ARKANSAS_MAGNETIC_SPLIT)
        or arkansas_contract.get("observation_contract_passed") is not True
        or arkansas_contract.get("formal_uncertainty_model_ready") is not False
        or arkansas_diagnostic.get("schema_version")
        != "wp8-western-arkansas-magnetic-train-diagnostics-v1"
        or arkansas_diagnostic.get("split_sha256")
        != sha256_file(WESTERN_ARKANSAS_MAGNETIC_SPLIT)
        or arkansas_diagnostic.get("response_policy", {}).get("buffer_rows_interpreted") != 0
        or arkansas_diagnostic.get("response_policy", {}).get("calibration_rows_interpreted") != 0
        or arkansas_diagnostic.get("response_policy", {}).get("test_rows_interpreted") != 0
        or arkansas_diagnostic.get("conservative_spatial_correlation_range_m") != 21000.0
        or arkansas_diagnostic.get("correlation_adjusted_test_clusters") != 0
        or arkansas_diagnostic.get("dimensionality", {}).get("passed") is not True
    ):
        errors.append("western-arkansas-evidence-chain")
    if (
        ga_catalog_manifest.get("schema_version")
        != "wp8-geoscience-australia-magnetic-catalog-freeze-v1"
        or ga_catalog_manifest.get("feature_count") != 1454
        or ga_catalog_manifest.get("catalogue_is_design_metadata_only") is not True
        or ga_catalog_manifest.get("magnetic_response_values_interpreted") != 0
        or ga_design.get("schema_version")
        != "wp8-geoscience-australia-magnetic-design-v1"
        or ga_design.get("catalogue_manifest_sha256")
        != sha256_file(GA_MAGNETIC_CATALOG_MANIFEST)
        or ga_design.get("formal_excluded_dataset_numbers") != [17638]
        or ga_design.get("partition_counts")
        != {"train": 1123, "buffer": 404, "calibration": 400, "test": 645}
        or ga_design.get("magnetic_response_values_interpreted") != 0
        or ga_design.get("test_unseal_count") != 0
        or ga_dds_manifest.get("schema_version")
        != "wp8-ga-magnetic-dds-freeze-v1"
        or ga_dds_manifest.get("design_sha256") != sha256_file(GA_MAGNETIC_DESIGN)
        or ga_dds_manifest.get("successful_products") != 598
        or ga_dds_manifest.get("failed_products") != []
        or ga_dds_manifest.get("dds_contains_declarations_only") is not True
        or ga_dds_manifest.get("variable_attributes_requested") is not False
        or ga_dds_manifest.get("magnetic_response_values_interpreted") != 0
        or ga_contract.get("schema_version")
        != "wp8-geoscience-australia-magnetic-dds-contract-v1"
        or ga_contract.get("design_sha256") != sha256_file(GA_MAGNETIC_DESIGN)
        or ga_contract.get("dds_manifest_sha256")
        != sha256_file(GA_MAGNETIC_DDS_MANIFEST)
        or ga_contract.get("coverage", {})
        .get("geometry_response", {})
        .get("partition_cell_counts", {})
        .get("test")
        != 305
        or ga_contract.get("coverage", {})
        .get("plus_explicit_corrections", {})
        .get("partition_cell_counts", {})
        .get("test")
        != 7
        or ga_contract.get("coverage", {})
        .get("plus_uncertainty", {})
        .get("product_count")
        != 0
        or ga_contract.get("formal_contract_ready") is not False
        or ga_contract.get("test_unseal_count") != 0
        or ga_training_manifest.get("schema_version")
        != "wp8-ga-magnetic-training-survey-freeze-v1"
        or ga_training_manifest.get("design_sha256")
        != sha256_file(GA_MAGNETIC_DESIGN)
        or ga_training_manifest.get("dataset_no") != 16980
        or ga_training_manifest.get("acquisition_interpreted_response_values") != 0
        or ga_training.get("schema_version")
        != "wp8-ga-magnetic-training-survey-audit-v1"
        or ga_training.get("raw_manifest_sha256")
        != sha256_file(GA_MAGNETIC_TRAINING_MANIFEST)
        or ga_training.get("response_rows_interpreted")
        != {"train": 2076119, "buffer": 0, "calibration": 0, "test": 0}
        or ga_training.get("geometry_rows_by_role", {}).get("test") != 1141327
        or ga_training.get("training_crossover_error", {}).get(
            "bins_with_main_and_tie"
        )
        != 1479
        or ga_training.get("training_crossover_error", {}).get("method_ready")
        is not True
        or ga_training.get("national_correlation_ready") is not False
        or ga_training.get("formal_contract_ready") is not False
        or ga_training.get("test_unseal_count") != 0
        or ga_consortium_manifest.get("schema_version")
        != "wp8-ga-magnetic-training-consortium-freeze-v1"
        or ga_consortium_manifest.get("design_sha256")
        != sha256_file(GA_MAGNETIC_DESIGN)
        or ga_consortium_manifest.get("dataset_numbers")
        != [16401, 16871, 18058, 18234, 18444, 15072]
        or ga_consortium_manifest.get("acquisition_interpreted_response_values") != 0
        or ga_consortium.get("schema_version")
        != "wp8-ga-magnetic-training-consortium-audit-v1"
        or ga_consortium.get("raw_manifest_sha256")
        != sha256_file(GA_MAGNETIC_CONSORTIUM_MANIFEST)
        or ga_consortium.get("total_training_rows_interpreted") != 650783
        or ga_consortium.get("response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or ga_consortium.get("conservative_pilot_correlation_range_m") != 17500.0
        or ga_consortium.get("total_crossover_bins") != 1565
        or ga_consortium.get("pilot_geometry_response_test_clusters") != 305
        or ga_consortium.get("pilot_power_count_possible") is not True
        or ga_consortium.get("national_correlation_ready") is not False
        or ga_consortium.get("formal_contract_ready") is not False
        or ga_consortium.get("test_unseal_count") != 0
        or ga_expansion_manifest.get("schema_version")
        != "wp8-ga-magnetic-training-expansion-freeze-v1"
        or ga_expansion_manifest.get("design_sha256")
        != sha256_file(GA_MAGNETIC_DESIGN)
        or len(ga_expansion_manifest.get("dataset_numbers", [])) != 14
        or ga_expansion_manifest.get("acquisition_interpreted_response_values") != 0
        or ga_expansion.get("schema_version")
        != "wp8-ga-magnetic-training-consortium-audit-v1"
        or ga_expansion.get("raw_manifest_sha256")
        != sha256_file(GA_MAGNETIC_EXPANSION_MANIFEST)
        or ga_expansion.get("products_sampled") != 14
        or ga_expansion.get("total_training_rows_interpreted") != 6233124
        or ga_expansion.get("response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or ga_expansion.get("conservative_pilot_correlation_range_m") != 22500.0
        or ga_expansion.get("total_crossover_bins") != 7210
        or ga_expansion.get("pilot_power_count_possible") is not True
        or ga_expansion.get("national_correlation_ready") is not False
        or ga_expansion.get("formal_contract_ready") is not False
        or ga_expansion.get("test_unseal_count") != 0
        or ga_probability_sample.get("schema_version")
        != "wp8-ga-magnetic-cell-weighted-probability-sample-v1"
        or ga_probability_sample.get("sample_size") != 20
        or ga_probability_sample.get("magnetic_response_values_interpreted") != 0
        or ga_probability_sample.get("test_unseal_count") != 0
        or ga_probability_manifest.get("schema_version")
        != "wp8-ga-magnetic-probability-sample-freeze-v1"
        or ga_probability_manifest.get("sample_sha256")
        != sha256_file(GA_MAGNETIC_PROBABILITY_SAMPLE)
        or ga_probability_manifest.get("design_sha256")
        != sha256_file(GA_MAGNETIC_DESIGN)
        or ga_probability_manifest.get("dds_contract_sha256")
        != sha256_file(GA_MAGNETIC_DDS_CONTRACT)
        or len(ga_probability_manifest.get("members", [])) != 19
        or ga_probability_manifest.get("acquisition_interpreted_response_values") != 0
        or ga_probability_manifest.get("test_responses_interpreted") != 0
        or ga_probability_manifest.get("test_unseal_count") != 0
        or ga_probability.get("schema_version")
        != "wp8-ga-magnetic-probability-audit-v1"
        or ga_probability.get("sample_sha256")
        != sha256_file(GA_MAGNETIC_PROBABILITY_SAMPLE)
        or ga_probability.get("raw_manifest_sha256")
        != sha256_file(GA_MAGNETIC_PROBABILITY_MANIFEST)
        or ga_probability.get("sampled_cells") != 20
        or ga_probability.get("successful_sampled_cells") != 18
        or ga_probability.get("all_sampled_cells_succeed") is not False
        or ga_probability.get("maximum_observed_correlation_range_m") != 100000.0
        or ga_probability.get("censored_product_count") != 1
        or ga_probability.get("response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or ga_probability.get("formal_correlation_power_gate_passes") is not False
        or ga_probability.get("test_unseal_count") != 0
    ):
        errors.append("geoscience-australia-catalog-dds-chain")
    if (
        combined_design_v3.get("schema_version")
        != "wp8-combined-magnetic-provider-design-v3"
        or combined_design_v3.get("correlation_range_km") != 75.0
        or combined_design_v3.get("ga_coordinate_only_pool_count") != 289
        or combined_design_v3.get("required_independent_test_count") != 223
        or combined_design_v3.get("test_unseal_count") != 0
        or ga_coordinates_v3.get("schema_version")
        != "wp8-ga-magnetic-coordinate-only-v3"
        or ga_coordinates_v3.get("combined_design_sha256")
        != sha256_file(COMBINED_MAGNETIC_DESIGN_V3)
        or ga_coordinates_v3.get("coordinate_pool_count") != 289
        or ga_coordinates_v3.get("candidate_count") != 288
        or ga_coordinates_v3.get("excluded_coordinate_datasets")
        != [
            {
                "dataset_no": 17858,
                "reason": "latitude/longitude variables contain no valid coordinate pair",
                "response_variables_requested": 0,
                "test_unseal_count": 0,
            }
        ]
        or ga_coordinates_v3.get("response_variables_requested") != 0
        or ga_coordinates_v3.get("test_unseal_count") != 0
        or combined_separation_v3.get("schema_version")
        != "wp8-combined-magnetic-provider-separation-v3"
        or combined_separation_v3.get("combined_design_sha256")
        != sha256_file(COMBINED_MAGNETIC_DESIGN_V3)
        or combined_separation_v3.get("ga_coordinate_only_sha256")
        != sha256_file(GA_MAGNETIC_COORDINATES_V3)
        or combined_separation_v3.get("correlation_range_km") != 75.0
        or combined_separation_v3.get("ga_actual_representative_independent_count")
        != 218
        or combined_separation_v3.get("usgs_conservative_bbox_independent_count")
        != 14
        or combined_separation_v3.get("combined_independent_test_count") != 232
        or combined_separation_v3.get("required_independent_test_count") != 223
        or combined_separation_v3.get("cluster_count_gate_passed") is not True
        or combined_separation_v3.get("response_variables_requested_for_geometry")
        != 0
        or combined_separation_v3.get("test_responses_interpreted") != 0
        or combined_separation_v3.get("test_unseal_count") != 0
    ):
        errors.append("combined-magnetic-provider-separation-v3")
    contract_passed = not errors
    cluster_power_passed = (
        contract_passed
        and combined_separation_v3["cluster_count_gate_passed"]
    )
    return {
        "errors": errors,
        "gates": {
            "observation_contract": gate(
                "passed" if contract_passed else "blocked",
                (
                    "Mountain Pass line/height/IGRF-diurnal contract is paired with "
                    "a provenance-backed training-only MagIC NRM prior (5905 complete "
                    "vectors from 21 contributions; magnitude units kept separate); "
                    "western Arkansas independently confirms line/flight, height, "
                    "base-station, correction and vector-field channels"
                    if contract_passed
                    else "magnetic evidence failure: " + ", ".join(errors)
                ),
            ),
            "clusters": gate(
                "passed" if cluster_power_passed else "blocked",
                "GA training-only provider surveys set a conservative 75-km range; "
                "exact coordinate-only representatives retain 218 GA surveys after "
                "training separation and pairwise conflicts, and 14 conservative "
                "USGS parent releases raise the sealed total to 232 independent "
                "clusters versus 223 required",
            ),
            "power": gate(
                "passed" if cluster_power_passed else "blocked",
                "the frozen all-metric requirement is 223 independent test clusters; "
                "the exact cross-provider separation supplies 232 (218 GA + 14 "
                "USGS), leaving a nine-cluster margin without reading test responses",
            ),
            "dimensionality": gate(
                "passed" if contract_passed else "blocked",
                (
                    "training-only regional detrending, 1.5-km residual range, "
                    "124 eligible flight-line spectra, height sensitivity and "
                    "5905-vector remanence prior select mandatory 3-D vector magnetization"
                    if contract_passed
                    else "magnetic dimensionality evidence failure"
                ),
            ),
        },
    }


def audit_selected_east_river_tem() -> dict[str, Any]:
    datasets = json.loads(DATASETS.read_text(encoding="utf-8"))
    selected = datasets["methods"]["tem"].get("backup_external", {})
    if selected.get("selection_status") != "selected_and_locally_frozen":
        raise RuntimeError("selected East River TEM backup is not frozen")
    required = (
        EAST_RIVER_MANIFEST,
        EAST_RIVER_SPLIT,
        EAST_RIVER_CONTRACT,
        EAST_RIVER_DIAGNOSTICS,
        TEM_CONSORTIUM_MANIFEST,
        TEM_CONSORTIUM_SPLIT,
        TEM_CONSORTIUM_CONTRACT,
        TEM_CONSORTIUM_DIAGNOSTICS,
        MARICOPA_MANIFEST,
        MARICOPA_SPLIT,
        MARICOPA_CONTRACT,
        MARICOPA_DIAGNOSTICS,
        GA_AEM_CATALOG_MANIFEST,
        GA_AEM_DESIGN,
        GA_AEM_PROBE_MANIFEST,
        GA_AEM_PROBE_INVENTORY,
        GA_AEM_PROBE_CONTRACT,
        GA_AEM_MULTISYSTEM_MANIFEST,
        GA_AEM_MULTISYSTEM_SELECTION,
        GA_AEM_MULTISYSTEM_INVENTORY,
        GA_AEM_MULTISYSTEM_CONTRACT,
        GA_AEM_MULTISYSTEM_SPLIT,
        GA_AEM_MULTISYSTEM_DIAGNOSTICS,
        USGS_AEM_EXPANSION_DESIGN,
        USGS_AEM_SCHEMA_AUDIT,
        USGS_AEM_RESPONSE_AUDIT,
        USGS_TEMPEST_2022_AUDIT,
        USGS_FLOATEM_TRAINING_DESIGN_POWER,
    )
    if any(not path.is_file() for path in required):
        raise RuntimeError("East River TEM evidence chain is incomplete")
    manifest = json.loads(EAST_RIVER_MANIFEST.read_text(encoding="utf-8"))
    split = json.loads(EAST_RIVER_SPLIT.read_text(encoding="utf-8"))
    contract = json.loads(EAST_RIVER_CONTRACT.read_text(encoding="utf-8"))
    diagnostic = json.loads(EAST_RIVER_DIAGNOSTICS.read_text(encoding="utf-8"))
    consortium_manifest = json.loads(TEM_CONSORTIUM_MANIFEST.read_text(encoding="utf-8"))
    consortium_split = json.loads(TEM_CONSORTIUM_SPLIT.read_text(encoding="utf-8"))
    consortium_contract = json.loads(
        TEM_CONSORTIUM_CONTRACT.read_text(encoding="utf-8")
    )
    consortium_diagnostic = json.loads(
        TEM_CONSORTIUM_DIAGNOSTICS.read_text(encoding="utf-8")
    )
    maricopa_manifest = json.loads(MARICOPA_MANIFEST.read_text(encoding="utf-8"))
    maricopa_split = json.loads(MARICOPA_SPLIT.read_text(encoding="utf-8"))
    maricopa_contract = json.loads(MARICOPA_CONTRACT.read_text(encoding="utf-8"))
    maricopa_diagnostic = json.loads(MARICOPA_DIAGNOSTICS.read_text(encoding="utf-8"))
    ga_aem_catalog = json.loads(GA_AEM_CATALOG_MANIFEST.read_text(encoding="utf-8"))
    ga_aem_design = json.loads(GA_AEM_DESIGN.read_text(encoding="utf-8"))
    ga_aem_probe = json.loads(GA_AEM_PROBE_MANIFEST.read_text(encoding="utf-8"))
    ga_aem_inventory = json.loads(GA_AEM_PROBE_INVENTORY.read_text(encoding="utf-8"))
    ga_aem_contract = json.loads(GA_AEM_PROBE_CONTRACT.read_text(encoding="utf-8"))
    ga_aem_multisystem_manifest = json.loads(
        GA_AEM_MULTISYSTEM_MANIFEST.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_inventory = json.loads(
        GA_AEM_MULTISYSTEM_INVENTORY.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_contract = json.loads(
        GA_AEM_MULTISYSTEM_CONTRACT.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_split = json.loads(
        GA_AEM_MULTISYSTEM_SPLIT.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_diagnostics = json.loads(
        GA_AEM_MULTISYSTEM_DIAGNOSTICS.read_text(encoding="utf-8")
    )
    usgs_aem_expansion = json.loads(
        USGS_AEM_EXPANSION_DESIGN.read_text(encoding="utf-8")
    )
    usgs_aem_schema = json.loads(USGS_AEM_SCHEMA_AUDIT.read_text(encoding="utf-8"))
    usgs_aem_response = json.loads(
        USGS_AEM_RESPONSE_AUDIT.read_text(encoding="utf-8")
    )
    usgs_tempest_2022 = json.loads(
        USGS_TEMPEST_2022_AUDIT.read_text(encoding="utf-8")
    )
    usgs_floatem = json.loads(
        USGS_FLOATEM_TRAINING_DESIGN_POWER.read_text(encoding="utf-8")
    )
    usgs_aem_2026 = json.loads(
        USGS_AEM_2026_METADATA_AUDIT.read_text(encoding="utf-8")
    )
    errors = []
    if (
        manifest.get("schema_version") != "wp8-east-river-aem-raw-manifest-v1"
        or manifest.get("member_count") != 10
        or len(manifest.get("members", [])) != 10
        or manifest.get("observation_response_interpreted") is not False
    ):
        errors.append("raw-manifest")
    for member in manifest.get("members", []):
        path = EAST_RIVER_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"raw-member:{member['name']}")
            break
    if (
        split.get("schema_version") != "wp8-east-river-aem-design-split-v1"
        or split.get("observation_response_values_parsed") is not False
        or split.get("candidate_500m_cell_counts")
        != {"train": 502, "buffer": 380, "calibration": 267, "test": 262}
    ):
        errors.append("design-split")
    report = EAST_RIVER_RAW / contract.get("report", {}).get("path", "")
    if (
        contract.get("schema_version")
        != "wp8-east-river-aem-contract-readiness-v1"
        or contract.get("passed") is not True
        or contract.get("raw_manifest_sha256") != sha256_file(EAST_RIVER_MANIFEST)
        or contract.get("response_values_interpreted") is not False
        or not report.is_file()
        or contract.get("report", {}).get("sha256") != sha256_file(report)
        or contract.get("observation_contract", {}).get("time_gate_count") != 52
        or contract.get("observation_contract", {}).get(
            "per_observation_standard_deviation"
        )
        is not True
    ):
        errors.append("observation-contract")
    if (
        diagnostic.get("schema_version")
        != "wp8-east-river-aem-train-diagnostics-v1"
        or diagnostic.get("split_sha256") != sha256_file(EAST_RIVER_SPLIT)
        or diagnostic.get("contract_sha256") != sha256_file(EAST_RIVER_CONTRACT)
        or diagnostic.get("training_rows_interpreted") != 23418
        or diagnostic.get("buffer_rows_interpreted") != 0
        or diagnostic.get("calibration_rows_interpreted") != 0
        or diagnostic.get("test_rows_interpreted") != 0
        or diagnostic.get("conservative_spatial_correlation_range_m") != 7250.0
        or diagnostic.get("correlation_adjusted_test_cluster_upper_bound") != 2
        or diagnostic.get("cluster_gate_passed") is not False
        or diagnostic.get("power_gate_passed") is not False
        or diagnostic.get("dimensionality", {}).get("selected") != "3-D"
    ):
        errors.append("training-diagnostics")
    if (
        consortium_manifest.get("schema_version")
        != "wp8-tem-aem-consortium-raw-manifest-v1"
        or consortium_manifest.get("member_count") != 14
        or consortium_manifest.get("total_bytes") != 701274624
        or consortium_manifest.get("observation_response_interpreted") is not False
    ):
        errors.append("consortium-manifest")
    for survey in consortium_manifest.get("surveys", []):
        for member in survey.get("members", []):
            path = TEM_CONSORTIUM_RAW / member["path"]
            if (
                not path.is_file()
                or path.stat().st_size != member["bytes"]
                or sha256_file(path) != member["sha256"]
            ):
                errors.append(f"consortium-member:{member['name']}")
                break
    if (
        consortium_split.get("schema_version")
        != "wp8-tem-aem-consortium-design-split-v1"
        or consortium_split.get("raw_manifest_sha256")
        != sha256_file(TEM_CONSORTIUM_MANIFEST)
        or consortium_split.get("observation_response_values_parsed") is not False
        or consortium_split.get("combined_candidate_500m_cell_counts", {}).get("test")
        != 1665
    ):
        errors.append("consortium-split")
    hualapai_report = TEM_CONSORTIUM_RAW / consortium_contract.get("surveys", {}).get(
        "hualapai", {}
    ).get("report_path", "")
    if (
        consortium_contract.get("schema_version")
        != "wp8-tem-aem-consortium-contract-readiness-v1"
        or consortium_contract.get("raw_manifest_sha256")
        != sha256_file(TEM_CONSORTIUM_MANIFEST)
        or consortium_contract.get("surveys", {}).get("hualapai", {}).get("passed")
        is not True
        or consortium_contract.get("surveys", {}).get("yellowstone", {}).get("passed")
        is not False
        or consortium_contract.get("sealed_response_values_interpreted") is not False
        or not hualapai_report.is_file()
        or consortium_contract.get("surveys", {})
        .get("hualapai", {})
        .get("report_sha256")
        != sha256_file(hualapai_report)
    ):
        errors.append("consortium-contract")
    if (
        consortium_diagnostic.get("schema_version")
        != "wp8-tem-aem-consortium-train-diagnostics-v1"
        or consortium_diagnostic.get("raw_manifest_sha256")
        != sha256_file(TEM_CONSORTIUM_MANIFEST)
        or consortium_diagnostic.get("split_sha256")
        != sha256_file(TEM_CONSORTIUM_SPLIT)
        or consortium_diagnostic.get("sealed_response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or consortium_diagnostic.get("surveys", {})
        .get("hualapai", {})
        .get("correlation_adjusted_test_cluster_upper_bound")
        != 4
        or consortium_diagnostic.get("surveys", {})
        .get("yellowstone", {})
        .get("correlation_adjusted_test_cluster_upper_bound")
        != 3
    ):
        errors.append("consortium-training-diagnostics")
    if (
        maricopa_manifest.get("schema_version")
        != "wp8-maricopa-aem-raw-manifest-v1"
        or maricopa_manifest.get("member_count") != 3
        or maricopa_manifest.get("total_bytes") != 711321496
        or maricopa_manifest.get("observation_response_interpreted") is not False
    ):
        errors.append("maricopa-manifest")
    for member in maricopa_manifest.get("members", []):
        path = MARICOPA_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"maricopa-member:{member['name']}")
            break
    if (
        maricopa_split.get("schema_version") != "wp8-maricopa-aem-design-split-v1"
        or maricopa_split.get("raw_manifest_sha256") != sha256_file(MARICOPA_MANIFEST)
        or maricopa_split.get("observation_response_values_parsed") is not False
        or maricopa_split.get("candidate_500m_cell_counts", {}).get("test") != 246
        or maricopa_contract.get("schema_version")
        != "wp8-maricopa-aem-contract-readiness-v1"
        or maricopa_contract.get("passed") is not True
        or maricopa_contract.get("raw_manifest_sha256")
        != sha256_file(MARICOPA_MANIFEST)
        or maricopa_contract.get("observation_response_values_parsed") is not False
        or maricopa_diagnostic.get("schema_version")
        != "wp8-maricopa-aem-train-diagnostics-v1"
        or maricopa_diagnostic.get("split_sha256") != sha256_file(MARICOPA_SPLIT)
        or maricopa_diagnostic.get("contract_sha256")
        != sha256_file(MARICOPA_CONTRACT)
        or maricopa_diagnostic.get("sealed_response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or maricopa_diagnostic.get("conservative_spatial_correlation_range_m")
        != 8750.0
        or maricopa_diagnostic.get("correlation_adjusted_test_cluster_upper_bound")
        != 1
    ):
        errors.append("maricopa-evidence")
    for member in ga_aem_catalog.get("members", []):
        path = GA_AEM_CATALOG_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"ga-aem-catalog-member:{member['path']}")
            break
    for member in ga_aem_probe.get("members", []):
        path = GA_AEM_PROBE_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"ga-aem-probe-member:{member['path']}")
            break
    for member in ga_aem_multisystem_manifest.get("members", []):
        path = GA_AEM_MULTISYSTEM_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"ga-aem-multisystem-member:{member['path']}")
            break
    if (
        ga_aem_catalog.get("schema_version")
        != "wp8-geoscience-australia-aem-catalog-freeze-v1"
        or ga_aem_catalog.get("feature_count") != 72
        or ga_aem_catalog.get("aem_response_values_interpreted") != 0
        or ga_aem_design.get("schema_version")
        != "wp8-geoscience-australia-aem-design-v1"
        or ga_aem_design.get("catalogue_manifest_sha256")
        != sha256_file(GA_AEM_CATALOG_MANIFEST)
        or ga_aem_design.get("eligible_open_license_product_count") != 71
        or ga_aem_design.get("unique_survey_count") != 40
        or ga_aem_design.get("partition_counts", {}).get("test") != 394
        or ga_aem_design.get("design_power_gate_possible") is not True
        or ga_aem_design.get("test_unseal_count") != 0
        or ga_aem_probe.get("schema_version")
        != "wp8-geoscience-australia-aem-training-probe-v1"
        or ga_aem_probe.get("covered_design_roles") != ["train"]
        or ga_aem_probe.get("test_unseal_count") != 0
        or ga_aem_inventory.get("raw_manifest_sha256")
        != sha256_file(GA_AEM_PROBE_MANIFEST)
        or ga_aem_inventory.get("member_payloads_read") != 0
        or ga_aem_contract.get("schema_version")
        != "wp8-geoscience-australia-aem-training-probe-contract-v1"
        or ga_aem_contract.get("raw_manifest_sha256")
        != sha256_file(GA_AEM_PROBE_MANIFEST)
        or ga_aem_contract.get("inventory_sha256")
        != sha256_file(GA_AEM_PROBE_INVENTORY)
        or ga_aem_contract.get("located_data", {}).get("row_count") != 442601
        or ga_aem_contract.get("located_data", {}).get("unique_line_count") != 269
        or ga_aem_contract.get("maximum_training_range_km") != 1.536
        or ga_aem_contract.get("exact_gate_center_times_present") is not True
        or ga_aem_contract.get("formal_contract_ready") is not False
        or ga_aem_contract.get("test_unseal_count") != 0
        or ga_aem_multisystem_manifest.get("sample_sha256")
        != sha256_file(GA_AEM_MULTISYSTEM_SELECTION)
        or ga_aem_multisystem_manifest.get("total_bytes") != 921757368
        or ga_aem_multisystem_manifest.get("test_unseal_count") != 0
        or ga_aem_multisystem_inventory.get("selection_sha256")
        != sha256_file(GA_AEM_MULTISYSTEM_SELECTION)
        or ga_aem_multisystem_inventory.get("observation_payload_members_opened") != 0
        or ga_aem_multisystem_inventory.get("response_values_interpreted") != 0
        or ga_aem_multisystem_contract.get("inventory_sha256")
        != sha256_file(GA_AEM_MULTISYSTEM_INVENTORY)
        or ga_aem_multisystem_contract.get("skytem_contract_ready") is not True
        or ga_aem_multisystem_contract.get("vtem_contract_ready") is not False
        or ga_aem_multisystem_contract.get("test_unseal_count") != 0
        or ga_aem_multisystem_split.get("partition_counts")
        != {"train": 523, "buffer": 511, "calibration": 170, "test": 418}
        or ga_aem_multisystem_split.get(
            "minimum_nonbuffer_cross_role_center_distance_km"
        ) != 87.61
        or ga_aem_multisystem_split.get("design_power_gate_possible") is not True
        or ga_aem_multisystem_split.get("test_unseal_count") != 0
        or ga_aem_multisystem_diagnostics.get("manifest_sha256")
        != sha256_file(GA_AEM_MULTISYSTEM_MANIFEST)
        or ga_aem_multisystem_diagnostics.get("split_sha256")
        != sha256_file(GA_AEM_MULTISYSTEM_SPLIT)
        or ga_aem_multisystem_diagnostics.get("contract_sha256")
        != sha256_file(GA_AEM_MULTISYSTEM_CONTRACT)
        or ga_aem_multisystem_diagnostics.get("sealed_response_rows_interpreted")
        != {"buffer": 0, "calibration": 0, "test": 0}
        or ga_aem_multisystem_diagnostics.get("test_unseal_count") != 0
        or ga_aem_multisystem_diagnostics.get(
            "formal_national_correlation_gate_passes"
        ) is not False
    ):
        errors.append("ga-national-aem-evidence")
    if (
        usgs_aem_expansion.get("schema_version")
        != "wp8-usgs-aem-training-expansion-design-v1"
        or usgs_aem_expansion.get("training_survey_count") != 5
        or usgs_aem_expansion.get("selection_frozen_before_payload_access")
        is not True
        or usgs_aem_expansion.get("usgs_calibration_surveys") != []
        or usgs_aem_expansion.get("usgs_test_surveys") != []
        or usgs_aem_expansion.get("test_unseal_count") != 0
        or usgs_aem_schema.get("schema_version")
        != "wp8-usgs-aem-training-schema-audit-v1"
        or usgs_aem_schema.get("design_sha256")
        != sha256_file(USGS_AEM_EXPANSION_DESIGN)
        or usgs_aem_schema.get("completed_training_file_count", 0) < 4
        or usgs_aem_schema.get("response_values_interpreted") != 0
        or usgs_aem_schema.get("test_unseal_count") != 0
        or usgs_aem_response.get("schema_version")
        != "wp8-usgs-aem-training-response-diagnostics-v1"
        or usgs_aem_response.get("design_sha256")
        != sha256_file(USGS_AEM_EXPANSION_DESIGN)
        or usgs_aem_response.get("completed_netcdf_training_survey_count", 0) < 3
        or usgs_aem_response.get("training_response_values_interpreted", 0)
        < 9_500_000
        or usgs_aem_response.get("paired_crps_effect_size_available") is not False
        or usgs_aem_response.get("power_gate_passed") is not False
        or usgs_aem_response.get("calibration_responses_interpreted") != 0
        or usgs_aem_response.get("test_responses_interpreted") != 0
        or usgs_aem_response.get("test_unseal_count") != 0
        or usgs_tempest_2022.get("schema_version")
        != "wp8-usgs-tempest-2022-training-diagnostics-v1"
        or usgs_tempest_2022.get("design_sha256")
        != sha256_file(USGS_AEM_EXPANSION_DESIGN)
        or usgs_tempest_2022.get("system") != "TEMPEST"
        or usgs_tempest_2022.get("processed_rows") != 449501
        or usgs_tempest_2022.get("unique_lines") != 385
        or usgs_tempest_2022.get("valid_response_noise_pairs") != 13485030
        or usgs_tempest_2022.get(
            "formal_response_uncertainty_contract_ready"
        )
        is not True
        or usgs_tempest_2022.get("paired_crps_effect_size_available") is not False
        or usgs_tempest_2022.get("power_gate_passed") is not False
        or usgs_tempest_2022.get("test_responses_interpreted") != 0
        or usgs_tempest_2022.get("test_unseal_count") != 0
        or usgs_aem_2026.get("schema_version")
        != "wp8-usgs-aem-2026-unexposed-metadata-audit-v1"
        or usgs_aem_2026.get("response_payloads_downloaded") != 0
        or usgs_aem_2026.get("response_values_interpreted") != 0
        or usgs_aem_2026.get("test_unseal_count") != 0
        or usgs_aem_2026.get("combined_geometry", {}).get("raw_line_records")
        != 382
        or usgs_aem_2026.get("combined_geometry", {}).get(
            "frozen_training_only_correlation_range_km"
        )
        != 3.51
        or usgs_aem_2026.get("combined_geometry", {}).get(
            "effective_cluster_upper_bound"
        )
        != 44
        or usgs_aem_2026.get("combined_geometry", {}).get(
            "passes_cluster_gate"
        )
        is not False
        or usgs_aem_2026.get("decision") != "abort_before_response_payload"
    ):
        errors.append("usgs-aem-training-expansion")
    if (
        usgs_floatem.get("schema_version")
        != "wp8-usgs-floatem-training-design-power-v1"
        or not USGS_LOWER_DELAWARE_FLOATEM.is_file()
        or usgs_floatem.get("sealed_archive_sha256")
        != sha256_file(USGS_LOWER_DELAWARE_FLOATEM)
        or usgs_floatem.get("training_only_correlation", {}).get(
            "frozen_range_m"
        )
        != 325.0
        or usgs_floatem.get("training_only_power", {}).get(
            "paired_training_clusters"
        )
        != 130
        or usgs_floatem.get("training_only_power", {}).get(
            "required_paired_crps_clusters_conservative"
        )
        != 321
        or usgs_floatem.get("sealed_coordinate_inventory", {}).get(
            "unique_positions"
        )
        != 30669
        or usgs_floatem.get("sealed_coordinate_inventory", {}).get(
            "response_columns_interpreted"
        )
        != 0
        or usgs_floatem.get("sealed_packing", {}).get(
            "packed_position_count"
        )
        != 465
        or usgs_floatem.get("role_assignment", {}).get("test_count") != 321
        or usgs_floatem.get("wp8_0_cluster_gate_passes") is not True
        or usgs_floatem.get("wp8_0_power_gate_passes") is not True
        or usgs_floatem.get("sealed_response_values_interpreted") != 0
        or usgs_floatem.get("test_unseal_count") != 0
        or usgs_floatem.get("formal_test_result") is not None
    ):
        errors.append("usgs-floatem-training-design-power")
    if errors:
        raise RuntimeError("East River TEM evidence-chain failure: " + ", ".join(errors))
    return {
        "license_evidence": {
            "passed": True,
            "statement": "USGS data release 10.5066/P949ZCZ8 is CC0/public domain",
            "evidence_path": str(EAST_RIVER_MANIFEST),
            "evidence_sha256": sha256_file(EAST_RIVER_MANIFEST),
        },
        "gates": {
            "license": gate("passed", "USGS CC0 1.0 / U.S. public domain"),
            "integrity": gate(
                "passed",
                f"10 local SHA-256 members verified ({manifest['total_bytes']} bytes)",
            ),
            "observation_contract": gate(
                "passed",
                "VTEM ET full-waveform source/receiver geometry, current waveform, 52 gates, Z response and per-observation DATASTD verified",
            ),
            "clusters": gate(
                "passed",
                "training-only land/towed TEM freezes a 325-m range; the "
                "response-blind Lower Delaware FloaTEM archive has 30,669 "
                "unique positions, 465 strictly separated positions, and a "
                "frozen 321-position sealed test partition",
            ),
            "power": gate(
                "passed",
                "130 training-only buffered paired-CRPS clusters give a "
                "one-sided conservative requirement of 321 clusters at the "
                "10% target; exactly 321 sealed Lower Delaware test clusters "
                "are frozen with zero sealed response reads",
            ),
            "dimensionality": gate(
                "passed",
                "fixed early/mid/late training variograms reject independent 1-D sounding eligibility; mandatory 3-D path selected",
            ),
        },
    }


def audit_potential_paths() -> dict[str, Any]:
    if not POTENTIAL_PATH_READINESS.is_file():
        raise RuntimeError("potential-field path readiness evidence missing")
    payload = json.loads(POTENTIAL_PATH_READINESS.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "wp8-potential-path-readiness-v1":
        raise RuntimeError("potential-field path readiness schema mismatch")
    expected_entrypoints = {
        "gravity": "geodeepbayes.forward.gravity.GravityOperator",
        "magnetic": "geodeepbayes.forward.magnetic.MagneticOperator",
    }
    result = {}
    for method, entrypoint in expected_entrypoints.items():
        evidence = payload.get("methods", {}).get(method, {})
        errors = []
        implementation = evidence.get("implementation", {})
        if (
            implementation.get("entrypoint") != entrypoint
            or not implementation.get("dependency_versions")
            or "3-D" not in implementation.get("applicable_dimension", "")
        ):
            errors.append("solver-path")
        reference = evidence.get("independent_reference", {})
        reference_path = ROOT / reference.get("test_path", "")
        if (
            reference.get("passed") is not True
            or reference.get("pytest_exit_code") != 0
            or not reference_path.is_file()
            or reference.get("test_source_sha256") != sha256_file(reference_path)
            or "Geoana" not in reference.get("kind", "")
        ):
            errors.append("reference-path")
        resource = evidence.get("resource_measurement", {})
        records = resource.get("records", [])
        if (
            len(records) < 3
            or resource.get("passed") is not True
            or not all(row.get("finite") for row in records)
            or resource.get("timeout_seconds", 0)
            <= max(row.get("wall_time_seconds", float("inf")) for row in records)
            or resource.get("memory_limit_bytes", 0)
            <= max(row.get("peak_python_memory_bytes", float("inf")) for row in records)
        ):
            errors.append("resource-budget")
        if errors:
            raise RuntimeError(f"{method} evidence-chain failure: " + ", ".join(errors))
        result[method] = {
            "gates": {
                "solver": gate(
                    "passed",
                    f"versioned {entrypoint.rsplit('.', 1)[-1]} path frozen for "
                    f"{implementation['applicable_dimension']}",
                ),
                "independent_reference": gate(
                    "passed",
                    f"{reference['quantity']} matches an independent Geoana implementation; "
                    "derivative tests passed with protected source hash",
                ),
                "resource_budget": gate(
                    "passed",
                    f"three representative meshes measured; abort limits frozen at "
                    f"{resource['timeout_seconds']} s and {resource['memory_limit_bytes']} bytes",
                ),
            }
        }
    return result


def audit_static_paths() -> dict[str, Any]:
    if not STATIC_PATH_READINESS.is_file():
        raise RuntimeError("static path readiness evidence missing")
    payload = json.loads(STATIC_PATH_READINESS.read_text(encoding="utf-8"))
    if not KRAUSE_ERT_CONTRACT.is_file():
        raise RuntimeError("Krause ERT contract evidence missing")
    krause = json.loads(KRAUSE_ERT_CONTRACT.read_text(encoding="utf-8"))
    krause_ok = (
        krause.get("schema_version") == "wp8-usgs-krause-ert-contract-v1"
        and krause.get("license_gate_passes") is True
        and krause.get("abmn_local_geometry_present") is True
        and krause.get("electrode_gps_present") is True
        and krause.get("navd88_topography_present") is True
        and krause.get("measurement_count") == 13605
        and krause.get("profile_count") == 4
        and krause.get("reciprocal_configuration_group_count") == 0
        and krause.get("empirical_error_model_possible") is False
        and krause.get("direct_per_observation_standard_deviation_present") is False
        and krause.get("formal_cluster_power_gate_passes") is False
        and krause.get("test_unseal_count") == 0
    )
    if not krause_ok:
        raise RuntimeError("Krause ERT contract evidence drift")
    if not PO_RIVER_DC_DESIGN.is_file() or not PO_RIVER_DC_TRAINING.is_file():
        raise RuntimeError("Po River DC evidence missing")
    po_design = json.loads(PO_RIVER_DC_DESIGN.read_text(encoding="utf-8"))
    po_training = json.loads(PO_RIVER_DC_TRAINING.read_text(encoding="utf-8"))
    po_contract_ok = (
        po_design.get("schema_version") == "wp8-po-river-dc-streamer-design-v2"
        and po_design.get("access_right") == "open"
        and po_design.get("license") == "cc-by-4.0"
        and po_design.get("declared_observation_count") == 164724
        and po_design.get("remaining_test_population_sealed") is True
        and po_design.get("partition_counts", {}).get("quarantine_response_exposed")
        == 8
        and po_training.get("schema_version")
        == "wp8-po-river-dc-streamer-training-audit-v2"
        and po_training.get("design_sha256") == sha256_file(PO_RIVER_DC_DESIGN)
        and po_training.get("training_response_rows_interpreted") == 29892
        and po_training.get("per_observation_standard_deviation_present") is True
        and po_training.get("calibration_response_rows_interpreted") == 0
        and po_training.get("remaining_test_response_rows_interpreted") == 0
        and po_training.get("remaining_test_population_sealed") is True
        and po_training.get("correlation_separated_test_station_count") == 38
        and po_training.get("cluster_gate_passed") is False
        and po_training.get("power_gate_passed") is False
    )
    if not po_contract_ok:
        raise RuntimeError("Po River DC contract evidence drift")
    taiwan_eri = json.loads(TAIWAN_ERI_METADATA.read_text(encoding="utf-8"))
    taiwan_eri_ok = (
        taiwan_eri.get("schema_version") == "wp8-taiwan-eri-metadata-audit-v1"
        and taiwan_eri.get("license") == "CC-BY-4.0"
        and taiwan_eri.get("declared_profile_count") == 265
        and taiwan_eri.get("public_folder_count") == 532
        and taiwan_eri.get("public_file_count") == 4838
        and taiwan_eri.get("exact_unique_profile_centres") == 251
        and taiwan_eri.get("training_correlation_range_m") == 64
        and taiwan_eri.get("effective_spatial_clusters_at_training_range") == 246
        and taiwan_eri.get("required_test_clusters") == 223
        and taiwan_eri.get("cluster_count_gate_possible") is True
        and taiwan_eri.get("paired_crps_effect_size_available") is False
        and taiwan_eri.get("power_gate_passed") is False
        and taiwan_eri.get("response_payloads_downloaded") == 0
        and taiwan_eri.get("response_values_interpreted") == 0
        and taiwan_eri.get("test_unseal_count") == 0
    )
    if not taiwan_eri_ok:
        raise RuntimeError("Taiwan ERI metadata evidence drift")
    taiwan_design = json.loads(TAIWAN_ERI_DESIGN.read_text(encoding="utf-8"))
    taiwan_power = json.loads(TAIWAN_ERI_POWER.read_text(encoding="utf-8"))
    taiwan_power_ok = (
        taiwan_design.get("schema_version") == "wp8-taiwan-eri-design-v1"
        and taiwan_design.get("metadata_audit_sha256")
        == sha256_file(TAIWAN_ERI_METADATA)
        and taiwan_design.get("selection_frozen_before_response_payload_access")
        is True
        and taiwan_design.get("correlation_range_m") == 64.0
        and taiwan_design.get("exact_unique_profile_centres") == 251
        and taiwan_design.get("component_count") == 246
        and taiwan_design.get("role_counts") == {"training": 23, "test": 223}
        and taiwan_design.get("design_cluster_gate_passes") is True
        and taiwan_design.get("response_payloads_downloaded") == 0
        and taiwan_design.get("response_values_interpreted") == 0
        and taiwan_design.get("test_unseal_count") == 0
        and taiwan_power.get("schema_version")
        == "wp8-taiwan-eri-training-power-v1"
        and taiwan_power.get("design_sha256") == sha256_file(TAIWAN_ERI_DESIGN)
        and taiwan_power.get("training_only") is True
        and taiwan_power.get("observation_contract", {}).get(
            "training_component_count"
        )
        == 23
        and taiwan_power.get("observation_contract", {}).get(
            "training_observation_count"
        )
        == 26356
        and taiwan_power.get("observation_contract", {}).get(
            "per_observation_repeat_error_present"
        )
        is True
        and taiwan_power.get("paired_training_components") == 23
        and taiwan_power.get("required_paired_crps_clusters_conservative") == 99
        and taiwan_power.get("required_clusters_all_metrics") == 223
        and taiwan_power.get("available_correlation_adjusted_test_clusters") == 223
        and taiwan_power.get("wp8_0_power_gate_passes") is True
        and taiwan_power.get("test_files_downloaded") == 0
        and taiwan_power.get("test_responses_interpreted") == 0
        and taiwan_power.get("test_unseal_count") == 0
        and taiwan_power.get("formal_test_result") is None
    )
    if not taiwan_power_ok:
        raise RuntimeError("Taiwan ERI design/power evidence drift")
    if payload.get("schema_version") != "wp8-static-path-readiness-v1":
        raise RuntimeError("static path readiness schema mismatch")
    expected = {
        "dc": ("geodeepbayes.forward.static.DCOperator", "3-D"),
        "sip_fdip": (
            "geodeepbayes.forward.static.ColeCole2DOperator",
            "2-D profile",
        ),
    }
    result = {}
    dc_geometry = json.loads(LITTLE_COLORADO_DC_GEOMETRY.read_text(encoding="utf-8"))
    dc_geometry_ok = (
        dc_geometry.get("schema_version") == "wp8-little-colorado-dc-geometry-v1"
        and dc_geometry.get("resistance_or_apparent_resistivity_values_parsed") is False
        and dc_geometry.get("profiles_requiring_3d") == ["MB4"]
        and dc_geometry.get("dimensionality", {}).get("selected") == "3-D"
        and dc_geometry.get("dimensionality", {}).get("passed") is True
    )
    for profile in dc_geometry.get("profiles", {}).values():
        path = ROOT / profile.get("archive_path", "")
        dc_geometry_ok = dc_geometry_ok and (
            path.is_file()
            and path.stat().st_size == profile.get("archive_bytes")
            and sha256_file(path) == profile.get("archive_sha256")
        )
    sip_geometry = json.loads(SERPENTINITE_SIP_GEOMETRY.read_text(encoding="utf-8"))
    sip_archive = ROOT / sip_geometry.get("archive_path", "")
    sip_geometry_ok = (
        sip_geometry.get("schema_version") == "wp8-serpentinite-sip-geometry-v1"
        and sip_geometry.get(
            "apparent_resistivity_chargeability_or_spectral_values_parsed"
        )
        is False
        and sip_archive.is_file()
        and sip_archive.stat().st_size == sip_geometry.get("archive_bytes")
        and sha256_file(sip_archive) == sip_geometry.get("archive_sha256")
        and sip_geometry.get("dimensionality", {}).get("selected") == "2-D profile"
        and sip_geometry.get("dimensionality", {}).get("passed") is True
        and sip_geometry.get("available_solver_compatible") is True
    )
    guidel_training = json.loads(GUIDEL_SIP_TRAINING.read_text(encoding="utf-8"))
    guidel_repeatability = json.loads(
        GUIDEL_SIP_REPEATABILITY.read_text(encoding="utf-8")
    )
    martin2020 = json.loads(
        MARTIN2020_FIELD_SIP_TRAINING.read_text(encoding="utf-8")
    )
    martin2020_archive = ROOT / martin2020.get("source", {}).get(
        "archive_path", ""
    )
    martin2020_ok = (
        martin2020.get("schema_version")
        == "wp8-zenodo-martin2020-field-sip-training-audit-v1"
        and martin2020.get("partition") == "permanently-training-only"
        and martin2020_archive.is_file()
        and martin2020_archive.stat().st_size
        == martin2020.get("source", {}).get("archive_bytes")
        and sha256_file(martin2020_archive)
        == martin2020.get("source", {}).get("archive_sha256")
        and martin2020.get("profiles", {}).get("IP1", {}).get(
            "quadrupole_count"
        )
        == 522
        and martin2020.get("profiles", {}).get("IP1", {}).get(
            "frequency_count"
        )
        == 14
        and martin2020.get("profiles", {}).get("IP5", {}).get(
            "quadrupole_count"
        )
        == 535
        and martin2020.get("profiles", {}).get("IP5", {}).get(
            "frequency_count"
        )
        == 11
        and martin2020.get("totals", {}).get("complex_observations") == 13_193
        and martin2020.get("totals", {}).get(
            "unique_quadrupole_midpoints_upper_bound"
        )
        == 196
        and martin2020.get("formal_gate_assessment", {}).get(
            "minimum_independent_test_clusters"
        )
        == 223
        and martin2020.get("formal_gate_assessment", {}).get(
            "cluster_gate_passes"
        )
        is False
        and martin2020.get("formal_gate_assessment", {}).get(
            "power_gate_passes"
        )
        is False
        and martin2020.get("formal_test_responses_opened") == 0
        and martin2020.get("test_unseal_count") == 0
        and martin2020.get("formal_test_result") is None
    )
    if not martin2020_ok:
        raise RuntimeError("Martin 2020 field SIP training evidence drift")
    sip_public = json.loads(
        SIP_FDIP_PUBLIC_DATA_AUDIT.read_text(encoding="utf-8")
    )
    sip_public_candidates = {
        row.get("id"): row for row in sip_public.get("candidates", [])
    }
    sip_debye = sip_public_candidates.get("github-sip-debye-net-2026", {})
    sip_debye_data = ROOT / sip_debye.get("dataset_path", "")
    vineyard = json.loads(VINEYARD_FIELD_SIP_AUDIT.read_text(encoding="utf-8"))
    vineyard_archive = ROOT / vineyard.get("archive", {}).get("path", "")
    streambed = json.loads(
        STREAMBED_FIELD_SIP_AUDIT.read_text(encoding="utf-8")
    )
    mendeley_heavy = json.loads(
        MENDELEY_HEAVY_METAL_SIP_CONTRACT.read_text(encoding="utf-8")
    )
    bc_aris_catalogue = json.loads(
        BC_ARIS_IP_CATALOGUE.read_text(encoding="utf-8")
    )
    bc_aris_split = json.loads(
        BC_ARIS_IP_DISCOVERY_SPLIT.read_text(encoding="utf-8")
    )
    bc_aris_training = json.loads(
        BC_ARIS_IP_TRAINING_CLASSIFICATION.read_text(encoding="utf-8")
    )
    streambed_archives = [
        ROOT / row.get("archive_path", "") for row in streambed.get("sites", [])
    ]
    if not (
        sip_public.get("schema_version")
        == "wp8-sip-fdip-public-data-audit-v1"
        and sip_public.get("formal_test_endpoints_inspected") is False
        and sip_debye.get("commit")
        == "eed826e823dd27959b136cd50c768db58c091f38"
        and sip_debye_data.is_file()
        and sip_debye.get("dataset_bytes") == sip_debye_data.stat().st_size
        and sip_debye.get("dataset_sha256") == sha256_file(sip_debye_data)
        and sip_debye.get("complex_spectra") == 140
        and sip_debye.get("frequencies_per_spectrum") == 19
        and sip_debye.get("complex_uncertainty_per_observation") is True
        and sip_debye.get("canadian_malartic_field_spectra") == 26
        and sip_debye.get("field_coordinate_or_abmn_geometry") is False
        and sip_debye.get("independent_spatial_cluster_count_derivable")
        is False
        and vineyard.get("schema_version")
        == "wp8-zenodo-vineyard-field-sip-audit-v1"
        and vineyard_archive.is_file()
        and vineyard.get("archive", {}).get("bytes")
        == vineyard_archive.stat().st_size
        and vineyard.get("archive", {}).get("sha256")
        == sha256_file(vineyard_archive)
        and vineyard.get("raw_data", {}).get(
            "independent_spatial_cluster_upper_bound"
        )
        == 2
        and vineyard.get("gate_assessment", {}).get("observation_pass") is True
        and vineyard.get("gate_assessment", {}).get("clusters_pass") is False
        and vineyard.get("gate_assessment", {}).get("power_pass") is False
        and streambed.get("schema_version")
        == "wp8-zenodo-streambed-sip-audit-v1"
        and streambed.get("license") == "cc-by-4.0"
        and streambed.get("formal_test_responses_opened") == 0
        and streambed.get("test_unseal_count") == 0
        and len(streambed.get("sites", [])) == 2
        and all(path.is_file() for path in streambed_archives)
        and all(
            row.get("archive_sha256") == sha256_file(path)
            for row, path in zip(streambed.get("sites", []), streambed_archives)
        )
        and streambed.get("totals", {}).get("profiles") == 10
        and streambed.get("totals", {}).get("coordinates") == 320
        and streambed.get("totals", {}).get("response_rows") == 40_800
        and streambed.get("totals", {}).get(
            "independent_spatial_cluster_upper_bound"
        )
        == 2
        and streambed.get("gate_assessment", {}).get("cluster_gate_passes")
        is False
        and streambed.get("gate_assessment", {}).get("power_gate_passes")
        is False
        and mendeley_heavy.get("schema_version")
        == "wp8-mendeley-heavy-metal-sip-training-contract-audit-v1"
        and mendeley_heavy.get("scope") == "permanently-training-only"
        and mendeley_heavy.get("provider_inventory_sha256")
        == "58316f9a2862b22da616463e73f1c37ff5fae99503ec1d8164b6a554d22c2041"
        and mendeley_heavy.get("archive_contract_integrity_passed") is True
        and mendeley_heavy.get("formal_status") == "blocked"
        and mendeley_heavy.get("formal_field_gate_passes") is False
        and mendeley_heavy.get("field_validation_eligible") is False
        and bc_aris_catalogue.get("schema_version")
        == "wp8-bc-aris-ip-digital-catalogue-v1"
        and bc_aris_catalogue.get("query", {}).get("response_payloads_opened")
        is False
        and bc_aris_catalogue.get("catalogue_counts", {}).get(
            "reported_records"
        )
        == 103
        and bc_aris_catalogue.get("catalogue_counts", {}).get(
            "parsed_unique_records"
        )
        == 103
        and bc_aris_catalogue.get("catalogue_counts", {}).get(
            "records_with_archive_endpoint"
        )
        == 102
        and bc_aris_catalogue.get("catalogue_counts", {}).get(
            "head_verified_archive_endpoints"
        )
        == 104
        and bc_aris_catalogue.get("gate_assessment", {}).get(
            "formal_clusters_added"
        )
        == 0
        and bc_aris_catalogue.get("gate_assessment", {}).get(
            "formal_gate_changed"
        )
        is False
        and bc_aris_split.get("schema_version")
        == "wp8-bc-aris-ip-discovery-split-v1"
        and bc_aris_split.get("catalogue_sha256")
        == sha256_file(BC_ARIS_IP_CATALOGUE)
        and bc_aris_split.get("role_counts")
        == {"training-discovery": 30, "sealed-candidate-test": 73}
        and bc_aris_split.get("formal_status", {}).get(
            "sealed_candidate_test_responses_opened"
        )
        == 0
        and bc_aris_split.get("formal_status", {}).get(
            "formal_clusters_added"
        )
        == 0
        and all(
            row.get("response_opened") is False
            and row.get("archive_members_listed") is False
            for row in bc_aris_split.get("assignments", [])
            if row.get("role") == "sealed-candidate-test"
        )
        and bc_aris_training.get("schema_version")
        == "wp8-bc-aris-ip-training-classification-v1"
        and bc_aris_training.get("audit_scope", {}).get(
            "training_archives_opened"
        )
        == 21
        and bc_aris_training.get("audit_scope", {}).get(
            "training_reports_classified"
        )
        == 30
        and bc_aris_training.get("audit_scope", {}).get(
            "training_reports_classified_from_official_pdf_only"
        )
        == 9
        and bc_aris_training.get("audit_scope", {}).get(
            "sealed_candidate_test_responses_opened"
        )
        == 0
        and len(
            bc_aris_training.get("classification", {}).get(
                "explicit_time_domain_ip_reports", []
            )
        )
        == 20
        and bc_aris_training.get("classification", {}).get(
            "qualifying_sip_fdip_reports"
        )
        == []
        and bc_aris_training.get("formal_status", {}).get(
            "formal_sip_fdip_clusters_added"
        )
        == 0
        and bc_aris_training.get("formal_status", {}).get(
            "formal_gate_changed"
        )
        is False
        and sip_public.get("conclusions", {}).get(
            "contract_complete_field_replacement_found"
        )
        is False
        and sip_public.get("conclusions", {}).get(
            "minimum_independent_test_clusters"
        )
        == 223
        and sip_public.get("conclusions", {}).get(
            "method_substitution_allowed"
        )
        is False
    ):
        raise RuntimeError("public SIP/FDIP search evidence drift")
    guidel_contract_ok = (
        guidel_training.get("schema_version")
        == "wp8-guidel-sip-training-diagnostics-v1"
        and guidel_training.get("partition") == "training-only"
        and guidel_training.get("raw_file_count") == 30
        and guidel_training.get("processing_contract", {}).get("abmn_quadrupoles")
        == 56
        and guidel_training.get("processing_contract", {}).get(
            "selected_frequency_count"
        )
        == 30
        and guidel_training.get("processing_contract", {}).get(
            "complex_observations_after_processing"
        )
        == 1680
        and guidel_training.get("geometry_contract", {}).get(
            "relative_geometry_reconstructable_without_interpolation"
        )
        is True
        and guidel_training.get("interpretation", {}).get(
            "frequency_to_quadrupole_key"
        )
        == "passed_training_only"
        and guidel_training.get("test_unseal_count") == 0
        and guidel_repeatability.get("schema_version")
        == "wp8-guidel-sip-repeatability-v1"
        and guidel_repeatability.get("partition") == "training-only"
        and guidel_repeatability.get(
            "adjacent_dipoles_frequency_ge_0_1_hz", {}
        ).get("complex_observations")
        == 364
        and guidel_repeatability.get("interpretation", {}).get(
            "repeat_based_uncertainty_contract"
        )
        == "passed_training_only"
        and guidel_repeatability.get("test_unseal_count") == 0
    )
    if not guidel_contract_ok:
        raise RuntimeError("Guidel SIP observation-contract evidence drift")
    for method, (entrypoint, dimension) in expected.items():
        evidence = payload.get("methods", {}).get(method, {})
        implementation = evidence.get("implementation", {})
        solver_ok = (
            implementation.get("entrypoint") == entrypoint
            and bool(implementation.get("dependency_versions"))
            and dimension in implementation.get("applicable_dimension", "")
        )
        dimension_mismatch = False
        reference = evidence.get("independent_reference", {})
        reference_path = ROOT / reference.get("test_path", "")
        reference_ok = (
            reference.get("passed") is True
            and reference.get("pytest_exit_code") == 0
            and reference_path.is_file()
            and reference.get("test_source_sha256") == sha256_file(reference_path)
        )
        resource = evidence.get("resource_measurement", {})
        resource_ok = (
            resource.get("passed") is True
            and len(resource.get("records", [])) == 3
            and all(row.get("finite") for row in resource.get("records", []))
            and resource.get("timeout_seconds", 0) > 0
            and resource.get("memory_limit_bytes", 0) > 0
        )
        result[method] = {
            "gates": {
                "solver": gate(
                    "passed" if solver_ok else "blocked",
                    f"version-frozen {dimension} implementation path"
                    if solver_ok
                    else (
                        "field geometry selects a dimension incompatible with the "
                        "frozen static implementation"
                        if dimension_mismatch
                        else "static solver evidence invalid"
                    ),
                ),
                "independent_reference": gate(
                    "passed" if reference_ok else "blocked",
                    reference.get("kind", "static independent reference invalid"),
                ),
                "resource_budget": gate(
                    "passed" if resource_ok else "blocked",
                    "three measured scales plus enforced timeout/memory abort limits"
                    if resource_ok
                    else "static resource evidence invalid",
                ),
            }
        }
        if method == "dc":
            result[method]["gates"]["observation_contract"] = gate(
                "passed",
                "Po River CC-BY-4.0 streamer data provide 164,724 ABMN apparent-"
                "resistivity observations with direct per-observation standard "
                "deviation; 29,892 frozen training rows were audited and the "
                "remaining test population is sealed after quarantining the one "
                "historical eight-station exposure block",
            )
            result[method]["gates"]["clusters"] = gate(
                "passed",
                "Taiwan ERI public coordinate workbooks provide 251 exact unique "
                "profile centres; the frozen Po River 64-m training correlation "
                "range leaves 246 response-blind spatial components, exceeding "
                "the required 223 while all response payloads remain unopened",
            )
            result[method]["gates"]["power"] = gate(
                "passed",
                "23 frozen Taiwan STG training components provide 26,356 "
                "observations; leave-one-component-out paired CRPS gives a "
                "conservative 99-cluster requirement, while coverage equivalence "
                "dominates at 223 and the sealed test contains exactly 223 "
                "correlation-adjusted components",
            )
            result[method]["gates"]["dimensionality"] = gate(
                "passed" if dc_geometry_ok else "blocked",
                (
                    "GPS-only PCA geometry finds MB4 crossline deviation far above "
                    "electrode spacing; mandatory 3-D nodal finite-volume path selected"
                    if dc_geometry_ok
                    else "Little Colorado DC geometry evidence invalid"
                ),
            )
        if method == "sip_fdip":
            result[method]["gates"]["observation_contract"] = gate(
                "passed",
                "Guidel training-only raw waveforms reconstruct 56 ABMN "
                "quadrupoles at 30 frequencies (1,680 complex observations); "
                "two recorded cycles provide repeat-based amplitude and phase "
                "uncertainty without opening calibration or test responses",
            )
            result[method]["gates"]["clusters"] = gate(
                "blocked",
                "Guidel supplies one site/date only; the Serpentinite and newly "
                "located Mendeley and Martin 2020 field candidates do not add "
                "223 independently auditable frequency-keyed profiles; Martin "
                "2020 has two colocated profiles and even its non-independent "
                "quadrupole-midpoint upper bound is only 196. The 2026 "
                "sip-debye-net release adds 26 Canadian Malartic field spectra "
                "with complex uncertainties, but no coordinates or ABMN geometry "
                "from which independent spatial clusters can be derived. The "
                "checksum-verified Zenodo vineyard release adds raw complex "
                "responses, ABMN geometry and repeat uncertainties, but its five "
                "campaign dates still cover only two independent spatial profiles. "
                "The newly audited CC-BY-4.0 streambed release adds 40,800 raw "
                "frequency-keyed rows, 320 electrode coordinates and repeat "
                "uncertainties across ten profiles, but those profiles belong to "
                "only two field sites. The response-blind BC ARIS query adds 103 "
                "public IP reports with 104 HEAD-verified digital archive "
                "endpoints (45.14 GB), but catalogue metadata does not distinguish "
                "TDIP from FDIP/SIP; all 30 frozen training reports have now been "
                "classified and none exposes a qualifying multi-frequency complex "
                "or phase response. The 73 candidate-test reports therefore remain "
                "sealed and contribute zero formal SIP/FDIP clusters",
            )
            result[method]["gates"]["power"] = gate(
                "blocked",
                "the observation contract is repaired, but no training-only "
                "paired-CRPS effect size and no 223 independent SIP/FDIP "
                "test clusters are available",
            )
            result[method]["gates"]["dimensionality"] = gate(
                "passed" if sip_geometry_ok else "blocked",
                (
                    "two 64-electrode field profiles require lateral 2-D structure; "
                    "outcome-blind GPS geometry diagnostic completed"
                    if sip_geometry_ok
                    else "Serpentinite SIP geometry evidence invalid"
                ),
            )
    return result


def audit_controlled_source_paths() -> dict[str, Any]:
    if not CONTROLLED_SOURCE_PATH_READINESS.is_file():
        raise RuntimeError("controlled-source path readiness evidence missing")
    payload = json.loads(CONTROLLED_SOURCE_PATH_READINESS.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "wp8-controlled-source-path-readiness-v1":
        raise RuntimeError("controlled-source path readiness schema mismatch")
    expected = {
        "csamt": "geodeepbayes.forward.controlled_source.CSAMTOperator",
        "wfem": "geodeepbayes.forward.controlled_source.WFEMOperator",
    }
    if not CSAMT_GEOMETRY.is_file():
        raise RuntimeError("CSAMT geometry evidence missing")
    if not MOUNT_ST_HELENS_CSAMT_CONTRACT.is_file():
        raise RuntimeError("Mount St. Helens CSAMT contract evidence missing")
    if not HUALAPAI_CSAMT_CONTRACT.is_file():
        raise RuntimeError("Hualapai CSAMT contract evidence missing")
    if not HUALAPAI_CSAMT_RECONCILIATION.is_file():
        raise RuntimeError("Hualapai CSAMT role reconciliation missing")
    if not NTGS_ANGULARLI_CSAMT.is_file():
        raise RuntimeError("NTGS Angularli CSAMT contract evidence missing")
    if any(
        not path.is_file()
        for path in (
            CSAMT_LINE_SPLIT_V2,
            CSAMT_TRAINING_MANIFEST_V2,
            CSAMT_TRAINING_CONTRACT_V2,
            WUXI_CSAMT_DESIGN,
            WUXI_CSAMT_TRAINING,
            NTGS_CR20130857_CSAMT_DESIGN,
            NTGS_CR20130857_CSAMT_TRAINING,
            BIG_CHINO_CSAMT_DESIGN,
            BIG_CHINO_CSAMT_TRAINING,
        )
    ):
        raise RuntimeError("CSAMT whole-line training evidence missing")
    if not BAOTU_WFEM_LINE_SPLIT.is_file() or not BAOTU_WFEM_TRAINING.is_file():
        raise RuntimeError("Baotu WFEM training evidence missing")
    mount_st_helens = json.loads(
        MOUNT_ST_HELENS_CSAMT_CONTRACT.read_text(encoding="utf-8")
    )
    if not (
        mount_st_helens.get("schema_version")
        == "wp8-usgs-mount-st-helens-csamt-contract-v1"
        and mount_st_helens.get("station_count") == 13
        and mount_st_helens.get("controlled_source_station_upper_bound") == 12
        and mount_st_helens.get("all_edi_have_rho_phase_and_error_arrays") is True
        and mount_st_helens.get("source_contract", {}).get(
            "exact_source_coordinates_present"
        ) is False
        and mount_st_helens.get("available_grounded_finite_line_solver_compatible")
        is False
        and mount_st_helens.get("observation_contract_ready") is False
        and mount_st_helens.get("formal_cluster_power_gate_passes") is False
        and mount_st_helens.get("response_values_interpreted") == 0
        and mount_st_helens.get("test_unseal_count") == 0
    ):
        raise RuntimeError("Mount St. Helens CSAMT contract evidence drift")
    hualapai = json.loads(HUALAPAI_CSAMT_CONTRACT.read_text(encoding="utf-8"))
    if not (
        hualapai.get("schema_version") == "wp8-usgs-hualapai-csamt-contract-v2"
        and hualapai.get("doi") == "10.5066/P90KAJM4"
        and hualapai.get("scope") == "permanently-training-only"
        and hualapai.get("field_validation_eligible") is False
        and hualapai.get("sealed_test_accessed") is False
        and hualapai.get("license_gate_passes") is True
        and hualapai.get("line_ids")
        == ["A1", "A2", "PT1", "PT2", "PT3", "QB1", "QB2", "QB3", "WG"]
        and hualapai.get("raw_line_file_count") == 9
        and hualapai.get("station_line_file_count") == 9
        and hualapai.get("inversion_line_file_count") == 9
        and hualapai.get("source_coordinates_imputed") is False
        and hualapai.get("site_mapping", {}).get("status")
        == "unsupported_by_anchored_official_evidence"
        and hualapai.get("site_mapping", {}).get(
            "requested_three_site_mapping_accepted"
        )
        is False
        and hualapai.get("site_mapping", {}).get("lines_are_sites") is False
        and hualapai.get("site_mapping", {}).get(
            "partial_marker_verified_from_mtm_headers"
        )
        is True
        and hualapai.get("available_provider_line_clusters") == 9
        and hualapai.get("observation_contract_ready") is False
        and hualapai.get("formal_cluster_power_gate_passes") is False
    ):
        raise RuntimeError("Hualapai CSAMT conservative contract evidence drift")
    angularli = json.loads(NTGS_ANGULARLI_CSAMT.read_text(encoding="utf-8"))
    if not (
        angularli.get("schema_version")
        == "wp8-ntgs-angularli-csamt-contract-v1"
        and angularli.get("archive_sha256")
        == "e6be7999a4b16417eb3c45881352724ed99c10b7dd8ed3f49c6f7c65210f01ad"
        and angularli.get("transmitter", {}).get(
            "endpoint_coordinates_derivable"
        )
        is True
        and angularli.get("transmitter", {}).get("length_m") == 1770
        and angularli.get("transmitter", {}).get("azimuth_deg") == 0
        and angularli.get("transmitter", {}).get("sampled_waveform_present")
        is False
        and angularli.get("receiver", {}).get("unique_centers") == 24
        and angularli.get("observations", {}).get("row_count") == 417
        and angularli.get("observations", {}).get("frequency_count") == 21
        and angularli.get("formal_finite_source_observation_contract_ready")
        is False
        and angularli.get("cluster_gate_passes") is False
    ):
        raise RuntimeError("NTGS Angularli CSAMT contract evidence drift")
    csamt_line_split = json.loads(CSAMT_LINE_SPLIT_V2.read_text(encoding="utf-8"))
    reconciliation = json.loads(
        HUALAPAI_CSAMT_RECONCILIATION.read_text(encoding="utf-8")
    )
    if not (
        reconciliation.get("schema_version")
        == "wp8-hualapai-csamt-role-reconciliation-v1"
        and reconciliation.get("raw_manifest_sha256")
        == hualapai.get("raw_manifest_sha256")
        and reconciliation.get("contract_sha256")
        == sha256_file(HUALAPAI_CSAMT_CONTRACT)
        and reconciliation.get("legacy_csamt_line_split_sha256")
        == sha256_file(CSAMT_LINE_SPLIT_V2)
        and reconciliation.get("legacy_split_preserved") is True
        and reconciliation.get("legacy_hualapai_test_line_count") == 6
        and reconciliation.get("legacy_hualapai_test_role_status")
        == "contaminated_and_superseded"
        and reconciliation.get("effective_hualapai_scope")
        == "permanently-training-only"
        and reconciliation.get("hualapai_sealed_test_eligible") is False
        and reconciliation.get("hualapai_formal_contribution") == 0
        and reconciliation.get("formal_cluster_power_gate_passes") is False
    ):
        raise RuntimeError("Hualapai CSAMT role reconciliation drift")
    csamt_training_manifest = json.loads(
        CSAMT_TRAINING_MANIFEST_V2.read_text(encoding="utf-8")
    )
    csamt_training_contract = json.loads(
        CSAMT_TRAINING_CONTRACT_V2.read_text(encoding="utf-8")
    )
    if not (
        csamt_line_split.get("schema_version")
        == "wp8-csamt-whole-line-split-v2"
        and csamt_line_split.get("selection_frozen_before_response_access") is True
        and csamt_line_split.get("partition_line_counts")
        == {"test": 14, "buffer": 4, "train": 9, "calibration": 3}
        and csamt_line_split.get("test_response_members_opened") == 0
        and csamt_training_manifest.get("schema_version")
        == "wp8-csamt-training-lines-manifest-v2"
        and csamt_training_manifest.get("design_sha256")
        == sha256_file(CSAMT_LINE_SPLIT_V2)
        and csamt_training_manifest.get("extracted_roles") == ["train"]
        and csamt_training_manifest.get("training_line_count") == 9
        and csamt_training_manifest.get("test_response_members_opened") == 0
        and csamt_training_contract.get("schema_version")
        == "wp8-csamt-training-line-contract-v2"
        and csamt_training_contract.get("training_manifest_sha256")
        == sha256_file(CSAMT_TRAINING_MANIFEST_V2)
        and csamt_training_contract.get("frequency_count") == 16
        and csamt_training_contract.get("components") == ["Ex", "Hy"]
        and csamt_training_contract.get("exact_transmitter_endpoints_present")
        is False
        and csamt_training_contract.get(
            "formal_finite_source_observation_contract_ready"
        )
        is False
        and csamt_training_contract.get("line_level_test_cluster_upper_bound")
        == 14
        and csamt_training_contract.get("test_response_members_opened") == 0
    ):
        raise RuntimeError("CSAMT whole-line training evidence drift")
    wuxi_design = json.loads(WUXI_CSAMT_DESIGN.read_text(encoding="utf-8"))
    wuxi_training = json.loads(WUXI_CSAMT_TRAINING.read_text(encoding="utf-8"))
    if not (
        wuxi_design.get("schema_version") == "wp8-public-evidence-v1"
        and wuxi_design.get("freeze", {}).get("status")
        == "frozen_before_response_payload_extraction"
        and wuxi_design.get("freeze", {}).get("response_values_seen") is False
        and wuxi_design.get("processed_line_roles", {}).get("test") == [7800, 8000]
        and wuxi_design.get("raw_acquisition_date_roles", {}).get("test")
        == ["20110406", "20110408"]
        and wuxi_design.get("workbook_geometry_protocol", {}).get(
            "test_response_unseals"
        )
        == 0
        and wuxi_training.get("schema_version") == "wp8-public-evidence-v1"
        and wuxi_training.get("test_unseals") == 0
        and wuxi_training.get("archive_inventory", {}).get(
            "processed_csamt_lines"
        )
        == 14
        and wuxi_training.get("archive_inventory", {}).get(
            "training_cmd_cms_pairs"
        )
        == 64
        and wuxi_training.get("training_cmd_observations", {}).get(
            "frequency_blocks"
        )
        == 1723
        and wuxi_training.get("training_cmd_observations", {}).get(
            "unique_frequency_count"
        )
        == 27
        and wuxi_training.get("training_cmd_observations", {}).get(
            "rows_with_percent_uncertainty_fields"
        )
        == 13784
        and wuxi_training.get("contract_assessment", {}).get(
            "transmitter_endpoint_coordinates_present"
        )
        is False
        and wuxi_training.get("contract_assessment", {}).get(
            "observation_contract_passed"
        )
        is False
        and wuxi_training.get("contract_assessment", {}).get(
            "cluster_contract_passed"
        )
        is False
        and wuxi_training.get("contract_assessment", {}).get(
            "power_contract_passed"
        )
        is False
    ):
        raise RuntimeError("Wuxi CSAMT training evidence drift")
    big_chino_design = json.loads(BIG_CHINO_CSAMT_DESIGN.read_text(encoding="utf-8"))
    big_chino_training = json.loads(
        BIG_CHINO_CSAMT_TRAINING.read_text(encoding="utf-8")
    )
    big_chino_power = json.loads(
        BIG_CHINO_CSAMT_POWER_READINESS.read_text(encoding="utf-8")
    )
    if not (
        sha256_file(BIG_CHINO_CSAMT_POWER_READINESS)
        == EXPECTED_BIG_CHINO_CSAMT_POWER_READINESS_SHA256
        and
        big_chino_design.get("design_version") == "usgs-big-chino-csamt-design-v1"
        and big_chino_design.get("status")
        == "frozen_before_response_archive_download_or_inspection"
        and big_chino_design.get("counts", {}).get("stations") == 1159
        and big_chino_design.get("counts", {}).get(
            "sealed_independent_test_clusters"
        )
        == 257
        and big_chino_design.get("split", {}).get(
            "minimum_training_test_distance_m"
        )
        == 200.0
        and big_chino_design.get("split", {}).get("minimum_test_test_distance_m")
        == 200.0
        and big_chino_training.get("schema_version")
        == "wp8-usgs-big-chino-csamt-training-audit-v1"
        and big_chino_training.get("design_sha256")
        == sha256_file(BIG_CHINO_CSAMT_DESIGN)
        and big_chino_training.get("partition", {}).get(
            "test_response_members_opened"
        )
        == 0
        and big_chino_training.get("training_observation_contract", {}).get(
            "components"
        )
        == ["Ex", "Hy"]
        and big_chino_training.get("training_observation_contract", {}).get(
            "frequency_count"
        )
        == 17
        and big_chino_training.get("training_observation_contract", {}).get(
            "finite_source_geometry_complete"
        )
        is True
        and big_chino_training.get("training_observation_contract", {}).get(
            "repeat_measurements_present"
        )
        is True
        and big_chino_training.get("gate_assessment", {}).get(
            "canonical_observation_contract_passes"
        )
        is True
        and big_chino_power.get("schema_version")
        == "usgs-big-chino-csamt-training-power-readiness-v1"
        and big_chino_power.get("scope") == "training-only"
        and big_chino_power.get("status") == "blocked"
        and big_chino_power.get("structure_audit_passed") is True
        and big_chino_power.get("errors") == []
        and big_chino_power.get("approved_sha256", {}).get("design")
        == sha256_file(BIG_CHINO_CSAMT_DESIGN)
        and big_chino_power.get("approved_sha256", {}).get("training_audit")
        == sha256_file(BIG_CHINO_CSAMT_TRAINING)
        and big_chino_power.get("approved_sha256", {}).get("raw")
        == sha256_file(BIG_CHINO_CSAMT_RAW)
        and big_chino_power.get("approved_sha256", {}).get("inversion")
        == sha256_file(BIG_CHINO_CSAMT_INVERSION)
        and big_chino_power.get("partition", {}).get(
            "response_content_members_opened_by_this_audit"
        )
        == []
        and big_chino_power.get("partition", {}).get(
            "archive_member_leakage_by_this_audit"
        )
        == []
        and big_chino_power.get("partition", {}).get(
            "train_sealed_unique_disjoint_complete"
        )
        is True
        and big_chino_power.get("partition", {}).get("approved_line_count") == 21
        and big_chino_power.get("partition", {}).get("authorized_training_lines")
        == ["CG", "CH", "EW2", "FMW", "NS1", "NS3"]
        and big_chino_power.get("partition", {}).get("sealed_lines")
        == ["AX", "EW1", "EW3", "FM", "FME", "GS16", "GS6", "GS8", "K1",
            "NS2", "NS4", "NS5", "WC", "WCN", "WR"]
        and big_chino_power.get("partition", {}).get("missing_training_members")
        == []
        and big_chino_power.get("inference_hierarchy", {}).get(
            "training_observations_reported"
        )
        == 342
        and big_chino_power.get("inference_hierarchy", {}).get("training_lines")
        == 6
        and big_chino_power.get("inference_hierarchy", {}).get("training_sites")
        == 1
        and big_chino_power.get("design_reconciliation", {}).get("claim_status")
        == "superseded_for_formal_gate"
        and big_chino_power.get("design_reconciliation", {}).get(
            "formal_independent_cluster_proven_upper_bound"
        )
        == 1
        and big_chino_power.get("design_reconciliation", {}).get(
            "sealed_packaged_line_upper_bound_not_independence_evidence"
        )
        == 15
        and big_chino_power.get("design_reconciliation", {}).get(
            "formal_cluster_gate_passes"
        )
        is False
        and big_chino_power.get("formal_power_gate_passes") is False
        and big_chino_power.get("formal_power_status") == "blocked"
        and big_chino_power.get("paired_crps_computed") is False
        and big_chino_power.get("paired_power_inputs", {}).get(
            "validated_registry_count"
        )
        == 0
        and set(
            big_chino_power.get("paired_power_inputs", {}).get(
                "minimum_computable_conditions", {}
            )
        )
        == {
            "cluster_and_correlation_model_frozen",
            "required_independent_cluster_count_derived_by_frozen_power_method",
            "two_frozen_methods_named_and_versioned",
            "same_information_and_compute_budget",
            "paired_out_of_sample_predictions_cover_all_training_lines",
            "paired_crps_artifact_hash_registered",
        }
        and all(
            value is False
            for value in big_chino_power.get("paired_power_inputs", {}).get(
                "minimum_computable_conditions", {}
            ).values()
        )
        and big_chino_power.get("field_validation_eligible") is False
        and big_chino_training.get("gate_assessment", {}).get(
            "power_gate_passes"
        )
        is False
    ):
        raise RuntimeError("USGS Big Chino CSAMT evidence drift")
    csamt_public = json.loads(
        CSAMT_PUBLIC_SEARCH_AUDIT.read_text(encoding="utf-8")
    )
    csamt_public_records = {
        str(row.get("record_id")): row for row in csamt_public.get("records", [])
    }
    pycsamt = csamt_public_records.get("5674430", {})
    pilgrim = csamt_public_records.get("DGGS-RDF-2020-9", {})
    pycsamt_archive = ROOT / pycsamt.get("archive_path", "")
    pilgrim_archive = ROOT / pilgrim.get("archive_path", "")
    if not (
        csamt_public.get("schema_version")
        == "wp8-zenodo-csamt-public-search-audit-v1"
        and csamt_public.get("formal_test_responses_opened") == 0
        and csamt_public.get("test_unseal_count") == 0
        and pycsamt_archive.is_file()
        and pycsamt.get("archive_bytes") == pycsamt_archive.stat().st_size
        and pycsamt.get("archive_sha256") == sha256_file(pycsamt_archive)
        and pycsamt.get("controlled_source_station_count") == 47
        and pycsamt.get("controlled_source_observation_count") == 799
        and pycsamt.get("natural_source_excluded_from_csamt_count") is True
        and pycsamt.get("transmitter_endpoint_coordinates_present") is False
        and pycsamt.get("sampled_transmitter_waveform_present") is False
        and pycsamt.get("cluster_gate_passes") is False
        and pilgrim_archive.is_file()
        and pilgrim.get("archive_bytes") == pilgrim_archive.stat().st_size
        and pilgrim.get("archive_sha256") == sha256_file(pilgrim_archive)
        and pilgrim.get("raw_component_file_count") == 99
        and pilgrim.get("field_log_location_count") == 20
        and pilgrim.get("receiver_electrode_endpoints_present") is True
        and pilgrim.get("transmitter_endpoint_coordinates_present") is False
        and pilgrim.get("sampled_transmitter_waveform_present") is False
        and pilgrim.get("observation_contract_ready") is False
        and pilgrim.get("cluster_gate_passes") is False
    ):
        raise RuntimeError("public CSAMT search evidence drift")
    sevier = json.loads(SEVIER_CSAMT_RAW_AUDIT.read_text(encoding="utf-8"))
    sevier_archive = ROOT / sevier.get("source", {}).get("archive_path", "")
    if not (
        sevier.get("schema_version")
        == "wp8-usgs-sevier-fault-csamt-raw-audit-v2"
        and sevier.get("partition") == "permanently-training-only"
        and sevier_archive.is_file()
        and sevier.get("source", {}).get("archive_bytes")
        == sevier_archive.stat().st_size
        and sevier.get("source", {}).get("archive_sha256")
        == sha256_file(sevier_archive)
        and sevier.get("source", {}).get("provider_parent_zip_restored") is True
        and sevier.get("lines", {}).get("Sv1", {}).get("stations", {}).get(
            "station_count"
        )
        == 101
        and sevier.get("lines", {}).get("Sv2", {}).get("stations", {}).get(
            "station_count"
        )
        == 40
        and sevier.get("lines", {}).get("Sv1", {}).get("raw", {}).get(
            "unique_frequency_count"
        )
        == 11
        and sevier.get("lines", {}).get("Sv2", {}).get("raw", {}).get(
            "unique_frequency_count"
        )
        == 12
        and sevier.get("gate_assessment", {}).get(
            "electric_and_magnetic_components_present"
        )
        is True
        and sevier.get("gate_assessment", {}).get(
            "transmitter_endpoint_coordinates_present"
        )
        is False
        and sevier.get("gate_assessment", {}).get(
            "sampled_transmitter_waveform_present"
        )
        is False
        and sevier.get("gate_assessment", {}).get(
            "independent_profile_upper_bound"
        )
        == 2
        and sevier.get("gate_assessment", {}).get(
            "observation_contract_passes"
        )
        is False
        and sevier.get("gate_assessment", {}).get("cluster_gate_passes")
        is False
        and sevier.get("gate_assessment", {}).get("power_gate_passes")
        is False
        and sevier.get("formal_test_responses_opened") == 0
        and sevier.get("test_unseal_count") == 0
        and sevier.get("formal_test_result") is None
    ):
        raise RuntimeError("USGS Sevier CSAMT restored raw evidence drift")
    san_antonio = json.loads(
        SAN_ANTONIO_CONTROLLED_SOURCE_AMT_AUDIT.read_text(encoding="utf-8")
    )
    if not (
        san_antonio.get("schema_version")
        == "wp8-usgs-san-antonio-controlled-source-amt-audit-v1"
        and san_antonio.get("archive", {}).get("bytes") == 105_815_157
        and san_antonio.get("archive", {}).get("sha256")
        == "b85e0ceb05ae593c65dd2ac461101fec23c9341edf643457e9bd13c336cac31b"
        and san_antonio.get("archive", {}).get("members") == 87
        and san_antonio.get("survey", {}).get("sites") == 29
        and san_antonio.get("byte_audit", {}).get(
            "impedance_frequency_rows"
        )
        == 1_682
        and san_antonio.get("byte_audit", {}).get(
            "complex_impedance_tensor_present"
        )
        is True
        and san_antonio.get("byte_audit", {}).get(
            "raw_receiver_time_series_present"
        )
        is True
        and san_antonio.get("missing_source_contract", {}).get(
            "sampled_transmitter_waveform"
        )
        is False
        and san_antonio.get("gate_assessment", {}).get(
            "independent_cluster_upper_bound"
        )
        == 29
        and san_antonio.get("gate_assessment", {}).get(
            "observation_contract_pass"
        )
        is False
        and san_antonio.get("gate_assessment", {}).get("formal_gate_changed")
        is False
    ):
        raise RuntimeError("USGS San Antonio controlled-source AMT evidence drift")
    full_waveform_csamt = json.loads(
        CSAMT_FULL_WAVEFORM_ACCESS_AUDIT.read_text(encoding="utf-8")
    )
    if not (
        full_waveform_csamt.get("schema_version")
        == "wp8-csamt-full-waveform-current-recorder-access-audit-v1"
        and full_waveform_csamt.get("source", {}).get("doi")
        == "10.5194/gi-8-139-2019"
        and full_waveform_csamt.get("field_experiment", {}).get(
            "receiver_count"
        )
        == 15
        and full_waveform_csamt.get("field_experiment", {}).get(
            "csamt_frequency_count"
        )
        == 41
        and full_waveform_csamt.get("field_experiment", {}).get(
            "continuous_current_waveform_recorded"
        )
        is True
        and full_waveform_csamt.get("access_audit", {}).get(
            "anonymous_raw_data_download"
        )
        is False
        and full_waveform_csamt.get("gate_assessment", {}).get(
            "source_contract_byte_auditable"
        )
        is False
        and full_waveform_csamt.get("gate_assessment", {}).get(
            "independent_cluster_upper_bound"
        )
        == 15
        and full_waveform_csamt.get("gate_assessment", {}).get(
            "formal_gate_changed"
        )
        is False
    ):
        raise RuntimeError("full-waveform CSAMT access evidence drift")
    ntgs_cr20100883_inventory = json.loads(
        NTGS_CR20100883_INVENTORY.read_text(encoding="utf-8")
    )
    ntgs_cr20100883_design = json.loads(
        NTGS_CR20100883_CSAMT_DESIGN.read_text(encoding="utf-8")
    )
    ntgs_cr20100883_archive = (
        ROOT / ntgs_cr20100883_inventory.get("archive_path", "")
    )
    if not (
        ntgs_cr20100883_inventory.get("schema_version")
        == "wp8-ntgs-cr20100883-response-blind-inventory-v1"
        and ntgs_cr20100883_archive.is_file()
        and ntgs_cr20100883_inventory.get("archive_bytes")
        == ntgs_cr20100883_archive.stat().st_size
        and ntgs_cr20100883_inventory.get("archive_sha256")
        == sha256_file(ntgs_cr20100883_archive)
        and ntgs_cr20100883_inventory.get("archive_member_count") == 8818
        and ntgs_cr20100883_inventory.get("response_payload_members_opened") == 0
        and ntgs_cr20100883_inventory.get("test_response_members_opened") == 0
        and ntgs_cr20100883_inventory.get("central_directory_only") is True
        and ntgs_cr20100883_inventory.get("method_name_member_counts", {}).get(
            "csamt"
        )
        == 242
        and ntgs_cr20100883_inventory.get("method_name_member_counts", {}).get(
            "pdip"
        )
        == 270
        and ntgs_cr20100883_design.get("schema_version")
        == "wp8-ntgs-cr20100883-csamt-design-audit-v1"
        and ntgs_cr20100883_design.get("inventory_sha256")
        == sha256_file(NTGS_CR20100883_INVENTORY)
        and ntgs_cr20100883_design.get("response_payload_members_opened") == 0
        and ntgs_cr20100883_design.get("test_response_members_opened") == 0
        and ntgs_cr20100883_design.get("survey_line_count") == 5
        and ntgs_cr20100883_design.get("published_sounding_count") == 111
        and ntgs_cr20100883_design.get(
            "transmitter_geometry_unambiguous_line_count"
        )
        == 4
        and ntgs_cr20100883_design.get("sampled_transmitter_waveform_present")
        is False
        and ntgs_cr20100883_design.get("independent_cluster_upper_bound") == 111
        and ntgs_cr20100883_design.get("observation_contract_ready") is False
        and ntgs_cr20100883_design.get("cluster_gate_passes") is False
        and ntgs_cr20100883_design.get("power_gate_passes") is False
    ):
        raise RuntimeError("NTGS CR2010-0883 CSAMT evidence drift")
    ntgs_cr20130857_design = json.loads(
        NTGS_CR20130857_CSAMT_DESIGN.read_text(encoding="utf-8")
    )
    ntgs_cr20130857_archive = (
        ROOT / ntgs_cr20130857_design.get("archive_path", "")
    )
    ntgs_cr20130857_training = json.loads(
        NTGS_CR20130857_CSAMT_TRAINING.read_text(encoding="utf-8")
    )
    if not (
        ntgs_cr20130857_design.get("schema_version")
        == "wp8-ntgs-cr20130857-csamt-design-audit-v1"
        and ntgs_cr20130857_archive.is_file()
        and ntgs_cr20130857_design.get("archive_bytes")
        == ntgs_cr20130857_archive.stat().st_size
        and ntgs_cr20130857_design.get("archive_sha256")
        == sha256_file(ntgs_cr20130857_archive)
        and ntgs_cr20130857_design.get("response_payload_members_opened") == 0
        and ntgs_cr20130857_design.get("test_response_members_opened") == 0
        and ntgs_cr20130857_design.get("published_line_count") == 13
        and ntgs_cr20130857_design.get("published_sounding_count") == 205
        and ntgs_cr20130857_design.get("coordinate_file_count") == 13
        and ntgs_cr20130857_design.get("coordinate_row_count") == 217
        and ntgs_cr20130857_design.get("transmitter_contract", {}).get(
            "center_gda94_zone_53"
        )
        == [478230, 7405490]
        and ntgs_cr20130857_design.get("transmitter_contract", {}).get(
            "length_m"
        )
        == 1995
        and ntgs_cr20130857_design.get("transmitter_contract", {}).get(
            "sampled_waveform_present"
        )
        is False
        and ntgs_cr20130857_design.get("absolute_sounding_upper_bound") == 205
        and ntgs_cr20130857_design.get("observation_contract_ready") is False
        and ntgs_cr20130857_design.get("cluster_gate_passes") is False
        and ntgs_cr20130857_design.get("power_gate_passes") is False
        and ntgs_cr20130857_design.get("rights_gate_ready") is False
        and ntgs_cr20130857_training.get("schema_version")
        == "wp8-ntgs-cr20130857-csamt-training-header-audit-v1"
        and ntgs_cr20130857_training.get("design_sha256")
        == sha256_file(NTGS_CR20130857_CSAMT_DESIGN)
        and ntgs_cr20130857_training.get("archive_sha256")
        == sha256_file(ntgs_cr20130857_archive)
        and ntgs_cr20130857_training.get("training_raw_members_opened") == 10
        and ntgs_cr20130857_training.get("calibration_raw_members_opened") == 0
        and ntgs_cr20130857_training.get("test_raw_members_opened") == 0
        and ntgs_cr20130857_training.get("test_response_values_interpreted") == 0
        and ntgs_cr20130857_training.get("training_response_values_interpreted")
        == 0
        and ntgs_cr20130857_training.get("training_acquisition_header_count")
        == 970
        and ntgs_cr20130857_training.get("unique_frequency_hz")
        == [4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0, 1024.0, 2048.0, 4096.0, 8192.0]
        and ntgs_cr20130857_training.get(
            "sampled_transmitter_waveform_present"
        )
        is False
        and ntgs_cr20130857_training.get("observation_contract_ready") is False
    ):
        raise RuntimeError("NTGS CR2013-0857 CSAMT evidence drift")
    baotu_split = json.loads(BAOTU_WFEM_LINE_SPLIT.read_text(encoding="utf-8"))
    baotu_training = json.loads(BAOTU_WFEM_TRAINING.read_text(encoding="utf-8"))
    if not (
        baotu_split.get("schema_version") == "wp8-baotu-wfem-line-split-v1"
        and baotu_split.get("license") == "cc-by-4.0"
        and baotu_split.get("selection_frozen_before_response_interpretation")
        is True
        and baotu_split.get("partition_line_counts")
        == {"test": 14, "train": 10, "buffer": 2, "calibration": 1}
        and baotu_split.get("test_response_values_interpreted") == 0
        and baotu_training.get("schema_version")
        == "wp8-baotu-wfem-training-audit-v1"
        and baotu_training.get("design_sha256")
        == sha256_file(BAOTU_WFEM_LINE_SPLIT)
        and baotu_training.get("training_line_count") == 10
        and baotu_training.get("training_rows_interpreted") == 44074
        and baotu_training.get("observed_columns")
        == ["Station", "Fre", "Rho_mn"]
        and baotu_training.get("formal_observation_contract_ready") is False
        and baotu_training.get("line_level_test_cluster_upper_bound") == 14
        and baotu_training.get("dimensionality_gate_passed") is False
        and baotu_training.get("test_response_values_interpreted") == 0
    ):
        raise RuntimeError("Baotu WFEM training evidence drift")
    geodata_cn = json.loads(
        GEODATA_CN_LOCKED_METHODS.read_text(encoding="utf-8")
    )
    geodata_records = {
        row.get("id"): row for row in geodata_cn.get("records", [])
    }
    sichuan_wfem = geodata_records.get("sichuan-central-wfem-2017", {})
    geodata_active_source_ids = {
        "laizhou-em-demonstration-2020",
        "laizhou-em-comparison-2020",
        "caosiyao-em-demonstration-2020",
        "caosiyao-em-comparison-2020",
        "taohemu-em-demonstration-2019",
        "taohemu-em-comparison-2019",
        "xiongan-controlled-source-em-2020",
        "tongling-tensor-controlled-source-2021",
        "tongling-short-offset-em-2021",
    }
    geodata_active_source = [
        geodata_records.get(key, {}) for key in geodata_active_source_ids
    ]
    sichuan_document = ROOT / sichuan_wfem.get("public_document_path", "")
    if not (
        geodata_cn.get("schema_version")
        == "wp8-geodata-cn-locked-methods-metadata-audit-v1"
        and geodata_cn.get("formal_test_responses_opened") == 0
        and geodata_cn.get("test_unseal_count") == 0
        and len(geodata_records) == 13
        and sichuan_wfem.get("doi")
        == "10.12041/geodata.37412589003507.ver1.db"
        and sichuan_wfem.get("access_group_id") == 7
        and sichuan_wfem.get("anonymous_entity_download") is False
        and sichuan_wfem.get("response_entity_opened") is False
        and sichuan_wfem.get("documented_fields")
        == {
            "station": True,
            "frequency": True,
            "source_current": True,
            "electric_field": True,
            "relative_error": True,
            "apparent_resistivity": True,
            "receiver_coordinates": True,
        }
        and sichuan_wfem.get("sampled_transmitter_waveform_public") is False
        and sichuan_wfem.get("source_endpoint_coordinates_public") is False
        and sichuan_wfem.get("formal_observation_contract_ready") is False
        and sichuan_document.is_file()
        and sichuan_wfem.get("public_document_bytes")
        == sichuan_document.stat().st_size
        and sichuan_wfem.get("public_document_sha256")
        == sha256_file(sichuan_document)
        and all(
            row.get("response_entity_opened") is False
            for row in geodata_records.values()
        )
        and all(
            row.get("access_group_id") == 7
            and row.get("catalogue_is_online") is False
            and row.get("anonymous_entity_download") is False
            and row.get("sampled_transmitter_waveform_public") is False
            and row.get("source_complete_population_public") is False
            and row.get("formal_cluster_contribution") == 0
            and (ROOT / row.get("public_document_path", "")).is_file()
            and row.get("public_document_sha256")
            == sha256_file(ROOT / row.get("public_document_path", ""))
            for row in geodata_active_source
        )
        and sorted(
            row.get("public_document_design_audit", {}).get(
                "nominal_station_upper_bound"
            )
            for row in geodata_active_source
            if row.get("public_document_design_audit", {}).get(
                "nominal_station_upper_bound"
            )
            is not None
        )
        == [21, 80, 160, 300, 300]
        and geodata_cn.get("conclusion", {}).get(
            "offline_active_source_candidates_found"
        )
        == 9
        and geodata_cn.get("conclusion", {}).get(
            "nominal_csamt_station_upper_bound_at_least_223"
        )
        == 2
        and all(
            row.get("locked_sip_fdip_method_match") is False
            for key, row in geodata_records.items()
            if key != "sichuan-central-wfem-2017"
        )
    ):
        raise RuntimeError("geodata.cn locked-method metadata evidence drift")
    csamt_geometry = json.loads(CSAMT_GEOMETRY.read_text(encoding="utf-8"))
    csamt_geometry_input = ROOT / csamt_geometry.get("input_path", "")
    csamt_dimension_ok = (
        csamt_geometry.get("schema_version") == "wp8-csamt-geometry-v1"
        and csamt_geometry.get("observation_or_inversion_values_parsed") is False
        and csamt_geometry_input.is_file()
        and csamt_geometry.get("input_sha256") == sha256_file(csamt_geometry_input)
        and csamt_geometry.get("dimensionality", {}).get("selected")
        == "3-D finite-source"
        and csamt_geometry.get("dimensionality", {}).get("passed") is True
        and csamt_geometry.get("available_solver_compatible") is True
    )
    result = {}
    for method, entrypoint in expected.items():
        evidence = payload.get("methods", {}).get(method, {})
        implementation = evidence.get("implementation", {})
        solver_ok = (
            implementation.get("entrypoint") == entrypoint
            and bool(implementation.get("dependency_versions"))
            and "3-D" in implementation.get("applicable_dimension", "")
        )
        reference = evidence.get("independent_reference", {})
        reference_path = ROOT / reference.get("test_path", "")
        reference_ok = (
            reference.get("passed") is True
            and reference.get("pytest_exit_code") == 0
            and reference_path.is_file()
            and reference.get("test_source_sha256") == sha256_file(reference_path)
        )
        resource = evidence.get("resource_measurement", {})
        resource_ok = (
            resource.get("passed") is True
            and len(resource.get("records", [])) == 3
            and all(row.get("finite") for row in resource.get("records", []))
            and resource.get("timeout_seconds", 0) > 0
            and resource.get("memory_limit_bytes", 0) > 0
        )
        result[method] = {
            "gates": {
                "solver": gate(
                    "passed" if solver_ok else "blocked",
                    "version-frozen 3-D finite-line Maxwell path"
                    if solver_ok
                    else "controlled-source solver evidence invalid",
                ),
                "independent_reference": gate(
                    "passed" if reference_ok else "blocked",
                    reference.get("kind", "controlled-source reference invalid"),
                ),
                "resource_budget": gate(
                    "passed" if resource_ok else "blocked",
                    "three measured meshes plus enforced timeout/memory abort limits"
                    if resource_ok
                    else "controlled-source resource evidence invalid",
                ),
            }
        }
        if method == "csamt":
            result[method]["gates"]["observation_contract"] = gate(
                "passed",
                "The outcome-blind USGS Big Chino replacement supplies 17 "
                "frequencies from 0.125 to 8192 Hz, measured transmitter current, "
                "repeated Ex/Hy observations, receiver coordinates/dipoles and "
                "SCS2D apparent-resistivity/phase error floors. Training-only MTM "
                "headers provide a 1,000-m finite bipole centre and azimuth for "
                "every training line, so exact endpoints are deterministically "
                "derived. Frequency and complex amplitude/phase fully specify the "
                "frequency-domain source; sampled time-domain waveform values are "
                "not required by the canonical CSAMT contract. "
                "Mount St. Helens adds 13 EDI files with rho/phase error arrays "
                "but its inductive source is only approximately 250 m west and "
                "lacks exact coordinates, orientation, moment/current and waveform. "
                "Wuxi adds 64 frozen training CMD files with 1,723 frequency "
                "blocks, 13,784 channel rows carrying percent-error fields, "
                "3.5 A current, 25-m receiver dipoles, 7-km source-receiver "
                "distance and a 1,550-m transmitter dipole; its exact transmitter "
                "endpoints and complete waveform remain absent. Angularli line "
                "9100E adds a public 1,770-m finite bipole with exact derivable "
                "endpoints, 24 Ex/Hy receiver centres, 21 frequencies, current "
                "and percent-error fields; sampled transmitter waveform values "
                "remain absent. The pyCSAMT release adds one 47-station field "
                "profile but no transmitter endpoints or sampled waveform; "
                "Pilgrim Hot Springs adds raw Stratagem components and receiver "
                "electrode geometry, but likewise lacks transmitter endpoints "
                "and a sampled waveform. NTGS CR2010-0883 adds five raw CSAMT "
                "lines; geometry-only MDE parsing yields unique derivable "
                "transmitter endpoints for four lines, but Trinity L35 has "
                "conflicting source metadata and no line publishes sampled "
                "waveform values. NTGS CR2013-0857 adds a larger anonymous raw "
                "package with 205 soundings on 13 lines, exact source center, "
                "orientation and 1,995-m length, Ex/Hy components, and "
                "frequency-dependent field-current sheets; it still lacks "
                "sampled waveform values and an explicit reusable data licence. "
                "The restored USGS Red Knoll parent ZIP adds 141 station "
                "coordinates and 18,072 raw Ex/Hy component rows on two lines "
                "at 1-8,192 Hz, but it also lacks exact transmitter endpoints "
                "and sampled waveform values and is permanently training-only. "
                "USGS San Antonio adds 29 coordinate-known sites with 1,682 "
                "impedance-frequency rows, full complex tensors, cross-powers "
                "and raw receiver time series; however natural and controlled "
                "sources are mixed and the transmitter geometry, current, "
                "sampled waveform, per-site source provenance and direct "
                "uncertainty remain unpublished. "
                "The 2019 Linxi full-waveform recorder experiment demonstrates "
                "continuous GPS-stamped transmitter-current sampling across 41 "
                "CSAMT frequencies, 2-30 A and a 1.3-km source dipole, but its "
                "raw transmitter and receiver files are explicitly request-only "
                "and endpoint coordinates are unpublished. "
                "Nine newly frozen geodata.cn active-source catalogue records "
                "add useful public design documents, but every response entity "
                "is group-7 offline application-only and none publicly supplies "
                "a sampled transmitter waveform",
            )
            result[method]["gates"]["clusters"] = gate(
                "blocked",
                "The Big Chino split was frozen before raw response download: "
                "six whole training lines and fifteen sealed test lines. A "
                "deterministic 200-m station packing retained 257 receiver points, "
                "but did not estimate response correlation and cannot override "
                "whole-line archive packaging; the conservative sealed inference-"
                "unit upper bound is therefore 15 lines, below 223. "
                "Mount St. Helens contributes "
                "only 12 controlled-source stations (plus one natural-source "
                "station), Wuxi adds only two sealed whole test lines, and "
                "Angularli adds one 24-centre line. pyCSAMT contributes one "
                "47-station profile and Pilgrim Hot Springs only 20 named "
                "locations. CR2010-0883 adds 111 published soundings on five "
                "lines, still independently below the frozen threshold and "
                "not a source-complete population. CR2013-0857 adds 205 "
                "soundings on 13 tightly spaced lines, but even its unadjusted "
                "sounding upper bound is below 223 and its line-level upper "
                "bound is 13. The restored Red Knoll package adds only two "
                "opened training profiles and therefore no sealed independent "
                "test cluster. San Antonio adds only 29 opened training sites "
                "and no sealed source-complete population; the Linxi waveform "
                "experiment uses only 15 receivers and is request-only. "
                "Laizhou and Caosiyao "
                "demonstration documents each "
                "imply a nominal 300 stations from 15 km/50 m, but both native "
                "entities are offline application-only; overlap, coordinates "
                "and spatial independence cannot be audited anonymously. No "
                "the Big Chino replacement is the eligible source-complete "
                "population and its sealed responses remain unopened",
            )
            result[method]["gates"]["power"] = gate(
                "blocked",
                "Big Chino has only six authorized training lines, no frozen pair "
                "of information-matched inference methods and no paired out-of-"
                "sample predictions or CRPS scores; stable paired dispersion and "
                "formal effect power are therefore not computable",
            )
            result[method]["gates"]["dimensionality"] = gate(
                "passed" if csamt_dimension_ok else "blocked",
                (
                    "official station-only audit spans three sites and multiple "
                    "line-azimuth families; 3-D finite-source physics selected"
                    if csamt_dimension_ok
                    else "CSAMT outcome-blind geometry evidence invalid"
                ),
            )
        if method == "wfem":
            result[method]["gates"]["observation_contract"] = gate(
                "blocked",
                "Ten frozen Baotu Spring training lines provide 44,074 apparent-"
                "resistivity rows at 42 frequencies (2-3072 Hz), but expose only "
                "Station/Fre/Rho_mn. Receiver coordinates, source geometry/current, "
                "phase, field component, geometric-factor definition and direct "
                "per-observation error remain absent. Sichuan metadata declares "
                "Station/Freq/I/Emag/Error/Rho plus survey coordinates, but its "
                "native payload is not anonymously downloadable",
            )
            result[method]["gates"]["clusters"] = gate(
                "blocked",
                "The outcome-blind Baotu whole-line split leaves only 14 sealed "
                "test lines; the 304-station Wucaiwan design remains request-only, "
                "so no downloadable population reaches 223 independent clusters",
            )
            result[method]["gates"]["power"] = gate(
                "blocked",
                "Baotu lacks a usable uncertainty and spatial-correlation contract; "
                "no training-only paired-CRPS effect size exists at sufficient "
                "independent cluster count",
            )
            result[method]["gates"]["dimensionality"] = gate(
                "blocked",
                "Baotu line files contain no receiver coordinates or source geometry, "
                "so the preregistered near/transition/far-zone and 3-D "
                "dimensionality diagnostic cannot be executed",
            )
    return result


def audit_tem1d_path() -> dict[str, Any]:
    if not TEM1D_PATH_READINESS.is_file():
        raise RuntimeError("TEM 1-D path readiness evidence missing")
    payload = json.loads(TEM1D_PATH_READINESS.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "wp8-tem1d-path-readiness-v1":
        raise RuntimeError("TEM 1-D path readiness schema mismatch")
    implementation = payload.get("implementation", {})
    solver_ok = (
        implementation.get("entrypoint")
        == "geodeepbayes.forward.em1d.TEM1DLayeredOperator"
        and bool(implementation.get("dependency_versions"))
        and implementation.get("applicable_dimension") == "1-D layered earth only"
        and "DimensionalityUpgradeRequired" in implementation.get("fail_closed", "")
    )
    reference = payload.get("independent_reference", {})
    reference_path = ROOT / reference.get("test_path", "")
    reference_ok = (
        reference.get("passed") is True
        and reference.get("pytest_exit_code") == 0
        and reference_path.is_file()
        and reference.get("test_source_sha256") == sha256_file(reference_path)
    )
    resource = payload.get("resource_measurement", {})
    resource_ok = (
        resource.get("passed") is True
        and len(resource.get("records", [])) == 3
        and all(row.get("finite") for row in resource.get("records", []))
        and resource.get("timeout_seconds", 0) > 0
        and resource.get("memory_limit_bytes", 0) > 0
    )
    return {
        "gates": {
            "solver": gate(
                "passed" if solver_ok else "blocked",
                "version-frozen layered 1-D TEM path; valid only if field diagnostic selects 1-D"
                if solver_ok
                else "TEM 1-D solver evidence invalid",
            ),
            "independent_reference": gate(
                "passed" if reference_ok else "blocked",
                reference.get("kind", "TEM reference invalid"),
            ),
            "resource_budget": gate(
                "passed" if resource_ok else "blocked",
                "three time-channel scales plus enforced timeout/memory abort limits"
                if resource_ok
                else "TEM resource evidence invalid",
            ),
        }
    }


def audit_selected_tdip() -> dict[str, Any]:
    if (
        not TDIP_SPLIT.is_file()
        or not TDIP_DIAGNOSTICS.is_file()
        or not TDIP_PATH_READINESS.is_file()
        or not NTGS_TDIP_COORDINATE_DESIGN.is_file()
        or not NTGS_TDIP_TRAINING_POWER.is_file()
    ):
        raise RuntimeError("TDIP split/training evidence is incomplete")
    split = json.loads(TDIP_SPLIT.read_text(encoding="utf-8"))
    diagnostic = json.loads(TDIP_DIAGNOSTICS.read_text(encoding="utf-8"))
    readiness = json.loads(TDIP_PATH_READINESS.read_text(encoding="utf-8"))
    ntgs_design = json.loads(
        NTGS_TDIP_COORDINATE_DESIGN.read_text(encoding="utf-8")
    )
    ntgs_power = json.loads(
        NTGS_TDIP_TRAINING_POWER.read_text(encoding="utf-8")
    )
    errors = []
    if diagnostic.get("split_sha256") != sha256_file(TDIP_SPLIT):
        errors.append("split-anchor")
    if split.get("observation_unit") != "acquisition_date":
        errors.append("cluster-unit")
    if split.get("counts") != {"train": 79, "buffer": 17, "calibration": 50, "test": 223}:
        errors.append("split-counts")
    if split.get("excluded", {}).get("endpoint_exposed") != ["20221023"]:
        errors.append("exposed-date")
    if split.get("excluded", {}).get("missing_reciprocal") != ["20230705"]:
        errors.append("unpaired-date")
    if set(sum(split.get("partitions", {}).values(), [])) & {"20221023", "20230705"}:
        errors.append("excluded-date-assigned")
    if diagnostic.get("training_dates_interpreted") != 79:
        errors.append("training-count")
    for key in ("buffer_dates_interpreted", "calibration_dates_interpreted", "test_dates_interpreted"):
        if diagnostic.get(key) != 0:
            errors.append(key)
    contract = diagnostic.get("contract", {})
    if not (
        contract.get("abmn") is True
        and contract.get("normal_reciprocal") is True
        and contract.get("chargeability_windows") == 20
        and contract.get("window_durations") == 20
    ):
        errors.append("contract")
    if diagnostic.get("dimensionality", {}).get("selected") != "2d":
        errors.append("dimension")
    correlation_days = diagnostic.get("temporal_correlation_length_days")
    if not isinstance(correlation_days, int) or correlation_days < 1:
        errors.append("correlation-length")
    if split.get("counts", {}).get("buffer", 0) < (correlation_days or 10**9):
        errors.append("buffer")
    effective_test = diagnostic.get("effective_cluster_counts", {}).get("test")
    if not isinstance(effective_test, int) or effective_test >= 223:
        errors.append("effective-test-clusters")
    if not (
        ntgs_design.get("schema_version")
        == "wp8-ntgs-pine-creek-tdip-coordinate-design-v1"
        and ntgs_design.get(
            "selection_frozen_before_sealed_response_interpretation"
        )
        is True
        and ntgs_design.get("training_only_correlation", {}).get(
            "unique_receiver_centres"
        )
        == 492
        and ntgs_design.get("training_only_correlation", {}).get(
            "frozen_range_m"
        )
        == 250
        and ntgs_design.get("sealed_coordinate_audit", {}).get(
            "raw_rows_with_geometry"
        )
        == 77604
        and ntgs_design.get("sealed_coordinate_audit", {}).get(
            "unique_receiver_centres"
        )
        == 1729
        and ntgs_design.get("sealed_coordinate_audit", {}).get(
            "strictly_separated_packed_centres"
        )
        == 247
        and ntgs_design.get("role_assignment", {}).get("calibration_count") == 24
        and ntgs_design.get("role_assignment", {}).get("test_count") == 223
        and ntgs_design.get("cluster_count_gate_possible") is True
        and ntgs_design.get("sealed_response_values_interpreted") == 0
        and ntgs_design.get("test_unseal_count") == 0
    ):
        errors.append("ntgs-spatial-design")
    if not (
        ntgs_power.get("schema_version")
        == "wp8-ntgs-pine-creek-tdip-training-power-v1"
        and ntgs_power.get("design_sha256")
        == sha256_file(NTGS_TDIP_COORDINATE_DESIGN)
        and ntgs_power.get("training_only") is True
        and ntgs_power.get("paired_training_clusters") == 17
        and ntgs_power.get("required_paired_crps_clusters_conservative") == 106
        and ntgs_power.get("required_clusters_all_metrics") == 223
        and ntgs_power.get("available_correlation_adjusted_test_clusters") == 223
        and ntgs_power.get("wp8_0_power_gate_passes") is True
        and ntgs_power.get("sealed_response_values_interpreted") == 0
        and ntgs_power.get("test_unseal_count") == 0
        and ntgs_power.get("formal_test_result") is None
    ):
        errors.append("ntgs-training-power")
    implementation = readiness.get("implementation", {})
    if (
        implementation.get("entrypoint") != "geodeepbayes.forward.static.TDIPOperator"
        or not implementation.get("dependency_versions")
        or "2-D" not in implementation.get("applicable_dimension", "")
    ):
        errors.append("solver-path")
    reference = readiness.get("independent_reference", {})
    reference_path = ROOT / reference.get("test_path", "")
    if (
        reference.get("passed") is not True
        or reference.get("pytest_exit_code") != 0
        or not reference_path.is_file()
        or reference.get("test_source_sha256") != sha256_file(reference_path)
    ):
        errors.append("reference-path")
    resource = readiness.get("resource_measurement", {})
    records = resource.get("records", [])
    if (
        len(records) < 3
        or resource.get("passed") is not True
        or not all(row.get("finite") for row in records)
        or resource.get("timeout_seconds", 0) <= max(row.get("wall_time_seconds", float("inf")) for row in records)
        or resource.get("memory_limit_bytes", 0) <= max(row.get("peak_python_memory_bytes", float("inf")) for row in records)
    ):
        errors.append("resource-budget")
    if errors:
        raise RuntimeError("TDIP evidence-chain failure: " + ", ".join(errors))
    return {
        "gates": {
            "observation_contract": gate(
                "passed",
                "ABMN, potential/current, delay, 20 windows/durations and paired N/R error evidence validated on 79 training dates",
            ),
            "clusters": gate(
                "passed",
                "NTGS CR2016-0418 supplies exactly 223 sealed receiver-centre "
                "test clusters selected from 247 centres separated by more "
                "than the 250-m training-only correlation range",
            ),
            "power": gate(
                "passed",
                "17 correlation-separated training clusters give a conservative "
                "paired-CRPS requirement of 106; the coverage requirement "
                "dominates at 223 and exactly 223 sealed test clusters are available",
            ),
            "dimensionality": gate(
                "passed",
                "training contract selects repeated 2-D electrode profile; dates and windows are not spatial dimensions or clusters",
            ),
            "solver": gate(
                "passed",
                f"versioned TDIPOperator path frozen for {implementation['applicable_dimension']}",
            ),
            "independent_reference": gate(
                "passed",
                "independent pulse-decay/derivative and three-level discretization tests passed with protected source hash",
            ),
            "resource_budget": gate(
                "passed",
                f"representative wall/peak-memory measured; abort limits frozen at {resource['timeout_seconds']} s and {resource['memory_limit_bytes']} bytes",
            ),
        }
    }


def audit_selected_usarray_mt() -> dict[str, Any]:
    datasets = json.loads(DATASETS.read_text(encoding="utf-8"))
    selected = datasets["methods"]["mt_amt"].get("backup_external", {})
    if selected.get("selection_status") != "selected_and_locally_frozen":
        raise RuntimeError("selected USArray MT backup is not frozen")
    raw_path = MT_RAW / "raw-manifest.json"
    split_path = MT_RAW / "geographic-split.json"
    required = (
        raw_path,
        split_path,
        MT_FREEZE,
        MT_DIAGNOSTICS,
        MT_XML_MANIFEST,
        MT_XML_COVARIANCE,
        MT3D_PATH_READINESS,
        FINAL_AUDIT,
    )
    if any(not path.is_file() for path in required):
        raise RuntimeError("selected USArray MT evidence chain is incomplete")
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    freeze = json.loads(MT_FREEZE.read_text(encoding="utf-8"))
    diagnostic = json.loads(MT_DIAGNOSTICS.read_text(encoding="utf-8"))
    xml_manifest = json.loads(MT_XML_MANIFEST.read_text(encoding="utf-8"))
    covariance = json.loads(MT_XML_COVARIANCE.read_text(encoding="utf-8"))
    mt3d = json.loads(MT3D_PATH_READINESS.read_text(encoding="utf-8"))
    final = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
    errors = []
    if freeze["manifest_sha256"] != sha256_file(raw_path):
        errors.append("raw-manifest-anchor")
    if diagnostic["raw_manifest_sha256"] != sha256_file(raw_path):
        errors.append("diagnostic-raw-anchor")
    if diagnostic["split_manifest_sha256"] != sha256_file(split_path):
        errors.append("diagnostic-split-anchor")
    if raw["member_count"] != 1104 or len(raw["members"]) != 1104:
        errors.append("member-count")
    for member in raw["members"]:
        path = MT_RAW / member["path"]
        if not path.is_file() or path.stat().st_size != member["bytes"] or sha256_file(path) != member["sha256"]:
            errors.append(f"member:{member['spud_id']}")
            break
    if merkle_root(raw["members"]) != raw["member_merkle_root"]:
        errors.append("member-merkle")
    counts = split["counts"]
    if counts != {"train": 361, "buffer": 74, "calibration": 240, "test": 429}:
        errors.append("geographic-split-counts")
    if diagnostic["training_members_interpreted"] != 361:
        errors.append("training-interpretation-count")
    if diagnostic["calibration_members_interpreted"] != 0 or diagnostic["test_members_interpreted"] != 0:
        errors.append("sealed-partition-interpreted")
    if (
        xml_manifest.get("schema_version")
        != "wp8-usarray-ta-xml-raw-manifest-v1"
        or xml_manifest.get("member_count") != 1104
        or len(xml_manifest.get("members", [])) != 1104
        or xml_manifest.get("split_frozen_before_requests") is not True
        or xml_manifest.get("sealed_payloads_interpreted") is not False
    ):
        errors.append("xml-manifest-contract")
    xml_counts = {
        role: sum(member.get("split") == role for member in xml_manifest.get("members", []))
        for role in ("train", "buffer", "calibration", "test")
    }
    if xml_counts != {"train": 361, "buffer": 74, "calibration": 240, "test": 429}:
        errors.append("xml-split-counts")
    for member in xml_manifest.get("members", []):
        path = MT_RAW / member["path"]
        if (
            not path.is_file()
            or path.stat().st_size != member["bytes"]
            or sha256_file(path) != member["sha256"]
        ):
            errors.append(f"xml-member:{member['spud_id']}")
            break
    adapter_path = ROOT / covariance.get("adapter_source", "")
    if (
        covariance.get("schema_version")
        != "wp8-mt-xml-covariance-readiness-v1"
        or covariance.get("passed") is not True
        or covariance.get("raw_member_count") != 1104
        or covariance.get("xml_manifest_sha256") != sha256_file(MT_XML_MANIFEST)
        or covariance.get("role_counts") != xml_counts
        or covariance.get("training_members_interpreted") != 361
        or covariance.get("buffer_members_interpreted") != 0
        or covariance.get("calibration_members_interpreted") != 0
        or covariance.get("test_members_interpreted") != 0
        or covariance.get("sealed_payload_values_read") is not False
        or covariance.get("covariance_periods_checked", 0) <= 0
        or covariance.get("representative_real_stack_off_diagonal_count", 0) <= 0
        or covariance.get("representative_minimum_covariance_eigenvalue", -1) < -1e-12
        or covariance.get("variance_identity_max_relative_error", float("inf")) > 1e-5
        or not adapter_path.is_file()
        or covariance.get("adapter_source_sha256") != sha256_file(adapter_path)
    ):
        errors.append("xml-covariance-contract")
    implementation = mt3d.get("implementation", {})
    reference = mt3d.get("independent_reference", {})
    resource = mt3d.get("resource_measurement", {})
    reference_path = ROOT / reference.get("test_path", "")
    if (
        mt3d.get("schema_version") != "wp8-mt3d-path-readiness-v1"
        or implementation.get("entrypoint")
        != "geodeepbayes.forward.mt3d.MT3DOperator"
        or "3-D" not in implementation.get("applicable_dimension", "")
    ):
        errors.append("mt3d-solver")
    if (
        reference.get("passed") is not True
        or reference.get("pytest_exit_code") != 0
        or not reference_path.is_file()
        or reference.get("test_source_sha256") != sha256_file(reference_path)
    ):
        errors.append("mt3d-reference")
    records = resource.get("records", [])
    if (
        resource.get("passed") is not True
        or len(records) != 3
        or records[-1].get("stations") != 336
        or records[-1].get("frequencies") != 3
        or not all(record.get("finite") for record in records)
        or resource.get("timeout_seconds", 0)
        <= max(record.get("wall_time_seconds", float("inf")) for record in records)
        or resource.get("memory_limit_bytes", 0)
        <= max(record.get("peak_python_memory_bytes", float("inf")) for record in records)
    ):
        errors.append("mt3d-resource")
    seal = final.get("mt_seal_verification", {})
    if (
        seal.get("raw_member_count") != 1104
        or seal.get("calibration_members_interpreted") != 0
        or seal.get("test_members_interpreted") != 0
        or seal.get("test_unseal_count") != 0
    ):
        errors.append("final-audit-seal")
    expected_final_status = {
        "license": "passed",
        "integrity": "passed",
        "contract": "passed",
        "cluster_power": "passed",
        "dimension": "passed",
        "solver": "passed",
        "reference": "passed",
        "resource": "passed",
    }
    actual_final_status = {
        name: value.get("status")
        for name, value in final.get("methods", {}).get("mt_amt", {}).items()
    }
    if actual_final_status != expected_final_status:
        errors.append("final-audit-mt-status-drift")
    if errors:
        raise RuntimeError("USArray MT evidence-chain failure: " + ", ".join(errors))
    return {
        "license_evidence": {
            "passed": True,
            "statement": "1104 official members declare Unrestricted Release with citation and acknowledgement",
            "evidence_path": str(MT_RAW / "raw-manifest.json"),
            "evidence_sha256": sha256_file(raw_path),
        },
        "gates": {
            "license": gate("passed", "USArray TA Unrestricted Release, citation and acknowledgement required"),
            "integrity": gate("passed", f"1104 local SHA-256 members and Merkle root verified ({raw['total_edi_bytes']} bytes)"),
            "observation_contract": gate(
                "passed",
                "official EMTF XML preserves complex Z plus residual/inverse-signal covariance; joint real/imag covariance verified on 10,820 training periods",
            ),
            "clusters": gate("passed", "geographic train/buffer/calibration/test split frozen before EDI access"),
            "power": gate("passed", "sealed geographic test contains 429 independent stations, exceeding coverage requirement 223"),
            "dimensionality": gate("passed", "training-only diagnostics select mandatory 3-D path (336/361 stations classified 3-D)"),
            "solver": gate("passed", "version-frozen MT3DOperator primary-secondary 3-D path verified"),
            "independent_reference": gate(
                "passed", reference["kind"]
            ),
            "resource_budget": gate(
                "passed",
                "three measured scales include 336 stations with frozen timeout/memory abort limits; WP8-0 path evidence only",
            ),
        },
    }


def protected_manifest(output: Path) -> dict[str, Any]:
    members = []
    for path in sorted(output.glob("*.json")):
        if path.name in {"protected-manifest.json", "ACTIVE_MANIFEST.json"}:
            continue
        members.append(
            {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    return {"schema_version": "wp8-protected-manifest-v1", "members": members}


def verify_protected(output: Path) -> tuple[bool, list[str]]:
    path = output / "protected-manifest.json"
    if not path.is_file():
        return False, ["protected manifest missing"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for member in manifest.get("members", []):
        relative = Path(member["path"])
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
            errors.append(f"unsafe-path:{member['path']}")
            continue
        target = output / relative
        if not target.is_file():
            errors.append(f"missing:{member['path']}")
        elif target.stat().st_size != member["bytes"] or sha256_file(target) != member["sha256"]:
            errors.append(f"tampered:{member['path']}")
    return not errors, errors


def verify_active_pointer(output: Path) -> tuple[bool, str]:
    pointer_path = output / "ACTIVE_MANIFEST.json"
    protected_path = output / "protected-manifest.json"
    if not pointer_path.is_file() or not protected_path.is_file():
        return False, "active pointer or protected manifest missing"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    if pointer.get("protected_manifest_sha256") != sha256_file(protected_path):
        return False, "active pointer drift"
    return True, ""


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def _synthetic_content_digest(arrays: dict[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    digest.update(str(arrays["method"].item()).encode("utf-8") + b"\0")
    digest.update(int(arrays["seed"].item()).to_bytes(8, "little", signed=True))
    digest.update(str(arrays["provenance"].item()).encode("utf-8") + b"\0")
    digest.update(
        b"\x01" if bool(arrays["field_validation_eligible"].item()) else b"\x00"
    )
    for value in (
        arrays["cluster_id"],
        arrays["role"].astype("U16"),
        arrays["frequencies_hz"],
        arrays["receiver_xyz_m"],
        arrays["source_vertices_xyz_m"],
        arrays["source_current_a"],
        arrays["response_real"] + 1j * arrays["response_imag"],
        arrays["standard_error"],
    ):
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def _without_wall_clock(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_wall_clock(item)
            for key, item in value.items()
            if key not in {
                "elapsed_ns", "setup_ns", "first_predict_ns",
                "median_warm_ns", "median_warm_scaling_ratio",
            }
        }
    if isinstance(value, list):
        return [_without_wall_clock(item) for item in value]
    return value


_SEMANTIC_REPLAY_IGNORED_KEYS = {
    "elapsed_ns",
    "setup_ns",
    "first_predict_ns",
    "median_warm_ns",
    "median_warm_scaling_ratio",
    # These describe the runner, not the deterministic scientific result.
    "platform",
    "machine",
    "logical_cpu_count",
}
_SEMANTIC_REPLAY_RTOL = 1e-6


def _semantic_replay_equal(
    recorded: Any,
    replayed: Any,
    *,
    threshold: float | None = None,
) -> bool:
    """Compare deterministic semantics across supported CI platforms.

    Structural and categorical values remain exact. Floating-point metrics may
    differ slightly across BLAS/LAPACK and sparse-solver implementations, so
    they use a tight relative tolerance. When a metric has an explicit
    acceptance threshold, the absolute tolerance is capped at five percent of
    that threshold; this permits implementation noise without hiding a
    decision-relevant change.
    """
    if isinstance(recorded, dict) and isinstance(replayed, dict):
        recorded_keys = set(recorded) - _SEMANTIC_REPLAY_IGNORED_KEYS
        replayed_keys = set(replayed) - _SEMANTIC_REPLAY_IGNORED_KEYS
        if recorded_keys != replayed_keys:
            return False
        local_threshold = threshold
        recorded_threshold = recorded.get("threshold")
        replayed_threshold = replayed.get("threshold")
        if (
            _finite_number(recorded_threshold)
            and _finite_number(replayed_threshold)
            and np.isclose(
                float(recorded_threshold),
                float(replayed_threshold),
                rtol=_SEMANTIC_REPLAY_RTOL,
                atol=1e-12,
            )
        ):
            local_threshold = min(
                abs(float(recorded_threshold)),
                abs(float(replayed_threshold)),
            )
        return all(
            _semantic_replay_equal(
                recorded[key],
                replayed[key],
                threshold=local_threshold,
            )
            for key in recorded_keys
        )
    if isinstance(recorded, list) and isinstance(replayed, list):
        return len(recorded) == len(replayed) and all(
            _semantic_replay_equal(left, right, threshold=threshold)
            for left, right in zip(recorded, replayed)
        )
    if isinstance(recorded, bool) or isinstance(replayed, bool):
        return type(recorded) is type(replayed) and recorded == replayed
    if isinstance(recorded, (int, np.integer)) and isinstance(
        replayed, (int, np.integer)
    ):
        return int(recorded) == int(replayed)
    if _finite_number(recorded) and _finite_number(replayed):
        absolute_tolerance = 1e-12
        if threshold is not None:
            absolute_tolerance = max(absolute_tolerance, threshold * 0.05)
        return bool(
            np.isclose(
                float(recorded),
                float(replayed),
                rtol=_SEMANTIC_REPLAY_RTOL,
                atol=absolute_tolerance,
            )
        )
    return type(recorded) is type(replayed) and recorded == replayed


def _finite_json_numbers(value: Any) -> bool:
    if isinstance(value, float):
        return np.isfinite(value)
    if isinstance(value, dict):
        return all(_finite_json_numbers(item) for item in value.values())
    if isinstance(value, list):
        return all(_finite_json_numbers(item) for item in value)
    return True


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and bool(np.isfinite(value))
    )


def _rank_metrics(ranks: Any, posterior_draw_count: int = 99) -> dict[str, Any] | None:
    if (
        not isinstance(ranks, list)
        or len(ranks) == 0
        or not all(
            isinstance(rank, int) and not isinstance(rank, bool)
            and 0 <= rank <= posterior_draw_count
            for rank in ranks
        )
    ):
        return None
    counts, _ = np.histogram(
        np.asarray(ranks), bins=np.linspace(0, posterior_draw_count + 1, 11)
    )
    chi_square, pvalue = stats.chisquare(counts)
    expected = len(ranks) / 10
    return {
        "counts": counts.tolist(),
        "chi_square": float(chi_square),
        "pvalue": float(pvalue),
        "max_z": float(np.max(np.abs(counts - expected)) / np.sqrt(expected)),
    }


def _live_method_validation() -> dict[str, Any]:
    return run_method_synthetic_validation()


def audit_synthetic_phase() -> dict[str, Any]:
    """Fail closed unless the risk acceptance and all synthetic inputs are intact."""
    errors: list[str] = []
    if not WP8_1_START.is_file():
        errors.append("start-record:missing")
        start: dict[str, Any] = {}
    else:
        try:
            loaded_start = json.loads(WP8_1_START.read_text(encoding="utf-8"))
            start = loaded_start if isinstance(loaded_start, dict) else {}
            if not isinstance(loaded_start, dict):
                errors.append("start-record:invalid-type")
        except (OSError, json.JSONDecodeError):
            start = {}
            errors.append("start-record:invalid-json")

    decision_value = start.get("feasibility_decision", {})
    decision = decision_value if isinstance(decision_value, dict) else {}
    authorization_value = start.get("authorization", {})
    authorization = authorization_value if isinstance(authorization_value, dict) else {}
    authorized_scope = start.get("authorized_scope", [])
    prohibitions = start.get("prohibited_until_formal_gates_pass", [])
    expected_scope = {
        "public-interface-implementation",
        "operator-implementation",
        "synthetic-development-and-validation",
        "synthetic-substitutes-for-known-gaps",
        "training-only-power-analysis",
        "wp8-synthetic-completion",
        "wp9-start",
    }
    required_scope = {
        "synthetic-development-and-validation",
        "synthetic-substitutes-for-known-gaps",
    }
    required_prohibitions = {
        "formal-field-test-unsealing",
        "field-validated-claim",
    }
    scope_valid = (
        isinstance(authorized_scope, list)
        and all(isinstance(item, str) for item in authorized_scope)
        and set(authorized_scope) == expected_scope
        and len(authorized_scope) == len(expected_scope)
    )
    prohibitions_valid = (
        isinstance(prohibitions, list)
        and all(isinstance(item, str) for item in prohibitions)
        and required_prohibitions.issubset(prohibitions)
    )
    start_valid = (
        start.get("schema_version") == "wp8-1-synthetic-completion-authorization-v2"
        and start.get("status") == "synthetic-completion-authorized"
        and authorization.get("kind") == "explicit-user-risk-acceptance"
        and authorization.get("field_data_required_for_wp8_completion") is False
        and authorization.get("synthetic_completion_allowed") is True
        and decision.get("status") == "failed"
        and decision.get("passed_methods") == 6
        and decision.get("total_methods") == 9
        and decision.get("wp8_1_allowed") is False
        and decision.get("reason_code") == "WP8_0_NOT_ALL_NINE_PASSED"
        and required_scope.issubset(authorized_scope if scope_valid else [])
        and scope_valid
        and prohibitions_valid
    )
    if not start_valid and not any(item.startswith("start-record:") for item in errors):
        errors.append("start-record:contract-mismatch")

    try:
        loaded_manifest = json.loads(SYNTHETIC_MANIFEST.read_text(encoding="utf-8"))
        manifest = loaded_manifest if isinstance(loaded_manifest, dict) else {}
        if not isinstance(loaded_manifest, dict):
            errors.append("manifest:invalid-type")
    except (OSError, json.JSONDecodeError):
        manifest = {}
        errors.append("manifest:missing-or-invalid")
    members_value = manifest.get("members", [])
    members = members_value if isinstance(members_value, list) else []
    if not isinstance(members_value, list):
        errors.append("manifest:members-invalid-type")
    expected_methods = {"sip_fdip", "csamt", "wfem"}
    member_methods = [member.get("method") for member in members if isinstance(member, dict)]
    member_methods_valid = all(isinstance(method, str) for method in member_methods)
    if (
        manifest.get("schema_version") != "wp8-synthetic-supplements-v1"
        or manifest.get("purpose") != "development-and-synthetic-validation-only"
        or manifest.get("closes_formal_field_gaps") is not False
        or len(members) != 3
        or not member_methods_valid
        or (set(member_methods) if member_methods_valid else set()) != expected_methods
        or (
            len(member_methods) != len(set(member_methods))
            if member_methods_valid
            else True
        )
    ):
        errors.append("manifest:contract-mismatch")

    audited_members = []
    required_keys = {
        "method", "provenance", "field_validation_eligible", "seed",
        "cluster_id", "role", "frequencies_hz", "receiver_xyz_m",
        "source_vertices_xyz_m", "source_current_a", "response_real",
        "response_imag", "standard_error",
    }
    supplement_root = SYNTHETIC_SUPPLEMENTS.resolve()
    for member in members:
        if not isinstance(member, dict):
            errors.append("member:not-an-object")
            continue
        method = member.get("method", "unknown")
        if method not in SYNTHETIC_EXPECTED_SEEDS:
            errors.append("member:unknown-method")
            continue
        relative = member.get("path")
        expected_relative = (
            f"validation/wp8/synthetic/supplements-v1/{method}.npz"
        )
        if not isinstance(relative, str) or relative != expected_relative:
            errors.append(f"{method}:unsafe-path")
            continue
        path = supplement_root / f"{method}.npz"
        expected_path = supplement_root / f"{method}.npz"
        if path != expected_path:
            errors.append(f"{method}:unexpected-path")
            continue
        if not path.is_file():
            errors.append(f"{method}:missing")
            continue
        if path.stat().st_size > SYNTHETIC_MAX_FILE_BYTES:
            errors.append(f"{method}:file-too-large")
            continue
        if sha256_file(path) != member.get("sha256"):
            errors.append(f"{method}:sha256-mismatch")
            continue
        try:
            with zipfile.ZipFile(path) as package:
                entries = package.infolist()
                compressed = sum(item.compress_size for item in entries)
                uncompressed = sum(item.file_size for item in entries)
                unsafe_archive = (
                    len(entries) > len(required_keys)
                    or uncompressed > SYNTHETIC_MAX_UNCOMPRESSED_BYTES
                    or compressed <= 0
                    or uncompressed / compressed > SYNTHETIC_MAX_COMPRESSION_RATIO
                    or any(item.flag_bits & 0x1 for item in entries)
                )
                if unsafe_archive:
                    raise ValueError("unsafe archive bounds")
            with np.load(path, allow_pickle=False) as archive:
                if set(archive.files) != required_keys:
                    raise ValueError("member keys")
                arrays = {key: archive[key] for key in archive.files}
        except (OSError, ValueError, zipfile.BadZipFile):
            errors.append(f"{method}:invalid-npz")
            continue

        cluster_id = arrays["cluster_id"]
        role = arrays["role"].astype("U16")
        frequencies = arrays["frequencies_hz"]
        response_shape = (500, 16)
        contract_ok = (
            arrays["method"].shape == ()
            and str(arrays["method"].item()) == method
            and arrays["provenance"].shape == ()
            and str(arrays["provenance"].item()) == "synthetic-substitute"
            and arrays["field_validation_eligible"].shape == ()
            and bool(arrays["field_validation_eligible"].item()) is False
            and arrays["field_validation_eligible"].dtype.kind == "b"
            and arrays["seed"].shape == ()
            and arrays["seed"].dtype.kind in "iu"
            and int(arrays["seed"].item()) == SYNTHETIC_EXPECTED_SEEDS[method]
            and cluster_id.shape == (500,)
            and cluster_id.dtype.kind in "iu"
            and np.array_equal(cluster_id, np.arange(500))
            and len(np.unique(cluster_id)) == 500
            and role.shape == (500,)
            and np.count_nonzero(role == "training") == 100
            and np.count_nonzero(role == "calibration") == 100
            and np.count_nonzero(role == "test") == 300
            and set(np.unique(role)) == {"training", "calibration", "test"}
            and frequencies.shape == (16,)
            and np.all(np.isfinite(frequencies))
            and np.all(frequencies > 0)
            and np.all(np.diff(frequencies) > 0)
            and arrays["receiver_xyz_m"].shape == (500, 3)
            and arrays["source_vertices_xyz_m"].shape == (500, 2, 3)
            and arrays["source_current_a"].shape == (500,)
            and np.all(arrays["source_current_a"] > 0)
            and np.all(
                np.linalg.norm(
                    arrays["source_vertices_xyz_m"][:, 1, :]
                    - arrays["source_vertices_xyz_m"][:, 0, :],
                    axis=1,
                )
                > 0
            )
            and arrays["response_real"].shape == response_shape
            and arrays["response_imag"].shape == response_shape
            and arrays["standard_error"].shape == response_shape
            and all(
                np.all(np.isfinite(arrays[key]))
                for key in (
                    "receiver_xyz_m", "source_vertices_xyz_m", "source_current_a",
                    "response_real", "response_imag", "standard_error",
                )
            )
            and np.all(arrays["standard_error"] > 0)
            and member.get("clusters") == 500
            and member.get("test_clusters") == 300
            and member.get("frequencies") == 16
            and member.get("provenance") == "synthetic-substitute"
            and member.get("field_validation_eligible") is False
            and _synthetic_content_digest(arrays) == member.get("content_digest")
        )
        if not contract_ok:
            errors.append(f"{method}:contract-mismatch")
            continue
        audited_members.append(
            {"method": method, "sha256": member["sha256"], "contract": "passed"}
        )

    try:
        loaded_policy = json.loads(METHOD_VALIDATION_POLICY.read_text(encoding="utf-8"))
        policy = loaded_policy if isinstance(loaded_policy, dict) else {}
        if not isinstance(loaded_policy, dict):
            errors.append("method-validation-policy:invalid-type")
    except (OSError, json.JSONDecodeError):
        policy = {}
        errors.append("method-validation-policy:missing-or-invalid")
    policy_ok = (
        METHOD_VALIDATION_POLICY.is_file()
        and sha256_file(METHOD_VALIDATION_POLICY)
        == EXPECTED_METHOD_VALIDATION_POLICY_SHA256
        and
        policy.get("schema_version") == "wp8-method-validation-policy-v1"
        and policy.get("required_checks")
        == list(next(iter(REQUIRED_METHOD_CHECKS.values())))
        and isinstance(policy.get("reference_ids"), dict)
        and set(policy.get("reference_ids", {})) == set(REQUIRED_METHOD_CHECKS)
        and isinstance(policy.get("convergence_ids"), dict)
        and set(policy.get("convergence_ids", {})) == set(REQUIRED_METHOD_CHECKS)
        and isinstance(policy.get("adversarial_scenarios"), dict)
        and {
            method: set(values)
            for method, values in policy.get("adversarial_scenarios", {}).items()
            if isinstance(values, list)
        } == ADVERSARIAL_SCENARIOS
    )
    if not policy_ok:
        errors.append("method-validation-policy:contract-drift")

    method_validation: dict[str, Any] = {}
    try:
        loaded_method_validation = json.loads(
            METHOD_SYNTHETIC_EVIDENCE.read_text(encoding="utf-8")
        )
        method_validation = (
            loaded_method_validation
            if isinstance(loaded_method_validation, dict)
            else {}
        )
        if not isinstance(loaded_method_validation, dict):
            errors.append("method-validation:invalid-type")
    except (OSError, json.JSONDecodeError):
        errors.append("method-validation:missing-or-invalid")

    validation_methods = method_validation.get("methods", {})
    method_contract_ok = (
        method_validation.get("schema_version")
        == "wp8-method-synthetic-validation-v1"
        and method_validation.get("status") == "passed"
        and method_validation.get("purpose")
        == "method-level solver development validation only"
        and method_validation.get("provenance")
        == "deterministic-semantics-with-nondeterministic-wall-clock-timings"
        and method_validation.get("field_validation_eligible") is False
        and method_validation.get("closes_formal_field_gaps") is False
        and isinstance(validation_methods, dict)
        and set(validation_methods) == set(REQUIRED_METHOD_CHECKS)
        and all(
            isinstance(result, dict) and isinstance(result.get("checks"), dict)
            for result in validation_methods.values()
        )
        and _finite_json_numbers(method_validation)
    )
    if method_contract_ok:
        producer_path = ROOT / "src/geodeepbayes/validation/wp8_method_synthetic.py"
        if (
            not producer_path.is_file()
            or method_validation.get("producer_source_sha256")
            != sha256_file(producer_path)
        ):
            errors.append("method-validation:producer-source-hash-mismatch")
        bindings = method_validation.get("provenance_bindings", {})
        file_hashes = bindings.get("files_sha256", {}) if isinstance(bindings, dict) else {}
        expected_policy_hash = (
            sha256_file(METHOD_VALIDATION_POLICY)
            if METHOD_VALIDATION_POLICY.is_file()
            else None
        )
        if (
            not isinstance(file_hashes, dict)
            or file_hashes.get(
                "validation/wp8/synthetic/method-validation-policy-v1.json"
            ) != expected_policy_hash
        ):
            errors.append("method-validation:policy-hash-mismatch")
        if isinstance(file_hashes, dict):
            for relative, recorded_hash in file_hashes.items():
                safe_relative = (
                    isinstance(relative, str)
                    and bool(relative)
                    and not Path(relative).is_absolute()
                    and ".." not in Path(relative).parts
                )
                candidate = (ROOT / relative).resolve() if safe_relative else ROOT.parent
                if not safe_relative or ROOT.resolve() not in candidate.parents:
                    errors.append("method-validation:dependency-path-escape")
                    break
                if (
                    not isinstance(recorded_hash, str)
                    or not candidate.is_file()
                    or sha256_file(candidate) != recorded_hash
                ):
                    errors.append("method-validation:dependency-hash-mismatch")
                    break
        if (
            not isinstance(bindings, dict)
            or not isinstance(bindings.get("dependency_versions"), dict)
            or not isinstance(bindings.get("runtime"), dict)
        ):
            errors.append("method-validation:environment-binding-invalid")
        try:
            live_validation = _live_method_validation()
        except Exception:
            errors.append("method-validation:semantic-replay-failed")
        else:
            if not _semantic_replay_equal(method_validation, live_validation):
                errors.append("method-validation:semantic-replay-mismatch")
        for method, required_checks in REQUIRED_METHOD_CHECKS.items():
            result = _object(validation_methods.get(method))
            checks = _object(result.get("checks"))
            if (
                result.get("status") != "passed"
                or result.get("method") != method
                or result.get("required_checks") != list(required_checks)
                or not isinstance(checks, dict)
                or any(
                    _object(checks.get(name)).get("status") != "passed"
                    or _object(checks.get(name)).get("required") is not True
                    for name in required_checks
                )
            ):
                errors.append(f"{method}:method-validation-failed")
            if (
                _object(checks.get("predict_reference_agreement")).get("reference_id")
                != _object(policy.get("reference_ids")).get(method)
                or _object(checks.get("three_level_convergence")).get("convergence_id")
                != _object(policy.get("convergence_ids")).get(method)
            ):
                errors.append(f"{method}:method-identity-crosswire")
            taylor = _object(checks.get("taylor_remainder_order"))
            taylor_metrics = _object(taylor.get("metrics"))
            remainders = taylor_metrics.get("remainders", [])
            normalized_remainders = taylor_metrics.get("normalized_remainders", [])
            observed_orders = taylor_metrics.get("observed_orders")
            normalization_scale = taylor_metrics.get("normalization_scale")
            exact_tolerance = taylor_metrics.get("scale_aware_exact_tolerance")
            taylor_ok = (
                isinstance(remainders, list)
                and len(remainders) == 3
                and all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and np.isfinite(value)
                    and value >= 0
                    for value in remainders
                )
                and isinstance(normalized_remainders, list)
                and len(normalized_remainders) == 3
                and all(_finite_number(value) and value >= 0 for value in normalized_remainders)
                and _finite_number(normalization_scale)
                and normalization_scale > 0
                and _finite_number(exact_tolerance)
                and exact_tolerance >= 0
                and all(
                    np.isclose(normalized, remainder / normalization_scale)
                    for normalized, remainder in zip(normalized_remainders, remainders)
                )
                and taylor_metrics.get("minimum_order") == 1.8
                and (
                    (
                        taylor_metrics.get("order_kind")
                        == "linear_exact_with_scale_aware_tolerance"
                        and observed_orders is None
                        and max(remainders)
                        <= exact_tolerance
                    )
                    or (
                        taylor_metrics.get("order_kind")
                        == "observed_remainder_orders"
                        and isinstance(observed_orders, list)
                        and len(observed_orders) == 2
                        and all(_finite_number(value) for value in observed_orders)
                        and min(observed_orders) > 1.8
                    )
                )
            )
            if not taylor_ok:
                errors.append(f"{method}:taylor-check-invalid")
            if method in {"csamt", "wfem"} and isinstance(checks, dict):
                reference_metrics = _object(_object(checks.get(
                    "predict_reference_agreement"
                )).get("metrics"))
                convergence_metrics = _object(_object(checks.get(
                    "three_level_convergence"
                )).get("metrics"))
                log_error = reference_metrics.get("absolute_log_amplitude_error")
                phase_error = reference_metrics.get("absolute_phase_error_radians")
                medium_error = convergence_metrics.get("medium_to_fine_error")
                coarse_error = convergence_metrics.get("coarse_to_fine_error")
                numeric_contract_ok = (
                    reference_metrics.get("log_amplitude_error_threshold") == 0.65
                    and reference_metrics.get("case_frequencies_hz") == [2.0, 5.0, 10.0]
                    and reference_metrics.get("case_receiver_xyz_m")
                    == [[35.0, 5.0, -8.0], [50.0, -7.0, -15.0]]
                    and reference_metrics.get("sanity_reference")
                    == "geoana.em.fdem.ElectricDipoleWholeSpace uniform whole-space"
                    and reference_metrics.get("phase_error_threshold_radians") == 0.01
                    and all(
                        isinstance(value, (int, float)) and not isinstance(value, bool)
                        for value in (log_error, phase_error, medium_error, coarse_error)
                    )
                    and log_error < 0.65
                    and phase_error < 0.01
                    and medium_error < coarse_error
                )
                if not numeric_contract_ok:
                    errors.append(f"{method}:method-validation-metrics-invalid")
            if isinstance(checks, dict):
                adversarial = _object(_object(checks.get(
                    "method_adversarial_suite"
                )).get("metrics"))
                scenarios = adversarial.get("scenarios", {})
                expected_scenarios = set(
                    _object(policy.get("adversarial_scenarios")).get(method, [])
                )
                if not isinstance(scenarios, dict) or set(scenarios) != expected_scenarios:
                    errors.append(f"{method}:adversarial-suite-invalid")

                sbc = _object(_object(checks.get("sbc_at_least_400")).get("metrics"))
                counts = sbc.get("counts", [])
                ranks = sbc.get("raw_ranks", [])
                recomputed = _rank_metrics(ranks)
                per_seed = sbc.get("per_seed", [])
                per_seed_recomputed = [
                    _rank_metrics(_object(item).get("raw_ranks"))
                    for item in per_seed
                ] if isinstance(per_seed, list) else []
                sbc_ok = (
                    sbc.get("repetitions") == 800
                    and sbc.get("reference_kind")
                    == "operator-sensitivity-conditioned scalar Gaussian reference rank test; not method-posterior calibration"
                    and sbc.get("repetitions_per_seed") == 400
                    and sbc.get("posterior_draw_count") == 99
                    and isinstance(counts, list)
                    and len(counts) == 10
                    and all(isinstance(count, int) and count >= 0 for count in counts)
                    and sum(counts) == 800
                    and isinstance(ranks, list)
                    and len(ranks) == 800
                    and all(isinstance(rank, int) and 0 <= rank <= 99 for rank in ranks)
                    and sbc.get("pvalue_threshold") == 0.01 / 27
                    and isinstance(sbc.get("pvalue"), (int, float))
                    and sbc["pvalue"] >= 0.01 / 27
                    and sbc.get("max_standardized_bin_deviation_threshold") == 4.0
                    and isinstance(
                        sbc.get("max_standardized_bin_deviation"), (int, float)
                    )
                    and sbc["max_standardized_bin_deviation"] < 4.0
                    and recomputed is not None
                    and counts == recomputed["counts"]
                    and _finite_number(sbc.get("chi_square"))
                    and np.isclose(sbc.get("chi_square"), recomputed["chi_square"])
                    and np.isclose(sbc.get("pvalue"), recomputed["pvalue"])
                    and np.isclose(
                        sbc.get("max_standardized_bin_deviation"),
                        recomputed["max_z"],
                    )
                    and sbc.get("seeds") == METHOD_SBC_SEEDS[method]
                    and isinstance(per_seed, list)
                    and len(per_seed) == 2
                    and all(
                        isinstance(item, dict)
                        and item.get("seed") == METHOD_SBC_SEEDS[method][index]
                        and item.get("repetitions") == 400
                        and metric is not None
                        and item.get("counts") == metric["counts"]
                        and _finite_number(item.get("chi_square"))
                        and np.isclose(item.get("chi_square"), metric["chi_square"])
                        and _finite_number(item.get("pvalue"))
                        and np.isclose(item.get("pvalue"), metric["pvalue"])
                        and item["pvalue"] >= 0.01 / 27
                        for index, (item, metric) in enumerate(
                            zip(per_seed, per_seed_recomputed)
                        )
                    )
                    and ranks == [
                        rank
                        for item in per_seed
                        for rank in item["raw_ranks"]
                    ]
                )
                if not sbc_ok:
                    errors.append(f"{method}:sbc-invalid")

                benchmark = _object(_object(checks.get(
                    "within_method_5x5_performance"
                )).get("metrics"))
                records = benchmark.get("records", [])
                cold_records = benchmark.get("cold_scale_records", [])
                recomputed_medians = (
                    [
                        float(np.median([
                            record["elapsed_ns"]
                            for record in records
                            if isinstance(record, dict)
                            and record.get("scale") == scale
                            and _finite_number(record.get("elapsed_ns"))
                        ]))
                        for scale in range(1, 6)
                    ]
                    if isinstance(records, list)
                    and all(
                        sum(
                            1 for record in records
                            if isinstance(record, dict)
                            and record.get("scale") == scale
                            and _finite_number(record.get("elapsed_ns"))
                        ) == 5
                        for scale in range(1, 6)
                    )
                    else []
                )
                recomputed_scaling_ratio = (
                    max(recomputed_medians) / max(min(recomputed_medians), 1)
                    if len(recomputed_medians) == 5
                    else None
                )
                benchmark_ok = (
                    benchmark.get("scale_count") == 5
                    and benchmark.get("repetitions_per_scale") == 5
                    and benchmark.get("record_count") == 25
                    and benchmark.get("cross_method_ranking_forbidden") is True
                    and benchmark.get("persistence_scope")
                    == "historical runtime smoke record only"
                    and benchmark.get("timings_replay_bound") is False
                    and benchmark.get("cross_run_timing_audit_forbidden") is True
                    and isinstance(records, list)
                    and len(records) == 25
                    and isinstance(cold_records, list)
                    and len(cold_records) == 5
                    and all(
                        isinstance(record, dict)
                        and record.get("scale") == index
                        and isinstance(record.get("setup_ns"), int)
                        and 0 < record["setup_ns"] <= 5_000_000_000
                        and record.get("max_setup_ns") == 5_000_000_000
                        and isinstance(record.get("first_predict_ns"), int)
                        and 0 < record["first_predict_ns"] <= 5_000_000_000
                        and record.get("max_first_predict_ns") == 5_000_000_000
                        for index, record in enumerate(cold_records, start=1)
                    )
                    and isinstance(benchmark.get("median_warm_scaling_ratio"), (int, float))
                    and benchmark["median_warm_scaling_ratio"] < 1000.0
                    and benchmark.get("max_median_warm_scaling_ratio") == 1000.0
                    and {
                        (record.get("scale"), record.get("repeat"))
                        for record in records
                        if isinstance(record, dict)
                    }
                    == {
                        (scale, repeat)
                        for scale in range(1, 6)
                        for repeat in range(1, 6)
                    }
                    and all(
                        isinstance(record, dict)
                        and isinstance(record.get("elapsed_ns"), int)
                        and not isinstance(record.get("elapsed_ns"), bool)
                        and record["elapsed_ns"] > 0
                        and record.get("max_elapsed_ns") == 2_000_000_000
                        and record["elapsed_ns"] <= record["max_elapsed_ns"]
                        and record.get("finite") is True
                        and isinstance(record.get("size_definition"), dict)
                        and isinstance(record.get("n_param"), int)
                        and not isinstance(record.get("n_param"), bool)
                        and record["n_param"] > 0
                        and isinstance(record.get("n_data"), int)
                        and not isinstance(record.get("n_data"), bool)
                        and record["n_data"] > 0
                        for record in records
                    )
                    and all(
                        _finite_number(_object(record).get("median_warm_ns"))
                        and np.isclose(
                            _object(record).get("median_warm_ns"),
                            recomputed_medians[index],
                        )
                        for index, record in enumerate(cold_records)
                    )
                    and recomputed_scaling_ratio is not None
                    and np.isclose(
                        benchmark["median_warm_scaling_ratio"],
                        recomputed_scaling_ratio,
                    )
                )
                if benchmark_ok:
                    for record in records:
                        scale = record["scale"]
                        size = record["size_definition"]
                        if method in {"gravity", "magnetic"}:
                            expected_size = (
                                size == {
                                    "cells_per_axis": scale + 2,
                                    "mesh_cells": (scale + 2) ** 3,
                                }
                                and record["n_param"] == (scale + 2) ** 3
                                and record["n_data"] == 1
                            )
                        elif method in {"dc", "tdip"}:
                            expected_size = (
                                size == {
                                    "cells_per_axis": scale + 2,
                                    "mesh_cells": (scale + 2) ** 3,
                                }
                                and record["n_param"] == (scale + 2) ** 3
                                and record["n_data"] == (1 if method == "dc" else 2)
                            )
                        elif method in {"tem", "mt_amt"}:
                            key = "time_count" if method == "tem" else "frequency_count"
                            expected_size = (
                                size == {"layer_count": scale + 1, key: scale + 2}
                                and record["n_param"] == scale + 1
                                and record["n_data"] == scale + 2
                            )
                        elif method == "sip_fdip":
                            expected_size = (
                                size == {"frequency_count": 2**scale}
                                and record["n_param"] == 4
                                and record["n_data"] == 2**scale
                            )
                        else:
                            expected_size = (
                                size == {"receiver_count": scale, "mesh_cells": 216}
                                and record["n_param"] == 216
                                and record["n_data"] == 2 * scale
                            )
                        if not expected_size:
                            benchmark_ok = False
                            break
                if not benchmark_ok:
                    errors.append(f"{method}:performance-benchmark-invalid")
    else:
        errors.append("method-validation:contract-mismatch")

    try:
        loaded_readiness = json.loads(SYNTHETIC_READINESS.read_text(encoding="utf-8"))
        readiness = loaded_readiness if isinstance(loaded_readiness, dict) else {}
        if not isinstance(loaded_readiness, dict):
            errors.append("synthetic-readiness:invalid-type")
    except (OSError, json.JSONDecodeError):
        readiness = {}
        errors.append("synthetic-readiness:missing-or-invalid")
    canonical_checks = list(next(iter(REQUIRED_METHOD_CHECKS.values())))
    readiness_methods = readiness.get("methods", {}) if isinstance(readiness, dict) else {}
    readiness_ok = (
        readiness.get("schema_version") == "wp8-synthetic-readiness-v1"
        and readiness.get("formal_synthetic_run") is False
        and readiness.get("reason") == policy.get("readiness_reason")
        and readiness.get("required_checks") == canonical_checks
        and isinstance(readiness_methods, dict)
        and set(readiness_methods) == set(REQUIRED_METHOD_CHECKS)
        and all(
            isinstance(readiness_methods.get(method), dict)
            and readiness_methods[method].get("implemented") == list(checks)
            and readiness_methods[method].get("status")
            == "development-synthetic-ready-field-blocked"
            and (
                readiness_methods[method].get("scope") == "tem_1d_layered"
                if method == "tem"
                else "scope" not in readiness_methods[method]
            )
            for method, checks in REQUIRED_METHOD_CHECKS.items()
        )
    )
    if not readiness_ok:
        errors.append("synthetic-readiness:contract-drift")

    return {
        "phase": "synthetic",
        "status": "passed" if not errors else "blocked",
        "reason_code": (
            "SYNTHETIC_COMPLETION_AUTHORIZED"
            if not errors
            else "SYNTHETIC_INPUT_VALIDATION_FAILED"
        ),
        "use": "wp8-synthetic-completion",
        "wp8_completion_allowed": not errors,
        "wp9_start_allowed": not errors,
        "formal_feasibility": {
            "passed_methods": 6,
            "total_methods": 9,
            "wp8_1_allowed": False,
        },
        "start_record_valid": start_valid,
        "members": audited_members,
        "method_validation": method_validation,
        "errors": errors,
        "field_phase": "not-required-for-synthetic-completion",
        "field_validated_claim_created": False,
    }


def run_synthetic() -> int:
    report = audit_synthetic_phase()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 4


def _live_authoritative_feasibility(
    generated_at_utc: str,
    *,
    maximum_wall_seconds: float = 180.0,
    maximum_peak_bytes: int = 512 * 1024 * 1024,
    maximum_input_bytes: int = 512 * 1024 * 1024,
    monitor_python_memory: bool = False,
) -> dict[str, Any]:
    """Rebuild the structural decision from original protected assets in-process."""
    started = time.monotonic()
    core_paths = (MANIFEST, DATASETS, PREREG, FIELD_CONTRACT_AUDIT, REGISTRATION_SCHEMA)
    core_bytes = sum(path.stat().st_size for path in core_paths)
    if core_bytes > maximum_input_bytes:
        raise RuntimeError("authoritative replay input byte budget exceeded")
    if monitor_python_memory:
        tracemalloc.start()
    manifest = json.loads(MANIFEST.read_bytes())
    datasets = json.loads(DATASETS.read_bytes())
    audit = audit_manifest(manifest)
    module_spec = importlib.util.spec_from_file_location(
        "_wp8_live_field_contracts", WP8 / "audit_field_contracts.py"
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("authoritative field-contract audit cannot be loaded")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    field_audit = json.loads(json.dumps(module.build_field_contract_audit(
        maximum_input_bytes=maximum_input_bytes - core_bytes
    )))
    frozen_field_audit = json.loads(FIELD_CONTRACT_AUDIT.read_bytes())
    if field_audit != frozen_field_audit:
        raise RuntimeError("derived field-contract audit differs from live raw-member replay")
    if (
        time.monotonic() - started > maximum_wall_seconds
        or (
            monitor_python_memory
            and tracemalloc.get_traced_memory()[1] > maximum_peak_bytes
        )
    ):
        raise RuntimeError("authoritative replay resource budget exceeded")
    registration = make_registration(manifest, datasets, audit, field_audit)
    schema = json.loads(REGISTRATION_SCHEMA.read_bytes())
    jsonschema.Draft202012Validator(schema).validate(registration)
    decision = evaluate_feasibility(
        registration,
        expected_registration_hashes={
            "manifest_sha256": sha256_file(MANIFEST),
            "dataset_selection_sha256": sha256_file(DATASETS),
            "preregistration_sha256": sha256_file(PREREG),
        },
        trusted_producers={
            "src/geodeepbayes/validation/feasibility.py": sha256_file(
                ROOT / "src/geodeepbayes/validation/feasibility.py"
            )
        },
    )
    decision["generated_at_utc"] = generated_at_utc
    decision["reason_code"] = (
        "ALL_NINE_FEASIBLE"
        if decision["status"] == "passed"
        else "WP8_0_NOT_ALL_NINE_PASSED"
    )
    if (
        time.monotonic() - started > maximum_wall_seconds
        or (
            monitor_python_memory
            and tracemalloc.get_traced_memory()[1] > maximum_peak_bytes
        )
    ):
        raise RuntimeError("authoritative replay resource budget exceeded")
    if monitor_python_memory:
        tracemalloc.stop()
    return decision


def _best_effort_worker_cleanup(
    process: Any, *, kernel32: Any | None = None, job_handle: Any | None = None
) -> None:
    """Attempt kill, reap, and handle close independently; never mask the caller error."""
    try:
        process.kill()
    except BaseException:
        pass
    try:
        process.communicate()
    except BaseException:
        pass
    if kernel32 is not None and job_handle:
        try:
            kernel32.CloseHandle(job_handle)
        except BaseException:
            pass


def _install_windows_memory_job(
    process: Any, *, kernel32: Any | None = None
) -> tuple[Any, Any]:
    """Install a 512 MiB Job Object or kill/reap the worker on any stage failure."""
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class BASIC_LIMIT(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = (
        ("CreateJobObjectW", [ctypes.c_void_p, ctypes.c_wchar_p], ctypes.c_void_p),
        ("SetInformationJobObject",
         [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        ("AssignProcessToJobObject",
         [ctypes.c_void_p, ctypes.c_void_p], wintypes.BOOL),
        ("CloseHandle", [ctypes.c_void_p], wintypes.BOOL),
    )
    for name, argtypes, restype in signatures:
        function = getattr(kernel32, name)
        function.argtypes, function.restype = argtypes, restype
    handle = kernel32.CreateJobObjectW(None, None)
    try:
        if not handle:
            raise RuntimeError("WINDOWS_JOB_CREATE_FAILED")
        information = EXTENDED_LIMIT()
        information.BasicLimitInformation.LimitFlags = 0x100 | 0x2000
        information.ProcessMemoryLimit = 512 * 1024 * 1024
        if not kernel32.SetInformationJobObject(
            handle, 9, ctypes.byref(information), ctypes.sizeof(information)
        ):
            raise RuntimeError("WINDOWS_JOB_SET_LIMIT_FAILED")
        if not kernel32.AssignProcessToJobObject(
            handle, ctypes.c_void_p(int(process._handle))
        ):
            raise RuntimeError("WINDOWS_JOB_ASSIGN_FAILED")
        return handle, kernel32
    except BaseException:
        _best_effort_worker_cleanup(
            process, kernel32=kernel32, job_handle=handle
        )
        raise


def _bounded_authoritative_feasibility(
    generated_at_utc: str,
    *,
    popen_factory: Any = subprocess.Popen,
    platform_name: str = os.name,
    timeout_seconds: float = 180.0,
) -> dict[str, Any]:
    """Run replay in a killable worker; timeout is a hard authorization failure."""
    deadline = time.monotonic() + timeout_seconds
    command = [
        sys.executable, str(Path(__file__).resolve()),
        "--phase", "authoritative-replay",
    ]
    if platform_name != "nt":
        command.extend(["--generated-at-utc", generated_at_utc])
    preexec_fn = None
    if platform_name != "nt":
        def limit_address_space() -> None:
            import resource
            maximum = 512 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (maximum, maximum))
        preexec_fn = limit_address_space
    process = popen_factory(
        command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, preexec_fn=preexec_fn,
    )
    job_handle = None
    if platform_name == "nt":
        ready_queue: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)
        def read_ready() -> None:
            try:
                ready_queue.put(
                    process.stdout.readline().strip()
                    if process.stdout is not None else RuntimeError("stdout unavailable")
                )
            except BaseException as error:
                ready_queue.put(error)
        threading.Thread(target=read_ready, daemon=True).start()
        try:
            ready = ready_queue.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty as error:
            process.kill()
            process.communicate()
            raise subprocess.TimeoutExpired(command, timeout_seconds) from error
        if isinstance(ready, BaseException) or ready != "READY":
            process.kill()
            process.communicate()
            raise RuntimeError("authoritative replay worker did not become ready")
        job_handle, kernel32 = _install_windows_memory_job(process)
        try:
            if process.stdin is None:
                raise RuntimeError("authoritative replay worker stdin unavailable")
            process.stdin.write(generated_at_utc + "\n")
            process.stdin.flush()
            process.stdin.close()
            process.stdin = None
        except BaseException:
            _best_effort_worker_cleanup(
                process, kernel32=kernel32, job_handle=job_handle
            )
            job_handle = None
            raise
    try:
        stdout, stderr = process.communicate(
            timeout=max(0.0, deadline - time.monotonic())
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise
    finally:
        if job_handle is not None:
            kernel32.CloseHandle(job_handle)
    if process.returncode != 0:
        raise RuntimeError(
            f"authoritative replay worker failed with exit {process.returncode}: "
            f"{stderr[-500:]}"
        )
    value = json.loads(stdout)
    if not isinstance(value, dict):
        raise TypeError("authoritative replay result must be an object")
    return value


class LiveReplayMismatch(ValueError):
    """Frozen decision differs from a successfully completed live replay."""


def audit_field_preregistration_scaffold() -> dict[str, Any]:
    """Audit only the frozen pre-unseal scaffold; never read field endpoints."""
    try:
        schema_bytes = FIELD_PREREGISTRATION_SCHEMA.read_bytes()
        payload_bytes = FIELD_PREREGISTRATION_SCAFFOLD.read_bytes()
        if (
            hashlib.sha256(schema_bytes).hexdigest()
            != EXPECTED_FIELD_PREREGISTRATION_SCHEMA_SHA256
            or hashlib.sha256(payload_bytes).hexdigest()
            != EXPECTED_FIELD_PREREGISTRATION_PAYLOAD_SHA256
        ):
            raise ValueError("field scaffold anchor mismatch")
        payload = json.loads(payload_bytes)
        schema = json.loads(schema_bytes)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(payload)
        decision_path = EVIDENCE / "decision.json"
        protected_path = EVIDENCE / "protected-manifest.json"
        protected_bytes = protected_path.read_bytes()
        decision_bytes = decision_path.read_bytes()
        decision_sha256 = hashlib.sha256(decision_bytes).hexdigest()
        protected = json.loads(protected_bytes)
        if not isinstance(protected, dict):
            raise ValueError("protected manifest must be an object")
        decision_members = [
            item for item in protected.get("members", [])
            if isinstance(item, dict) and item.get("path") == "decision.json"
        ]
        if (
            len(decision_members) != 1
            or decision_members[0].get("sha256") != decision_sha256
            or decision_members[0].get("bytes") != len(decision_bytes)
        ):
            raise ValueError("protected manifest does not bind the feasibility decision")
        decision = json.loads(decision_bytes)
        if not isinstance(decision, dict):
            raise ValueError("feasibility decision must be an object")
        live_decision = _bounded_authoritative_feasibility(
            str(decision.get("generated_at_utc", ""))
        )
        live_bytes = (
            json.dumps(live_decision, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        if b"\r\n" in decision_bytes:
            live_bytes = live_bytes.replace(b"\n", b"\r\n")
        if live_bytes != decision_bytes:
            raise LiveReplayMismatch(
                "live authoritative feasibility replay differs from frozen decision; "
                "SHA-256 is an integrity digest, not a producer signature"
            )
        result = validate_field_preregistration(
            payload,
            feasibility_decision=decision,
            feasibility_decision_sha256=decision_sha256,
            protected_manifest_sha256=hashlib.sha256(protected_bytes).hexdigest(),
        )
    except LiveReplayMismatch:
        return {
            "phase": "field", "status": "blocked",
            "reason_code": "LIVE_REPLAY_MISMATCH",
            "wp8_1_allowed": False, "field_validated_claim_created": False,
        }
    except (
        OSError, ValueError, RuntimeError, TypeError, AttributeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        jsonschema.ValidationError, jsonschema.SchemaError,
    ):
        return {
            "phase": "field",
            "status": "blocked",
            "reason_code": "FIELD_PREREGISTRATION_SCAFFOLD_INVALID",
            "wp8_1_allowed": False,
            "field_validated_claim_created": False,
        }
    return {
        "phase": "field",
        **result,
        "use": "field-validation-prohibited",
        "wp8_1_allowed": False,
        "field_validated_claim_created": False,
    }


def run_feasibility(self_test: bool) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    datasets = json.loads(DATASETS.read_text(encoding="utf-8"))
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    expected_preregistration = {
        "frozen": True,
        "test_endpoints_viewed": False,
        "selection_policy": "license_integrity_design_only",
        "alpha_one_sided": 0.05,
        "minimum_power": 0.8,
        "minimum_relative_crps_improvement": 0.1,
        "coverage_equivalence_margin_percentage_points": 5,
        "cluster_is_inference_unit": True,
        "small_cluster_test": "exact_paired_randomization",
        "bootstrap_requires_stability_check": True,
        "dimensionality_upgrade_required_when_indicated": True,
        "field_test_unseal_limit": 1,
        "intent_to_analyze_all_preregistered_clusters": True,
    }
    preregistration_errors = [
        key for key, expected in expected_preregistration.items()
        if prereg.get(key) != expected
    ]
    if preregistration_errors:
        raise RuntimeError(
            "preregistration invariant failure: " + ", ".join(preregistration_errors)
        )

    audit = audit_manifest(manifest)
    if not FIELD_CONTRACT_AUDIT.is_file():
        raise RuntimeError(
            "outcome-blind field-contract audit missing; run "
            "validation/wp8/audit_field_contracts.py first"
        )
    field_audit = json.loads(FIELD_CONTRACT_AUDIT.read_text(encoding="utf-8"))
    if field_audit.get("observation_values_read_by_this_program") is not False:
        raise RuntimeError("field-contract audit is not outcome-blind")
    contract_inventory = audit_observation_contracts(manifest, datasets)
    solver_inventory = audit_solver_paths()
    sbc_qois = {
        "gravity": "density_contrast",
        "magnetic": "effective_susceptibility",
        "dc": "log_conductivity",
        "tdip": "chargeability",
        "sip_fdip": "cole_cole_eta",
        "tem": "layer_log_conductivity",
        "mt_amt": "layer_log_conductivity",
        "csamt": "cell_log_conductivity",
        "wfem": "cell_log_conductivity",
    }
    development_sbc = {
        "schema_version": "wp8-development-sbc-v1",
        "formal_wp8_1_evidence": False,
        "reason": "WP8-0 has not passed",
        "methods": {
            method: normal_conjugate_reference_sbc(
                seed=8800 + index,
                sensitivity=0.5 + index / 10,
                qoi=sbc_qois[method],
            )
            for index, method in enumerate(METHOD_NAMES)
        },
    }
    registration = make_registration(manifest, datasets, audit, field_audit)
    schema = json.loads(REGISTRATION_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(registration)
    decision = evaluate_feasibility(
        registration,
        expected_registration_hashes={
            "manifest_sha256": sha256_file(MANIFEST),
            "dataset_selection_sha256": sha256_file(DATASETS),
            "preregistration_sha256": sha256_file(PREREG),
        },
        trusted_producers={
            "src/geodeepbayes/validation/feasibility.py": sha256_file(
                ROOT / "src/geodeepbayes/validation/feasibility.py"
            )
        },
    )
    decision["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    decision["reason_code"] = (
        "ALL_NINE_FEASIBLE" if decision["status"] == "passed" else "WP8_0_NOT_ALL_NINE_PASSED"
    )

    write_json(EVIDENCE / "member-audit.json", audit)
    write_json(EVIDENCE / "observation-contract-inventory.json", contract_inventory)
    write_json(EVIDENCE / "solver-resource-inventory.json", solver_inventory)
    write_json(EVIDENCE / "development-sbc-raw-ranks.json", development_sbc)
    write_json(EVIDENCE / "registration.json", registration)
    write_json(EVIDENCE / "decision.json", decision)
    write_json(
        EVIDENCE / "gate-failure-inventory.json",
        {
            "schema_version": "wp8-gate-failure-inventory-v1",
            "formal_test_eligibility": field_audit["formal_test_eligibility"],
            "endpoint_exposure_incident": field_audit["endpoint_exposure_incident"],
            "methods": {
                item["method"]: {
                    reason["code"].removesuffix("_NOT_PASSED").lower(): reason["detail"]
                    for reason in item["reasons"]
                }
                for item in decision["methods"]
            },
        },
    )
    write_json(
        EVIDENCE / "producer-manifest.json",
        {
            "schema_version": "wp8-producer-manifest-v1",
            "members": [
                {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256_file(path)}
                for path in (
                    MANIFEST,
                    DATASETS,
                    PREREG,
                    REGISTRATION_SCHEMA,
                    FIELD_CONTRACT_AUDIT,
                    MT_RAW / "raw-manifest.json",
                    MT_RAW / "geographic-split.json",
                    MT_FREEZE,
                    MT_DIAGNOSTICS,
                    TDIP_SPLIT,
                    TDIP_DIAGNOSTICS,
                    TDIP_PATH_READINESS,
                    FINAL_AUDIT,
                )
            ],
        },
    )

    self_test_result = {
        "intact_package_accepted": None,
        "tampered_package_rejected": None,
        "active_pointer_drift_rejected": None,
        "tampered_final_audit_rejected": None,
        "tampered_mt_raw_rejected": None,
        "tampered_mt_split_rejected": None,
        "tampered_mt_diagnostics_rejected": None,
    }
    write_json(EVIDENCE / "self-test.json", self_test_result)
    evidence_members = [
        {
            "path": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(EVIDENCE.glob("*.json"))
        if path.name not in {"evidence-manifest.json", "protected-manifest.json", "ACTIVE_MANIFEST.json"}
    ]
    write_json(
        EVIDENCE / "evidence-manifest.json",
        {"schema_version": "wp8-evidence-manifest-v1", "members": evidence_members},
    )
    write_json(EVIDENCE / "protected-manifest.json", protected_manifest(EVIDENCE))
    write_json(
        EVIDENCE / "ACTIVE_MANIFEST.json",
        {
            "schema_version": "wp8-active-pointer-v1",
            "protected_manifest_sha256": sha256_file(EVIDENCE / "protected-manifest.json"),
        },
    )
    intact, errors = verify_protected(EVIDENCE)
    active_ok, _ = verify_active_pointer(EVIDENCE)
    self_test_result["intact_package_accepted"] = intact and active_ok
    if self_test:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            for source in EVIDENCE.glob("*.json"):
                (fixture / source.name).write_bytes(source.read_bytes())
            decision_fixture = fixture / "decision.json"
            mutated = json.loads(decision_fixture.read_text(encoding="utf-8"))
            mutated["status"] = "passed"
            write_json(decision_fixture, mutated)
            rejected, _ = verify_protected(fixture)
            self_test_result["tampered_package_rejected"] = not rejected
            pointer_fixture = fixture / "ACTIVE_MANIFEST.json"
            pointer = json.loads(pointer_fixture.read_text(encoding="utf-8"))
            pointer["protected_manifest_sha256"] = "0" * 64
            write_json(pointer_fixture, pointer)
            pointer_ok, _ = verify_active_pointer(fixture)
            self_test_result["active_pointer_drift_rejected"] = not pointer_ok
            # Protected evidence members: final audit and MT diagnostics.
            for name, result_key in (
                ("final-requirement-audit.json", "tampered_final_audit_rejected"),
                ("mt-usarray-train-diagnostics.json", "tampered_mt_diagnostics_rejected"),
            ):
                target = fixture / name
                original = target.read_bytes()
                target.write_bytes(original + b"\n")
                accepted, _ = verify_protected(fixture)
                self_test_result[result_key] = not accepted
                target.write_bytes(original)
            # Raw/split anchors are checked without interpreting endpoint values.
            raw_manifest = json.loads((MT_RAW / "raw-manifest.json").read_text(encoding="utf-8"))
            first = raw_manifest["members"][0]
            raw_fixture = fixture / "raw-member.edi"
            raw_fixture.write_bytes((MT_RAW / first["path"]).read_bytes())
            raw_fixture.write_bytes(raw_fixture.read_bytes() + b"\n")
            self_test_result["tampered_mt_raw_rejected"] = sha256_file(raw_fixture) != first["sha256"]
            split_fixture = fixture / "geographic-split.json"
            split_fixture.write_bytes((MT_RAW / "geographic-split.json").read_bytes() + b"\n")
            diagnostics = json.loads(MT_DIAGNOSTICS.read_text(encoding="utf-8"))
            self_test_result["tampered_mt_split_rejected"] = (
                sha256_file(split_fixture) != diagnostics["split_manifest_sha256"]
            )
    write_json(EVIDENCE / "self-test.json", self_test_result)
    # Self-test and evidence manifest are protected; refresh both after results.
    evidence_members = [
        {"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(EVIDENCE.glob("*.json"))
        if path.name not in {"evidence-manifest.json", "protected-manifest.json", "ACTIVE_MANIFEST.json"}
    ]
    write_json(EVIDENCE / "evidence-manifest.json", {"schema_version": "wp8-evidence-manifest-v1", "members": evidence_members})
    write_json(EVIDENCE / "protected-manifest.json", protected_manifest(EVIDENCE))
    write_json(EVIDENCE / "ACTIVE_MANIFEST.json", {"schema_version": "wp8-active-pointer-v1", "protected_manifest_sha256": sha256_file(EVIDENCE / "protected-manifest.json")})
    intact, errors = verify_protected(EVIDENCE)
    active_ok, _ = verify_active_pointer(EVIDENCE)

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    if errors or not intact or not active_ok or (
        self_test
        and not (
            self_test_result["tampered_package_rejected"]
            and self_test_result["active_pointer_drift_rejected"]
            and self_test_result["tampered_final_audit_rejected"]
            and self_test_result["tampered_mt_raw_rejected"]
            and self_test_result["tampered_mt_split_rejected"]
            and self_test_result["tampered_mt_diagnostics_rejected"]
        )
    ):
        return 2
    # A correct fail-closed gate uses a non-zero exit when WP8-0 does not pass.
    return 0 if decision["wp8_1_allowed"] else 3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("feasibility", "synthetic", "field", "authoritative-replay"),
        required=True,
    )
    parser.add_argument("--generated-at-utc")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.phase == "authoritative-replay":
        generated_at = args.generated_at_utc
        if generated_at is None and os.name == "nt":
            print("READY", flush=True)
            generated_at = sys.stdin.readline().rstrip("\r\n")
        if not generated_at:
            parser.error("--generated-at-utc or worker stdin value is required")
        print(json.dumps(
            _live_authoritative_feasibility(generated_at),
            ensure_ascii=False,
        ))
        return 0
    if args.phase == "synthetic":
        return run_synthetic()
    if args.phase == "field":
        print(json.dumps(audit_field_preregistration_scaffold()))
        return 4
    return run_feasibility(args.self_test)


if __name__ == "__main__":
    sys.exit(main())
