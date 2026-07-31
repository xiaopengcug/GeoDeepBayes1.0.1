#!/usr/bin/env python
"""Produce the final WP8-0 requirement-by-requirement blocker audit."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"
RAW = ROOT / "validation/wp8/data/usarray-ta-emtf-v1"
METHODS = ("gravity", "magnetic", "dc", "tdip", "sip_fdip", "tem", "mt_amt", "csamt", "wfem")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merkle(leaves: list[dict[str, object]]) -> str:
    nodes = [
        hashlib.sha256(json.dumps(leaf, sort_keys=True, separators=(",", ":")).encode()).digest()
        for leaf in leaves
    ]
    while len(nodes) > 1:
        if len(nodes) % 2:
            nodes.append(nodes[-1])
        nodes = [hashlib.sha256(nodes[i] + nodes[i + 1]).digest() for i in range(0, len(nodes), 2)]
    return nodes[0].hex()


def gate(status: str, evidence: str, unblock: str | None = None) -> dict[str, object]:
    return {"status": status, "evidence": evidence, "unblock_condition": unblock}


def main() -> None:
    registration = json.loads((EVIDENCE / "registration.json").read_text(encoding="utf-8"))
    field = json.loads((EVIDENCE / "field-contract-audit.json").read_text(encoding="utf-8"))
    raw = json.loads((RAW / "raw-manifest.json").read_text(encoding="utf-8"))
    split = json.loads((RAW / "geographic-split.json").read_text(encoding="utf-8"))
    train = json.loads((EVIDENCE / "mt-usarray-train-diagnostics.json").read_text(encoding="utf-8"))
    xml_manifest_path = RAW / "xml-raw-manifest.json"
    xml_manifest = json.loads(xml_manifest_path.read_text(encoding="utf-8"))
    xml_covariance = json.loads(
        (EVIDENCE / "mt-xml-covariance-readiness.json").read_text(encoding="utf-8")
    )
    tdip_split = json.loads((EVIDENCE / "tdip-date-split.json").read_text(encoding="utf-8"))
    tdip_train = json.loads((EVIDENCE / "tdip-train-diagnostics.json").read_text(encoding="utf-8"))
    tdip_path = json.loads((EVIDENCE / "tdip-path-readiness.json").read_text(encoding="utf-8"))
    mt3d_path = json.loads((EVIDENCE / "mt3d-path-readiness.json").read_text(encoding="utf-8"))
    tem_manifest_path = ROOT / "validation/wp8/data/east-river-aem-v1/raw-manifest.json"
    tem_manifest = json.loads(tem_manifest_path.read_text(encoding="utf-8"))
    tem_split = json.loads((EVIDENCE / "east-river-aem-design-split.json").read_text(encoding="utf-8"))
    tem_contract = json.loads(
        (EVIDENCE / "east-river-aem-contract-readiness.json").read_text(encoding="utf-8")
    )
    tem_train = json.loads(
        (EVIDENCE / "east-river-aem-train-diagnostics.json").read_text(encoding="utf-8")
    )
    tem_consortium_manifest_path = (
        ROOT / "validation/wp8/data/tem-aem-consortium-v1/raw-manifest.json"
    )
    tem_consortium_manifest = json.loads(
        tem_consortium_manifest_path.read_text(encoding="utf-8")
    )
    tem_consortium_contract = json.loads(
        (EVIDENCE / "tem-aem-consortium-contract-readiness.json").read_text(encoding="utf-8")
    )
    tem_consortium_train = json.loads(
        (EVIDENCE / "tem-aem-consortium-train-diagnostics.json").read_text(encoding="utf-8")
    )
    maricopa_manifest_path = ROOT / "validation/wp8/data/maricopa-aem-v1/raw-manifest.json"
    maricopa_manifest = json.loads(maricopa_manifest_path.read_text(encoding="utf-8"))
    maricopa_split = json.loads(
        (EVIDENCE / "maricopa-aem-design-split.json").read_text(encoding="utf-8")
    )
    maricopa_contract = json.loads(
        (EVIDENCE / "maricopa-aem-contract-readiness.json").read_text(encoding="utf-8")
    )
    maricopa_train = json.loads(
        (EVIDENCE / "maricopa-aem-train-diagnostics.json").read_text(encoding="utf-8")
    )
    ga_aem_catalog_manifest_path = (
        ROOT
        / "validation/wp8/data/geoscience-australia-aem-catalog-v1/raw-manifest.json"
    )
    ga_aem_catalog = json.loads(
        ga_aem_catalog_manifest_path.read_text(encoding="utf-8")
    )
    ga_aem_design = json.loads(
        (EVIDENCE / "geoscience-australia-aem-design.json").read_text(
            encoding="utf-8"
        )
    )
    ga_aem_probe_manifest_path = (
        ROOT
        / "validation/wp8/data/geoscience-australia-aem-training-probe-v1/raw-manifest.json"
    )
    ga_aem_probe = json.loads(
        ga_aem_probe_manifest_path.read_text(encoding="utf-8")
    )
    ga_aem_probe_contract = json.loads(
        (
            EVIDENCE / "geoscience-australia-aem-training-probe-contract.json"
        ).read_text(encoding="utf-8")
    )
    ga_aem_multisystem_manifest_path = (
        ROOT
        / "validation/wp8/data/geoscience-australia-aem-multisystem-v1/raw-manifest.json"
    )
    ga_aem_multisystem_manifest = json.loads(
        ga_aem_multisystem_manifest_path.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_inventory_path = (
        EVIDENCE / "geoscience-australia-aem-multisystem-inventory.json"
    )
    ga_aem_multisystem_inventory = json.loads(
        ga_aem_multisystem_inventory_path.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_contract = json.loads(
        (EVIDENCE / "geoscience-australia-aem-multisystem-contract.json").read_text(
            encoding="utf-8"
        )
    )
    ga_aem_multisystem_split_path = (
        EVIDENCE / "geoscience-australia-aem-multisystem-spatial-split.json"
    )
    ga_aem_multisystem_split = json.loads(
        ga_aem_multisystem_split_path.read_text(encoding="utf-8")
    )
    ga_aem_multisystem_train = json.loads(
        (
            EVIDENCE
            / "geoscience-australia-aem-multisystem-train-diagnostics.json"
        ).read_text(encoding="utf-8")
    )
    krause_ert_manifest_path = (
        ROOT / "validation/wp8/data/usgs-krause-ert-v1/raw-manifest.json"
    )
    krause_ert_manifest = json.loads(
        krause_ert_manifest_path.read_text(encoding="utf-8")
    )
    krause_ert_contract = json.loads(
        (EVIDENCE / "usgs-krause-ert-contract.json").read_text(encoding="utf-8")
    )
    svalbard_ert_manifest_path = (
        ROOT / "validation/wp8/data/svalbard-ert-repository-v1/raw-manifest.json"
    )
    svalbard_ert_manifest = json.loads(
        svalbard_ert_manifest_path.read_text(encoding="utf-8")
    )
    svalbard_ert_contract = json.loads(
        (EVIDENCE / "svalbard-ert-training-contract.json").read_text(encoding="utf-8")
    )
    cpers_manifest_path = (
        ROOT / "validation/wp8/data/cpers-public-catalogue-v2/raw-manifest.json"
    )
    cpers_manifest = json.loads(cpers_manifest_path.read_text(encoding="utf-8"))
    cpers_catalogue = json.loads(
        (EVIDENCE / "cpers-public-catalogue.json").read_text(encoding="utf-8")
    )
    mount_st_helens_csamt_manifest_path = (
        ROOT
        / "validation/wp8/data/usgs-mount-st-helens-csamt-v1/raw-manifest.json"
    )
    mount_st_helens_csamt_manifest = json.loads(
        mount_st_helens_csamt_manifest_path.read_text(encoding="utf-8")
    )
    mount_st_helens_csamt_contract = json.loads(
        (
            EVIDENCE / "usgs-mount-st-helens-csamt-contract.json"
        ).read_text(encoding="utf-8")
    )
    hualapai_csamt_manifest_path = (
        ROOT / "validation/wp8/data/usgs-hualapai-csamt-v1/raw-manifest.json"
    )
    hualapai_csamt_manifest = json.loads(
        hualapai_csamt_manifest_path.read_text(encoding="utf-8")
    )
    hualapai_csamt_contract = json.loads(
        (EVIDENCE / "usgs-hualapai-csamt-contract.json").read_text(encoding="utf-8")
    )
    hualapai_reconciliation_path = (
        EVIDENCE / "hualapai-csamt-role-reconciliation-v1.json"
    )
    hualapai_reconciliation = json.loads(
        hualapai_reconciliation_path.read_text(encoding="utf-8")
    )
    wisconsin_gravity_manifest_path = (
        ROOT / "validation/wp8/data/wisconsin-gravity-v1/raw-manifest.json"
    )
    wisconsin_gravity_manifest = json.loads(
        wisconsin_gravity_manifest_path.read_text(encoding="utf-8")
    )
    wisconsin_gravity_split = json.loads(
        (EVIDENCE / "wisconsin-gravity-design-split.json").read_text(encoding="utf-8")
    )
    wisconsin_gravity_train = json.loads(
        (EVIDENCE / "wisconsin-gravity-train-diagnostics.json").read_text(encoding="utf-8")
    )
    sierra_gravity_manifest_path = (
        ROOT / "validation/wp8/data/sierra-nevada-gravity-v1/raw-manifest.json"
    )
    sierra_gravity_manifest = json.loads(
        sierra_gravity_manifest_path.read_text(encoding="utf-8")
    )
    sierra_gravity_design = json.loads(
        (EVIDENCE / "sierra-nevada-gravity-design.json").read_text(encoding="utf-8")
    )
    sierra_gravity_train = json.loads(
        (EVIDENCE / "sierra-nevada-gravity-train-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    san_pedro_gravity_manifest_path = (
        ROOT / "validation/wp8/data/usgs-upper-san-pedro-gravity-v1/raw-manifest.json"
    )
    san_pedro_gravity_manifest = json.loads(
        san_pedro_gravity_manifest_path.read_text(encoding="utf-8")
    )
    san_pedro_gravity_contract = json.loads(
        (EVIDENCE / "usgs-upper-san-pedro-gravity.json").read_text(encoding="utf-8")
    )
    san_pedro_gravity_design = json.loads(
        (EVIDENCE / "usgs-upper-san-pedro-gravity-design.json").read_text(
            encoding="utf-8"
        )
    )
    saudi_gravity_manifest_path = (
        ROOT / "validation/wp8/data/usgs-saudi-regional-gravity-v1/raw-manifest.json"
    )
    saudi_gravity_manifest = json.loads(
        saudi_gravity_manifest_path.read_text(encoding="utf-8")
    )
    saudi_gravity_extraction = json.loads(
        (EVIDENCE / "usgs-saudi-regional-gravity-extraction.json").read_text(
            encoding="utf-8"
        )
    )
    saudi_gravity_design = json.loads(
        (EVIDENCE / "usgs-saudi-regional-gravity-design.json").read_text(
            encoding="utf-8"
        )
    )
    ridgecrest_gravity_manifest_path = (
        ROOT / "validation/wp8/data/usgs-ridgecrest-gravity-v1/raw-manifest.json"
    )
    ridgecrest_gravity_manifest = json.loads(
        ridgecrest_gravity_manifest_path.read_text(encoding="utf-8")
    )
    ridgecrest_gravity_design = json.loads(
        (EVIDENCE / "usgs-ridgecrest-gravity-design.json").read_text(encoding="utf-8")
    )
    ridgecrest_gravity_training = json.loads(
        (EVIDENCE / "usgs-ridgecrest-gravity-training.json").read_text(encoding="utf-8")
    )
    tasmania_gravity_manifest_path = (
        ROOT / "validation/wp8/data/mrt-tasmania-gravity-v1/raw-manifest.json"
    )
    tasmania_gravity_manifest = json.loads(
        tasmania_gravity_manifest_path.read_text(encoding="utf-8")
    )
    tasmania_gravity_design = json.loads(
        (EVIDENCE / "mrt-tasmania-gravity-design.json").read_text(encoding="utf-8")
    )
    tasmania_gravity_training = json.loads(
        (EVIDENCE / "mrt-tasmania-gravity-training.json").read_text(encoding="utf-8")
    )
    ga_gravity_catalogue_manifest_path = (
        ROOT
        / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1/raw-manifest.json"
    )
    ga_gravity_catalogue_manifest = json.loads(
        ga_gravity_catalogue_manifest_path.read_text(encoding="utf-8")
    )
    ga_gravity_design = json.loads(
        (EVIDENCE / "ga-national-ground-gravity-design.json").read_text(
            encoding="utf-8"
        )
    )
    ga_gravity_schema = json.loads(
        (EVIDENCE / "ga-ground-gravity-schema-probe.json").read_text(
            encoding="utf-8"
        )
    )
    ga_gravity_pool_manifest_path = (
        ROOT
        / "validation/wp8/data/ga-national-ground-gravity-catalogue-v1/pool-manifest.json"
    )
    ga_gravity_pool = json.loads(
        ga_gravity_pool_manifest_path.read_text(encoding="utf-8")
    )
    ga_gravity_geometry = json.loads(
        (EVIDENCE / "ga-national-ground-gravity-geometry.json").read_text(
            encoding="utf-8"
        )
    )
    ga_gravity_uncertainty = json.loads(
        (EVIDENCE / "ga-national-ground-gravity-uncertainty.json").read_text(
            encoding="utf-8"
        )
    )
    ga_gravity_training = json.loads(
        (EVIDENCE / "ga-national-ground-gravity-training.json").read_text(
            encoding="utf-8"
        )
    )
    ga_gravity_power = json.loads(
        (EVIDENCE / "ga-national-ground-gravity-power.json").read_text(
            encoding="utf-8"
        )
    )
    ga_gravity_separation = json.loads(
        (EVIDENCE / "ga-national-ground-gravity-separation.json").read_text(
            encoding="utf-8"
        )
    )
    csamt_split = json.loads((EVIDENCE / "csamt-candidate-split.json").read_text(encoding="utf-8"))
    mountain_magnetic = json.loads(
        (EVIDENCE / "mountain-pass-magnetic-design-split.json").read_text(encoding="utf-8")
    )
    mountain_magnetic_train = json.loads(
        (EVIDENCE / "mountain-pass-magnetic-train-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    arkansas_magnetic_contract = json.loads(
        (EVIDENCE / "western-arkansas-magnetic-contract-readiness.json").read_text(
            encoding="utf-8"
        )
    )
    arkansas_magnetic_train = json.loads(
        (EVIDENCE / "western-arkansas-magnetic-train-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    ga_magnetic_design = json.loads(
        (EVIDENCE / "geoscience-australia-magnetic-design.json").read_text(
            encoding="utf-8"
        )
    )
    ga_magnetic_contract = json.loads(
        (EVIDENCE / "geoscience-australia-magnetic-dds-contract.json").read_text(
            encoding="utf-8"
        )
    )
    ga_magnetic_training = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-training-consortium.json"
        ).read_text(encoding="utf-8")
    )
    ga_magnetic_expansion = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-training-expansion.json"
        ).read_text(encoding="utf-8")
    )
    ga_magnetic_probability = json.loads(
        (
            EVIDENCE / "geoscience-australia-magnetic-probability-audit.json"
        ).read_text(encoding="utf-8")
    )
    magic_prior = json.loads(
        (EVIDENCE / "magic-training-remanence-prior.json").read_text(encoding="utf-8")
    )
    texas_magnetic = json.loads(
        (EVIDENCE / "texas-aib-magnetic-contract-readiness.json").read_text(encoding="utf-8")
    )
    texas_access = json.loads(
        (EVIDENCE / "texas-aib-response-access.json").read_text(encoding="utf-8")
    )
    controlled_public = json.loads(
        (EVIDENCE / "controlled-source-public-data-audit.json").read_text(encoding="utf-8")
    )
    if (
        controlled_public.get("schema_version")
        != "wp8-controlled-source-public-data-audit-v1"
        or controlled_public.get("formal_test_endpoints_inspected") is not False
        or controlled_public.get("conclusions", {}).get("method_substitution_allowed")
        is not False
    ):
        raise RuntimeError("controlled-source public-data evidence drift")
    sip_public = json.loads(
        (EVIDENCE / "sip-fdip-public-data-audit.json").read_text(encoding="utf-8")
    )
    if (
        sip_public.get("schema_version") != "wp8-sip-fdip-public-data-audit-v1"
        or sip_public.get("formal_test_endpoints_inspected") is not False
        or sip_public.get("conclusions", {}).get(
            "contract_complete_field_replacement_found"
        )
        is not False
        or sip_public.get("conclusions", {}).get("method_substitution_allowed")
        is not False
    ):
        raise RuntimeError("SIP/FDIP public-data evidence drift")
    tdip_full_decay = json.loads(
        (EVIDENCE / "zenodo-tdip-full-decay-contract.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        tdip_full_decay.get("schema_version")
        != "wp8-zenodo-tdip-full-decay-contract-v1"
        or tdip_full_decay.get("observation_values_read") is not False
        or tdip_full_decay.get("formal_test_endpoints_inspected") is not False
        or tdip_full_decay.get("selection_role")
        != "training_contract_candidate_only"
        or tdip_full_decay.get("gate_impact", {}).get("power_gate_passed")
        is not False
        or tdip_full_decay.get("test_unseal_count") != 0
    ):
        raise RuntimeError("Zenodo TDIP full-decay contract evidence drift")
    tdip_full_decay_training = json.loads(
        (EVIDENCE / "zenodo-tdip-full-decay-training-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        tdip_full_decay_training.get("schema_version")
        != "wp8-zenodo-tdip-full-decay-training-diagnostics-v1"
        or tdip_full_decay_training.get("selection_role") != "training_only"
        or tdip_full_decay_training.get("buffer_values_read") != 0
        or tdip_full_decay_training.get("calibration_values_read") != 0
        or tdip_full_decay_training.get("test_values_read") != 0
        or tdip_full_decay_training.get("test_unseal_count") != 0
        or tdip_full_decay_training.get("interpretation", {}).get(
            "formal_power_gate"
        )
        != "failed"
    ):
        raise RuntimeError("Zenodo TDIP full-decay training evidence drift")
    ip_vae_release = json.loads(
        (EVIDENCE / "ip-vae-public-release.json").read_text(encoding="utf-8")
    )
    if (
        ip_vae_release.get("schema_version")
        != "wp8-ip-vae-public-release-audit-v1"
        or ip_vae_release.get("paper_compilation", {}).get("field_decay_curve_count")
        != 1600319
        or ip_vae_release.get("paper_compilation", {}).get("field_survey_count")
        != 110
        or ip_vae_release.get("pretrained_weight_file_count") != 4
        or ip_vae_release.get("likely_field_observation_file_count") != 0
        or ip_vae_release.get("raw_field_compilation_publicly_released") is not False
        or ip_vae_release.get("formal_cluster_power_gate_passes") is not False
        or ip_vae_release.get("test_unseal_count") != 0
    ):
        raise RuntimeError("IP-VAE public release evidence drift")
    ntgs_tdip = json.loads(
        (EVIDENCE / "ntgs-tdip-training-candidates.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        ntgs_tdip.get("schema_version")
        != "wp8-ntgs-tdip-training-candidates-audit-v1"
        or ntgs_tdip.get("kroda_2018", {}).get("line_file_count") != 4
        or ntgs_tdip.get("kroda_2018", {}).get(
            "all_files_have_contract_fields"
        )
        is not True
        or ntgs_tdip.get("arunta_2024", {}).get("raw_gdd_file_count") != 15
        or ntgs_tdip.get("arunta_2024", {}).get(
            "all_raw_files_have_contract_fields"
        )
        is not True
        or ntgs_tdip.get("repository_access", {}).get(
            "formal_license_gate_passes"
        )
        is not False
        or ntgs_tdip.get("formal_cluster_power_gate_passes") is not False
        or ntgs_tdip.get("test_unseal_count") != 0
    ):
        raise RuntimeError("NTGS TDIP training-candidate evidence drift")
    ntgs_ip_catalogue = json.loads(
        (EVIDENCE / "ntgs-ip-open-search-catalogue.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        ntgs_ip_catalogue.get("schema_version")
        != "wp8-ntgs-ip-open-search-catalogue-audit-v1"
        or ntgs_ip_catalogue.get("unique_item_count") != 619
        or ntgs_ip_catalogue.get("items_with_digital_attachments") != 218
        or ntgs_ip_catalogue.get(
            "items_with_explicit_ip_or_raw_named_attachments"
        )
        != 16
        or ntgs_ip_catalogue.get("data_payloads_downloaded") != 0
        or ntgs_ip_catalogue.get("formal_contract_ready") is not False
        or ntgs_ip_catalogue.get("formal_cluster_power_gate_passes") is not False
        or ntgs_ip_catalogue.get("test_unseal_count") != 0
    ):
        raise RuntimeError("NTGS IP OpenSearch catalogue evidence drift")
    ntgs_ip_explicit = json.loads(
        (EVIDENCE / "ntgs-ip-explicit-candidates.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        ntgs_ip_explicit.get("schema_version")
        != "wp8-ntgs-ip-explicit-candidates-audit-v1"
        or ntgs_ip_explicit.get("package_count") != 20
        or ntgs_ip_explicit.get("packages_with_contract_rich_full_decay") != 4
        or ntgs_ip_explicit.get("duplicate_observation_hash_group_count") != 26
        or ntgs_ip_explicit.get("repository_access", {}).get(
            "formal_license_gate_passes"
        )
        is not False
        or ntgs_ip_explicit.get("formal_independent_campaign_count") != 0
        or ntgs_ip_explicit.get("formal_cluster_power_gate_passes") is not False
        or ntgs_ip_explicit.get("test_unseal_count") != 0
    ):
        raise RuntimeError("NTGS explicit IP candidate evidence drift")
    brittany_ert = json.loads(
        (EVIDENCE / "pangaea-brittany-ert-training-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        brittany_ert.get("schema_version")
        != "wp8-pangaea-brittany-ert-training-diagnostics-v1"
        or brittany_ert.get("partition") != "training-only"
        or brittany_ert.get("profile_count") != 8
        or brittany_ert.get("geographic_area_count") != 2
        or brittany_ert.get("usable_as_tdip_evidence") is not False
        or brittany_ert.get("test_reads") != 0
        or brittany_ert.get("test_unseal_count") != 0
    ):
        raise RuntimeError("PANGAEA Brittany ERT training evidence drift")
    guidel_sip = json.loads(
        (EVIDENCE / "guidel-sip-contract.json").read_text(encoding="utf-8")
    )
    if (
        guidel_sip.get("schema_version") != "wp8-guidel-sip-contract-v1"
        or guidel_sip.get("selection_role") != "training_contract_candidate_only"
        or guidel_sip.get("observation_values_read") is not False
        or guidel_sip.get("formal_test_endpoints_inspected") is not False
        or guidel_sip.get("monitoring_csv_bytes") != 0
        or guidel_sip.get("monitoring_observations_available") is not False
        or guidel_sip.get("gate_impact", {}).get("power_gate_passed") is not False
        or guidel_sip.get("test_unseal_count") != 0
    ):
        raise RuntimeError("Guidel SIP contract evidence drift")
    guidel_sip_training = json.loads(
        (EVIDENCE / "guidel-sip-training-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        guidel_sip_training.get("schema_version")
        != "wp8-guidel-sip-training-diagnostics-v1"
        or guidel_sip_training.get("partition") != "training-only"
        or guidel_sip_training.get("raw_file_count") != 30
        or guidel_sip_training.get("nonfinite_scalar_values") != 0
        or guidel_sip_training.get("long_term_monitoring_rows_available") != 0
        or guidel_sip_training.get("processing_contract", {}).get(
            "complex_observations_after_processing"
        )
        != 1680
        or guidel_sip_training.get("geometry_contract", {}).get(
            "relative_geometry_reconstructable_without_interpolation"
        )
        is not True
        or guidel_sip_training.get("interpretation", {}).get(
            "field_geometry_contract"
        )
        != "passed_training_only"
        or guidel_sip_training.get("interpretation", {}).get(
            "formal_power_gate"
        )
        != "failed"
        or guidel_sip_training.get("test_values_read") != 0
        or guidel_sip_training.get("test_unseal_count") != 0
    ):
        raise RuntimeError("Guidel SIP training evidence drift")
    guidel_repeatability = json.loads(
        (EVIDENCE / "guidel-sip-repeatability.json").read_text(encoding="utf-8")
    )
    if (
        guidel_repeatability.get("schema_version")
        != "wp8-guidel-sip-repeatability-v1"
        or guidel_repeatability.get("partition") != "training-only"
        or guidel_repeatability.get("adjacent_dipoles_all_frequencies", {}).get(
            "complex_observations"
        )
        != 420
        or guidel_repeatability.get("interpretation", {}).get(
            "repeat_based_uncertainty_contract"
        )
        != "passed_training_only"
        or guidel_repeatability.get("interpretation", {}).get(
            "formal_power_gate"
        )
        != "failed"
        or guidel_repeatability.get("test_values_read") != 0
        or guidel_repeatability.get("test_unseal_count") != 0
    ):
        raise RuntimeError("Guidel SIP repeatability evidence drift")
    tuwien_sip = json.loads(
        (EVIDENCE / "tuwien-ice-sip-training-diagnostics.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        tuwien_sip.get("schema_version")
        != "wp8-tuwien-ice-sip-training-diagnostics-v1"
        or tuwien_sip.get("selection_role")
        != "laboratory_solver_reference_only"
        or tuwien_sip.get("electrode_count") != 54
        or tuwien_sip.get("quadrupoles_per_frequency") != 138
        or tuwien_sip.get("frequency_count") != 21
        or tuwien_sip.get("formal_cluster_contribution") != 0
        or tuwien_sip.get("test_values_read") != 0
        or tuwien_sip.get("test_unseal_count") != 0
    ):
        raise RuntimeError("TU Wien SIP training evidence drift")
    wfem_public = json.loads(
        (EVIDENCE / "wfem-public-contract-references.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        wfem_public.get("schema_version")
        != "wp8-wfem-public-contract-references-v1"
        or wfem_public.get("formal_test_endpoints_inspected") is not False
        or wfem_public.get("conclusions", {}).get(
            "largest_public_design_station_upper_bound"
        )
        != 304
        or wfem_public.get("conclusions", {}).get(
            "qualified_formal_station_count"
        )
        != 0
        or wfem_public.get("conclusions", {}).get("formal_power_gate")
        != "failed"
        or wfem_public.get("conclusions", {}).get("dimensionality_gate")
        != "failed"
        or wfem_public.get("test_values_read") != 0
        or wfem_public.get("test_unseal_count") != 0
    ):
        raise RuntimeError("WFEM public contract-reference evidence drift")

    checked = []
    readonly_failures = []
    for member in raw["members"]:
        path = RAW / member["path"]
        readonly = not bool(path.stat().st_mode & stat.S_IWRITE)
        if not readonly:
            readonly_failures.append(member["spud_id"])
        if sha(path) != member["sha256"]:
            raise RuntimeError(f"MT raw hash drift: {member['spud_id']}")
        checked.append(member)
    if merkle(checked) != raw["member_merkle_root"]:
        raise RuntimeError("MT raw Merkle drift")
    if readonly_failures:
        raise RuntimeError(f"MT writable raw members: {readonly_failures[:5]}")
    if train["calibration_members_interpreted"] != 0 or train["test_members_interpreted"] != 0:
        raise RuntimeError("MT sealed partition was interpreted")
    xml_checked = []
    xml_readonly_failures = []
    for member in xml_manifest["members"]:
        path = RAW / member["path"]
        if path.stat().st_mode & stat.S_IWRITE:
            xml_readonly_failures.append(member["spud_id"])
        if path.stat().st_size != member["bytes"] or sha(path) != member["sha256"]:
            raise RuntimeError(f"MT XML hash drift: {member['spud_id']}")
        xml_checked.append(member)
    xml_role_counts = {
        role: sum(member["split"] == role for member in xml_checked)
        for role in ("train", "buffer", "calibration", "test")
    }
    adapter_path = ROOT / xml_covariance["adapter_source"]
    if (
        xml_manifest["member_count"] != 1104
        or len(xml_checked) != 1104
        or xml_role_counts != split["counts"]
        or xml_readonly_failures
        or xml_manifest["split_frozen_before_requests"] is not True
        or xml_manifest["sealed_payloads_interpreted"] is not False
        or xml_covariance["passed"] is not True
        or xml_covariance["xml_manifest_sha256"] != sha(xml_manifest_path)
        or xml_covariance["role_counts"] != xml_role_counts
        or xml_covariance["training_members_interpreted"] != 361
        or xml_covariance["buffer_members_interpreted"] != 0
        or xml_covariance["calibration_members_interpreted"] != 0
        or xml_covariance["test_members_interpreted"] != 0
        or xml_covariance["sealed_payload_values_read"] is not False
        or xml_covariance["representative_real_stack_off_diagonal_count"] <= 0
        or xml_covariance["variance_identity_max_relative_error"] > 1e-5
        or not adapter_path.is_file()
        or xml_covariance["adapter_source_sha256"] != sha(adapter_path)
    ):
        raise RuntimeError("MT XML covariance evidence drift")

    methods = {}
    external_contract = {
        "gravity": "independent spatial surveys or provider-defined clusters and field-scale error model",
        "magnetic": "outcome-blind line clustering/correlation estimate and at least 223 effective held-out clusters",
        "dc": "per-observation errors and at least 223 independent field clusters",
        "tdip": "provider QC/error export and 223 independent date/site clusters",
        "sip_fdip": "multi-laboratory/profile consortium with 223 units, complex covariance and station keys",
        "tem": "outcome-blind site inventory, field dimensionality evidence and sufficient clusters",
        "csamt": "transmitter GPS/current logs, receiver geometry, near-field classification, errors and 223 clusters",
        "wfem": "native source/receiver/phase/component/geometric-factor/error export and 223 clusters",
    }
    for method in METHODS:
        registered = registration["methods"][method]["gates"]
        observed = field["methods"][method]
        if method == "mt_amt":
            methods[method] = {
                "license": gate("passed", "1104 TA members declare Unrestricted Release with citation/acknowledgement"),
                "integrity": gate("passed", f"1104 HTTPS members, {raw['total_edi_bytes']} bytes, local SHA-256 and Merkle verified"),
                "contract": gate(
                    "passed",
                    "official EMTF XML residual/inverse-signal matrices reconstruct joint complex Z covariance; "
                    f"{xml_covariance['covariance_periods_checked']} training periods checked, "
                    f"variance identity maximum relative error={xml_covariance['variance_identity_max_relative_error']}",
                ),
                "cluster_power": gate("passed", f"geographic train/buffer/cal/test={split['counts']}; sealed test=429 >=223"),
                "dimension": gate("passed", f"training-only classification={train['dimensionality_counts']}; mandatory 3-D upgrade selected"),
                "solver": gate(
                    "passed",
                    "version-frozen MT3DOperator primary-secondary natural-source Maxwell path produces full Z tensor and tipper",
                ),
                "reference": gate(
                    "passed",
                    mt3d_path["independent_reference"]["kind"],
                ),
                "resource": gate(
                    "passed",
                    "three measured scales end at 336 stations/3 frequencies/512 cells with enforced abort limits; formal_wp8_1_evidence=false",
                ),
            }
            continue
        if method == "gravity":
            archive = ROOT / wisconsin_gravity_manifest["archive"]["path"]
            if (
                archive.stat().st_size
                != wisconsin_gravity_manifest["archive"]["bytes"]
                or sha(archive) != wisconsin_gravity_manifest["archive"]["sha256"]
                or wisconsin_gravity_manifest["response_values_interpreted"] is not False
                or wisconsin_gravity_split["format_contract"][
                    "response_fields_values_parsed"
                ]
                is not False
                or wisconsin_gravity_train["response_policy"]["buffer_rows_interpreted"]
                != 0
                or wisconsin_gravity_train["response_policy"][
                    "calibration_rows_interpreted"
                ]
                != 0
                or wisconsin_gravity_train["response_policy"]["test_rows_interpreted"]
                != 0
                or wisconsin_gravity_train[
                    "correlation_adjusted_test_cluster_upper_bound"
                ]
                != 1
                or wisconsin_gravity_train["dimensionality"]["passed"] is not True
                or sierra_gravity_manifest["license"] != "CC0 1.0 Universal"
                or sierra_gravity_manifest[
                    "response_values_interpreted_during_acquisition"
                ]
                != 0
                or sierra_gravity_design["formal_excluded_ids"] != ["CH75"]
                or sierra_gravity_design["response_fields_interpreted"] != 0
                or sierra_gravity_design["partition_block_counts"]
                != {"train": 107, "buffer": 48, "calibration": 59, "test": 320}
                or sierra_gravity_train["response_rows_interpreted"]
                != {"train": 5585, "buffer": 0, "calibration": 0, "test": 0}
                or sierra_gravity_train["correlation_range_km"] != 62.5
                or sierra_gravity_train[
                    "correlation_adjusted_test_cluster_upper_bound"
                ]
                != 42
                or sierra_gravity_train["cluster_power_gate_passes"] is not False
                or sierra_gravity_train[
                    "per_observation_uncertainty_contract_ready"
                ]
                is not False
                or sierra_gravity_train["test_unseal_count"] != 0
                or san_pedro_gravity_contract["observation_contract"] != "pass"
                or san_pedro_gravity_contract["parsed_station_count"] != 1520
                or san_pedro_gravity_contract[
                    "positive_finite_complete_bouguer_sd"
                ]
                != 1520
                or san_pedro_gravity_design["response_fields_interpreted"] != 0
                or san_pedro_gravity_design["partition_block_counts"]
                != {"train": 58, "buffer": 14, "calibration": 17, "test": 141}
                or san_pedro_gravity_design["design_power_gate_possible"] is not False
                or san_pedro_gravity_design["test_unseal_count"] != 0
                or saudi_gravity_extraction["strict_records"] != 1342
                or saudi_gravity_extraction["formal_test_endpoint_exposure"] != 1342
                or saudi_gravity_extraction["formal_confirmatory_contribution"] != 0
                or saudi_gravity_design["response_fields_interpreted"] != 0
                or saudi_gravity_design["partition_block_counts"]
                != {"train": 97, "buffer": 38, "calibration": 58, "test": 311}
                or saudi_gravity_design["design_power_gate_possible"] is not True
                or ridgecrest_gravity_manifest["license"] != "CC0-1.0"
                or ridgecrest_gravity_design["response_fields_interpreted"] != 0
                or ridgecrest_gravity_design["partition_block_counts"]
                != {"train": 127, "buffer": 65, "calibration": 56, "test": 375}
                or ridgecrest_gravity_training["response_rows_interpreted"]
                != {"train": 1464, "buffer": 0, "calibration": 0, "test": 0}
                or ridgecrest_gravity_training["correlation_range_km"] != 21.25
                or ridgecrest_gravity_training[
                    "correlation_adjusted_test_cluster_upper_bound"
                ]
                != 46
                or ridgecrest_gravity_training[
                    "per_observation_uncertainty_contract"
                ]
                is not False
                or ridgecrest_gravity_training["test_unseal_count"] != 0
                or tasmania_gravity_manifest["license"]
                != "Creative Commons Attribution 3.0 Australia"
                or tasmania_gravity_manifest[
                    "response_values_interpreted_during_acquisition"
                ]
                != 0
                or tasmania_gravity_design["response_fields_interpreted"] != 0
                or tasmania_gravity_design["partition_block_counts"]
                != {"train": 576, "buffer": 297, "calibration": 303, "test": 1585}
                or tasmania_gravity_design["design_power_gate_possible"] is not True
                or tasmania_gravity_training["response_rows_interpreted"]
                != {"train": 14226, "buffer": 0, "calibration": 0, "test": 0}
                or tasmania_gravity_training["correlation_range_km"] != 100.0
                or tasmania_gravity_training["range_censored_at_100km"] is not True
                or tasmania_gravity_training[
                    "correlation_adjusted_test_cluster_upper_bound"
                ]
                != 0
                or tasmania_gravity_training[
                    "per_observation_uncertainty_contract"
                ]
                is not False
                or tasmania_gravity_training["formal_confirmatory_contribution"] != 0
                or tasmania_gravity_training["test_unseal_count"] != 0
                or ga_gravity_catalogue_manifest["dataset_count"] != 1634
                or ga_gravity_catalogue_manifest["declared_station_total"] != 1840331
                or ga_gravity_catalogue_manifest["anonymous_file_download_urls"] != 1634
                or ga_gravity_catalogue_manifest[
                    "response_values_interpreted_during_acquisition"
                ]
                != 0
                or ga_gravity_design["formal_excluded_surveys"] != ["P199964"]
                or ga_gravity_design["response_fields_interpreted"] != 0
                or ga_gravity_design["partition_block_counts"]
                != {"train": 144, "buffer": 94, "calibration": 106, "test": 491}
                or ga_gravity_design["design_power_gate_possible"] is not True
                or ga_gravity_design["test_unseal_count"] != 0
                or ga_gravity_schema["required_variables_present"] is not True
                or ga_gravity_schema["response_array_values_read"] != 0
                or ga_gravity_schema["pre_design_response_metadata_exposure"][
                    "scope"
                ]
                != "P199964 only"
                or ga_gravity_schema["formal_confirmatory_contribution"] != 0
                or ga_gravity_pool["member_count"] != 1633
                or ga_gravity_pool["formal_excluded_surveys"] != ["P199964"]
                or ga_gravity_pool[
                    "response_values_interpreted_during_acquisition"
                ]
                != 0
                or ga_gravity_geometry["survey_status_counts"]
                != {"excluded_cross_role_footprint": 1108, "retained": 525}
                or ga_gravity_geometry["retained_unique_block_counts"]
                != {"train": 48, "buffer": 27, "calibration": 29, "test": 302}
                or ga_gravity_geometry["station_level_power_gate_possible"] is not True
                or ga_gravity_geometry["test_unseal_count"] != 0
                or ga_gravity_uncertainty["eligible_unique_block_counts"]
                != {"train": 48, "buffer": 27, "calibration": 29, "test": 301}
                or ga_gravity_uncertainty[
                    "uncertainty_qualified_test_cluster_upper_bound"
                ]
                != 301
                or ga_gravity_uncertainty["uncertainty_power_gate_possible"] is not True
                or ga_gravity_uncertainty["test_unseal_count"] != 0
                or ga_gravity_training["response_policy"]
                != {
                    "train_rows_interpreted": 53066,
                    "train_contract_eligible_rows": 53066,
                    "buffer_rows_interpreted": 0,
                    "calibration_rows_interpreted": 0,
                    "test_rows_interpreted": 0,
                    "test_quality_rows_examined_without_response": 159554,
                }
                or ga_gravity_training["training_subcells"] != 598
                or ga_gravity_training["correlation_range_km"] != 12.5
                or ga_gravity_training[
                    "correlation_adjusted_test_cluster_upper_bound"
                ]
                != 1603
                or ga_gravity_training["cluster_power_gate_passes"] is not True
                or ga_gravity_training["complete_bouguer_contract"] is not True
                or ga_gravity_training[
                    "per_observation_uncertainty_contract"
                ]
                is not True
                or ga_gravity_training["paired_crps_effect_available"] is not False
                or ga_gravity_training["formal_confirmatory_contribution"] != 0
                or ga_gravity_training["test_unseal_count"] != 0
                or ga_gravity_power["training_only"] is not True
                or ga_gravity_power["paired_training_blocks"] != 48
                or ga_gravity_power["power_target_relative_improvement"] != 0.1
                or ga_gravity_power["required_paired_crps_clusters"] != 153
                or ga_gravity_power["required_coverage_clusters"]
                != {"0.90": 223, "0.95": 118}
                or ga_gravity_power["required_clusters_all_metrics"] != 223
                or ga_gravity_power["wp8_0_power_gate_passes"] is not True
                or ga_gravity_power["test_responses_interpreted"] != 0
                or ga_gravity_power["test_unseal_count"] != 0
                or ga_gravity_power["formal_test_result"] is not None
                or ga_gravity_separation["response_fields_read"] != []
                or ga_gravity_separation["test_provider_survey_candidates"] != 352
                or ga_gravity_separation["excluded_near_train_or_calibration"] != 1
                or ga_gravity_separation["accepted_independent_test_surveys"] != 261
                or ga_gravity_separation["required_clusters_all_metrics"] != 223
                or ga_gravity_separation[
                    "provider_spatial_power_gate_passes"
                ]
                is not True
                or ga_gravity_separation["test_responses_interpreted"] != 0
                or ga_gravity_separation["test_unseal_count"] != 0
            ):
                raise RuntimeError("gravity evidence drift")
            san_pedro_root = san_pedro_gravity_manifest_path.parent
            for member in san_pedro_gravity_manifest["members"]:
                member_path = san_pedro_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(
                        f"Upper San Pedro gravity raw hash drift: {member['path']}"
                    )
            saudi_root = saudi_gravity_manifest_path.parent
            for member in saudi_gravity_manifest["members"]:
                member_path = saudi_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(
                        f"Saudi regional gravity raw hash drift: {member['path']}"
                    )
            ridgecrest_root = ridgecrest_gravity_manifest_path.parent
            for member in ridgecrest_gravity_manifest["members"]:
                member_path = ridgecrest_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(
                        f"Ridgecrest gravity raw hash drift: {member['path']}"
                    )
            tasmania_root = tasmania_gravity_manifest_path.parent
            tasmania_archive = (
                tasmania_root / tasmania_gravity_manifest["archive"]["path"]
            )
            if (
                tasmania_archive.stat().st_size
                != tasmania_gravity_manifest["archive"]["bytes"]
                or sha(tasmania_archive)
                != tasmania_gravity_manifest["archive"]["sha256"]
            ):
                raise RuntimeError("MRT Tasmania gravity raw archive hash drift")
            tasmania_geopackage = tasmania_root / "Gravity_Data_Geopackage.gpkg"
            if sha(tasmania_geopackage) != tasmania_gravity_design[
                "raw_geopackage_sha256"
            ]:
                raise RuntimeError("MRT Tasmania gravity GeoPackage hash drift")
            ga_gravity_catalogue_root = ga_gravity_catalogue_manifest_path.parent
            ga_gravity_catalogue = (
                ga_gravity_catalogue_root
                / ga_gravity_catalogue_manifest["catalogue"]["path"]
            )
            if (
                ga_gravity_catalogue.stat().st_size
                != ga_gravity_catalogue_manifest["catalogue"]["bytes"]
                or sha(ga_gravity_catalogue)
                != ga_gravity_catalogue_manifest["catalogue"]["sha256"]
            ):
                raise RuntimeError("GA national gravity catalogue hash drift")
            for member in ga_gravity_pool["members"]:
                member_path = ga_gravity_catalogue_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(
                        f"GA national gravity raw hash drift: {member['survey_id']}"
                    )
            methods[method] = {
                "license": registered["license"],
                "integrity": registered["integrity"],
                "contract": gate(
                    "passed",
                    "USGS OFR 00-138 contributes 1,520 machine-parseable stations "
                    "with complete Bouguer anomaly, total terrain correction and "
                    "positive per-station complete-Bouguer standard deviation",
                ),
                "cluster_power": gate(
                    "passed",
                    "GA national training-only residual range is 12.5 km; after "
                    "provider-survey capping, train/calibration separation and "
                    "test-to-test packing, 261 sealed independent test surveys remain. "
                    "Training-block paired-CRPS dispersion requires 153 clusters for "
                    "a 10% improvement at one-sided alpha=0.05 and 80% power; coverage "
                    "equivalence requires 223, so the conservative 261-unit pool passes",
                ),
                "dimension": registered["dimensionality"],
                "solver": gate("passed", registered["solver"]["reason"]),
                "reference": gate(
                    "passed", registered["independent_reference"]["reason"]
                ),
                "resource": gate("passed", registered["resource_budget"]["reason"]),
            }
            continue
        if method == "tem":
            tem_raw_root = tem_manifest_path.parent
            for member in tem_manifest["members"]:
                member_path = tem_raw_root / member["path"]
                if member_path.stat().st_size != member["bytes"] or sha(member_path) != member["sha256"]:
                    raise RuntimeError(f"East River TEM raw hash drift: {member['name']}")
            tem_consortium_root = tem_consortium_manifest_path.parent
            for survey in tem_consortium_manifest["surveys"]:
                for member in survey["members"]:
                    member_path = tem_consortium_root / member["path"]
                    if (
                        member_path.stat().st_size != member["bytes"]
                        or sha(member_path) != member["sha256"]
                    ):
                        raise RuntimeError(
                            f"TEM consortium raw hash drift: {member['name']}"
                        )
            maricopa_root = maricopa_manifest_path.parent
            for member in maricopa_manifest["members"]:
                member_path = maricopa_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(f"Maricopa TEM raw hash drift: {member['name']}")
            ga_aem_catalog_root = ga_aem_catalog_manifest_path.parent
            for member in ga_aem_catalog["members"]:
                member_path = ga_aem_catalog_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(
                        f"GA AEM catalogue hash drift: {member['path']}"
                    )
            ga_aem_probe_root = ga_aem_probe_manifest_path.parent
            for member in ga_aem_probe["members"]:
                member_path = ga_aem_probe_root / member["path"]
                if (
                    member_path.stat().st_size != member["bytes"]
                    or sha(member_path) != member["sha256"]
                ):
                    raise RuntimeError(
                        f"GA AEM training probe hash drift: {member['path']}"
                    )
            if (
                tem_manifest["member_count"] != 10
                or tem_manifest["observation_response_interpreted"] is not False
                or tem_contract["passed"] is not True
                or tem_contract["raw_manifest_sha256"] != sha(tem_manifest_path)
                or tem_train["split_sha256"] != sha(EVIDENCE / "east-river-aem-design-split.json")
                or tem_train["contract_sha256"]
                != sha(EVIDENCE / "east-river-aem-contract-readiness.json")
                or tem_train["buffer_rows_interpreted"] != 0
                or tem_train["calibration_rows_interpreted"] != 0
                or tem_train["test_rows_interpreted"] != 0
                or tem_consortium_manifest["member_count"] != 14
                or tem_consortium_manifest["observation_response_interpreted"] is not False
                or tem_consortium_contract["raw_manifest_sha256"]
                != sha(tem_consortium_manifest_path)
                or tem_consortium_contract["surveys"]["hualapai"]["passed"] is not True
                or tem_consortium_contract["surveys"]["yellowstone"]["passed"] is not False
                or tem_consortium_train["sealed_response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or maricopa_manifest["member_count"] != 3
                or maricopa_manifest["observation_response_interpreted"] is not False
                or maricopa_split["raw_manifest_sha256"] != sha(maricopa_manifest_path)
                or maricopa_split["observation_response_values_parsed"] is not False
                or maricopa_contract["passed"] is not True
                or maricopa_contract["raw_manifest_sha256"] != sha(maricopa_manifest_path)
                or maricopa_contract["observation_response_values_parsed"] is not False
                or maricopa_train["split_sha256"]
                != sha(EVIDENCE / "maricopa-aem-design-split.json")
                or maricopa_train["contract_sha256"]
                != sha(EVIDENCE / "maricopa-aem-contract-readiness.json")
                or maricopa_train["sealed_response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or maricopa_train["correlation_adjusted_test_cluster_upper_bound"] != 1
                or ga_aem_catalog["feature_count"] != 72
                or ga_aem_catalog["aem_response_values_interpreted"] != 0
                or ga_aem_design["catalogue_manifest_sha256"]
                != sha(ga_aem_catalog_manifest_path)
                or ga_aem_design["eligible_open_license_product_count"] != 71
                or ga_aem_design["unique_survey_count"] != 40
                or ga_aem_design["partition_counts"]["test"] != 394
                or ga_aem_design["design_power_gate_possible"] is not True
                or ga_aem_design["test_unseal_count"] != 0
                or ga_aem_probe["selection_design_sha256"]
                != sha(EVIDENCE / "geoscience-australia-aem-design.json")
                or ga_aem_probe["covered_design_roles"] != ["train"]
                or ga_aem_probe_contract["raw_manifest_sha256"]
                != sha(ga_aem_probe_manifest_path)
                or ga_aem_probe_contract["located_data"]["row_count"] != 442601
                or ga_aem_probe_contract["maximum_training_range_km"] != 1.536
                or ga_aem_probe_contract["exact_gate_center_times_present"] is not True
                or ga_aem_probe_contract["formal_contract_ready"] is not False
                or ga_aem_probe_contract["test_unseal_count"] != 0
                or ga_aem_multisystem_manifest["total_bytes"] != 921757368
                or ga_aem_multisystem_inventory["observation_payload_members_opened"] != 0
                or ga_aem_multisystem_contract["skytem_contract_ready"] is not True
                or ga_aem_multisystem_contract["vtem_contract_ready"] is not False
                or ga_aem_multisystem_split["partition_counts"]
                != {"train": 523, "buffer": 511, "calibration": 170, "test": 418}
                or ga_aem_multisystem_split[
                    "minimum_nonbuffer_cross_role_center_distance_km"
                ] != 87.61
                or ga_aem_multisystem_train["split_sha256"]
                != sha(ga_aem_multisystem_split_path)
                or ga_aem_multisystem_train["sealed_response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or ga_aem_multisystem_train[
                    "formal_national_correlation_gate_passes"
                ] is not False
            ):
                raise RuntimeError("East River TEM evidence drift")
            methods[method] = {
                "license": gate("passed", "USGS DOI 10.5066/P949ZCZ8, CC0/public domain"),
                "integrity": gate(
                    "passed",
                    f"{tem_manifest['member_count']} protected members, {tem_manifest['total_bytes']} bytes, SHA-256 verified",
                ),
                "contract": gate(
                    "passed",
                    "VTEM ET full waveform, concentric-coplanar Z geometry, transmitter current/loop, "
                    "52 time gates, normalized Z response and per-observation DATASTD verified",
                ),
                "cluster_power": gate(
                    "blocked",
                    f"East River cells={tem_split['candidate_500m_cell_counts']}; "
                    f"GA macroblock design has {ga_aem_multisystem_split['partition_counts']['test']} "
                    "sealed 55-km test centers separated by at least 87.61 km from "
                    "nonbuffer training/calibration centers; VTEM/SkyTEM train-only "
                    "descriptive ranges are 5/7 km, but two systems/surveys do not "
                    "qualify the national unsampled-survey tolerance bound",
                    "freeze response-blind located-line products spanning the national "
                    "GA AEM systems, qualify exact waveforms/gates and uncertainty, and "
                    "estimate national correlation and paired-CRPS effect using training only",
                ),
                "dimension": gate(
                    "passed",
                    f"fixed training-gate variograms select {tem_train['dimensionality']['selected']} path",
                ),
                "solver": gate("passed", registered["solver"]["reason"]),
                "reference": gate(
                    "passed",
                    registered["independent_reference"]["reason"],
                ),
                "resource": gate(
                    "passed",
                    registered["resource_budget"]["reason"],
                ),
            }
            continue
        if method == "tdip":
            methods[method] = {
                "license": gate(registered["license"]["status"], registered["license"]["reason"]),
                "integrity": gate(registered["integrity"]["status"], registered["integrity"]["reason"]),
                "contract": gate(
                    "passed",
                    "training-only adapter validates ABMN, potential/current, delay, 20 chargeability windows/durations and N/R discrepancy error evidence",
                ),
                "cluster_power": gate(
                    "blocked",
                    f"date observations split={tdip_split['counts']}; training-only correlation length={tdip_train['temporal_correlation_length_days']} days gives effective clusters={tdip_train['effective_cluster_counts']}; "
                    "the IP-VAE paper documents 110 field surveys and 1,600,319 "
                    "decays, but its public software archive contains four pretrained "
                    "weight files and no likely field-observation files; NTGS adds "
                    "two downloadable, contract-rich campaigns (Kroda and Arunta), "
                    "but their company-report item pages declare no reuse license; "
                    "a response-blind GEMIS catalogue has 619 nominal search items, "
                    "218 with digital attachments and only 16 with explicitly named "
                    "IP/raw attachments, none yet license- or cluster-qualified; coverage "
                    "requires 223 independent test clusters and paired-CRPS effect is unavailable",
                    "obtain enough correlation-separated campaigns and estimate paired-CRPS effect using training only; never count dates, N/R or windows as independent when correlated",
                ),
                "dimension": gate(
                    "passed",
                    f"training-only dimensionality={tdip_train['dimensionality']['selected']}; repeated profile dates remain clusters, not spatial axes",
                ),
                "solver": gate("passed", registered["solver"]["reason"]),
                "reference": gate("passed", registered["independent_reference"]["reason"]),
                "resource": gate(
                    "passed",
                    f"representative development measurements and fail-closed abort limits frozen; formal_wp8_1_evidence={tdip_path['formal_wp8_1_evidence']}",
                ),
            }
            continue
        if method == "magnetic":
            if (
                magic_prior["training_contributions_interpreted"] != 64
                or magic_prior["buffer_contributions_interpreted"] != 0
                or magic_prior["calibration_contributions_interpreted"] != 0
                or magic_prior["test_contributions_interpreted"] != 0
                or magic_prior["complete_vector_rows"] != 5905
                or magic_prior["complete_vector_contributions"] != 21
                or magic_prior["prior_gate_passed"] is not True
                or magic_prior["held_out_response_values_read"] is not False
                or texas_magnetic["passed"] is not True
                or texas_magnetic["response_archives_downloaded"] is not False
                or texas_magnetic["response_values_interpreted"] is not False
                or texas_access["response_bytes_read"] != 0
                or texas_access["direct_archive_available_without_human_challenge"]
                is not False
                or mountain_magnetic_train["split_sha256"]
                != sha(EVIDENCE / "mountain-pass-magnetic-design-split.json")
                or mountain_magnetic_train["remanence_prior_sha256"]
                != sha(EVIDENCE / "magic-training-remanence-prior.json")
                or mountain_magnetic_train["sealed_response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or mountain_magnetic_train[
                    "correlation_adjusted_test_cluster_upper_bound"
                ]
                != 15
                or mountain_magnetic_train["dimensionality"]["passed"] is not True
                or arkansas_magnetic_contract["observation_contract_passed"] is not True
                or arkansas_magnetic_contract["formal_uncertainty_model_ready"] is not False
                or arkansas_magnetic_contract["calibration_responses_interpreted"] != 0
                or arkansas_magnetic_contract["test_responses_interpreted"] != 0
                or arkansas_magnetic_train["response_policy"]["buffer_rows_interpreted"] != 0
                or arkansas_magnetic_train["response_policy"]["calibration_rows_interpreted"] != 0
                or arkansas_magnetic_train["response_policy"]["test_rows_interpreted"] != 0
                or arkansas_magnetic_train["conservative_spatial_correlation_range_m"]
                != 21000.0
                or arkansas_magnetic_train["correlation_adjusted_test_clusters"] != 0
                or arkansas_magnetic_train["dimensionality"]["passed"] is not True
                or ga_magnetic_design["formal_excluded_dataset_numbers"] != [17638]
                or ga_magnetic_design["partition_counts"]
                != {"train": 1123, "buffer": 404, "calibration": 400, "test": 645}
                or ga_magnetic_design["magnetic_response_values_interpreted"] != 0
                or ga_magnetic_design["test_unseal_count"] != 0
                or ga_magnetic_contract["coverage"]["geometry_response"][
                    "partition_cell_counts"
                ]["test"]
                != 305
                or ga_magnetic_contract["coverage"]["plus_explicit_corrections"][
                    "partition_cell_counts"
                ]["test"]
                != 7
                or ga_magnetic_contract["coverage"]["plus_uncertainty"]["product_count"]
                != 0
                or ga_magnetic_contract["formal_contract_ready"] is not False
                or ga_magnetic_contract["test_unseal_count"] != 0
                or ga_magnetic_training["total_training_rows_interpreted"] != 650783
                or ga_magnetic_training["response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or ga_magnetic_training["conservative_pilot_correlation_range_m"]
                != 17500.0
                or ga_magnetic_training["total_crossover_bins"] != 1565
                or ga_magnetic_training["pilot_power_count_possible"] is not True
                or ga_magnetic_training["national_correlation_ready"] is not False
                or ga_magnetic_training["formal_contract_ready"] is not False
                or ga_magnetic_training["test_unseal_count"] != 0
                or ga_magnetic_expansion["products_sampled"] != 14
                or ga_magnetic_expansion["total_training_rows_interpreted"] != 6233124
                or ga_magnetic_expansion["response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or ga_magnetic_expansion["conservative_pilot_correlation_range_m"]
                != 22500.0
                or ga_magnetic_expansion["total_crossover_bins"] != 7210
                or ga_magnetic_expansion["pilot_power_count_possible"] is not True
                or ga_magnetic_expansion["national_correlation_ready"] is not False
                or ga_magnetic_expansion["formal_contract_ready"] is not False
                or ga_magnetic_expansion["test_unseal_count"] != 0
                or ga_magnetic_probability["sampled_cells"] != 20
                or ga_magnetic_probability["successful_sampled_cells"] != 18
                or ga_magnetic_probability["all_sampled_cells_succeed"] is not False
                or ga_magnetic_probability[
                    "maximum_observed_correlation_range_m"
                ]
                != 100000.0
                or ga_magnetic_probability["censored_product_count"] != 1
                or ga_magnetic_probability["response_rows_interpreted"]
                != {"buffer": 0, "calibration": 0, "test": 0}
                or ga_magnetic_probability[
                    "formal_correlation_power_gate_passes"
                ]
                is not False
                or ga_magnetic_probability["test_unseal_count"] != 0
            ):
                raise RuntimeError("magnetic expansion evidence drift")
            test_cells = mountain_magnetic["counts"]["test"]["spatial_cells_1km"]
            methods[method] = {
                "license": gate(registered["license"]["status"], registered["license"]["reason"]),
                "integrity": gate(registered["integrity"]["status"], registered["integrity"]["reason"]),
                "contract": gate(
                    "passed",
                    f"Mountain Pass survey geometry/correction fields plus training-only MagIC "
                    f"NRM prior={magic_prior['complete_vector_rows']} complete vectors from "
                    f"{magic_prior['complete_vector_contributions']} contributions; western "
                    "Arkansas independently supplies line/flight, height, base-station, "
                    "correction and vector-field channels; magnitude units remain separate",
                ),
                "cluster_power": gate(
                    "blocked",
                    f"Mountain Pass outcome-blind test design has {test_cells} 1-km cells; "
                    f"training-only 1.5-km correlation gives an effective upper bound of "
                    f"{mountain_magnetic_train['correlation_adjusted_test_cluster_upper_bound']}; "
                    "western Arkansas has 366 design test cells but its training-only "
                    f"{arkansas_magnetic_train['conservative_spatial_correlation_range_m']/1000:g}-km "
                    "range excludes every test cell under the frozen 20-km macroblock split; "
                    "the GA national DDS catalogue has 305 geometry/height/response design "
                    "test cells, but only 7 with explicit correction declarations and none "
                    "with an uncertainty declaration; its six-state training pilot gives "
                    "a 17.5-km maximum range and 1565 crossover bins but covers only six "
                    "of 598 products; its 14-product state-by-era expansion adds "
                    "6,233,124 training rows and 7,210 crossover bins with a 22.5-km "
                    "maximum; its preregistered cell-weighted probability audit then "
                    f"passed only {ga_magnetic_probability['successful_sampled_cells']}/"
                    f"{ga_magnetic_probability['sampled_cells']} cells, observed an "
                    "82.5-km range and one range censored at 100 km, so the formal "
                    "unsampled-survey tolerance rule failed; "
                    "Texas AIB contract passes with "
                    "166,594 line-km but its 4,236,679,294-byte response archive remains sealed/not "
                    f"downloaded ({texas_access['status']})",
                    external_contract[method],
                ),
                "dimension": gate(
                    "passed",
                    "training-only regional trend, 1.5-km residual range, 124 flight-line spectra, height sensitivity and MagIC remanence prior select 3-D vector magnetization",
                ),
                "solver": gate(registered["solver"]["status"], registered["solver"]["reason"]),
                "reference": gate(
                    registered["independent_reference"]["status"],
                    registered["independent_reference"]["reason"],
                ),
                "resource": gate(
                    registered["resource_budget"]["status"],
                    registered["resource_budget"]["reason"],
                ),
            }
            continue
        if method == "dc":
            if (
                krause_ert_manifest["doi"] != "10.5066/P91Z1HKN"
                or not krause_ert_manifest["license"].startswith("CC0")
                or krause_ert_contract["raw_manifest_sha256"]
                != sha(krause_ert_manifest_path)
                or krause_ert_contract["measurement_count"] != 13605
                or krause_ert_contract["profile_count"] != 4
                or krause_ert_contract["reciprocal_configuration_group_count"] != 0
                or krause_ert_contract["empirical_error_model_possible"] is not False
                or krause_ert_contract[
                    "direct_per_observation_standard_deviation_present"
                ] is not False
                or krause_ert_contract["test_unseal_count"] != 0
            ):
                raise RuntimeError("Krause ERT contract evidence drift")
            if (
                svalbard_ert_manifest["license"] != "cc-by-4.0"
                or svalbard_ert_contract["raw_manifest_sha256"]
                != sha(svalbard_ert_manifest_path)
                or svalbard_ert_contract["raw_bin_profile_count"] != 18
                or svalbard_ert_contract["topography_profile_count"] != 18
                or svalbard_ert_contract["reciprocal_profile_count"] != 10
                or svalbard_ert_contract["reciprocal_paired_row_count"] != 30426
                or svalbard_ert_contract[
                    "profiles_with_complete_abmn_response_and_direct_error"
                ] != 10
                or svalbard_ert_contract["training_observation_contract_ready"]
                is not True
                or svalbard_ert_contract["formal_cluster_power_gate_passes"]
                is not False
                or svalbard_ert_contract["test_unseal_count"] != 0
            ):
                raise RuntimeError("Svalbard ERT contract evidence drift")
            if (
                cpers_manifest["measurement_payloads_downloaded"] != 0
                or cpers_catalogue["raw_manifest_sha256"] != sha(cpers_manifest_path)
                or cpers_catalogue["distinct_profile_count"] != 423
                or cpers_catalogue["raw_survey_count"] != 292
                or cpers_catalogue["nominal_profile_power_threshold_exceeded"]
                is not True
                or cpers_catalogue["nominal_raw_survey_power_threshold_exceeded"]
                is not True
                or cpers_catalogue["permission_contract"]["permission_obtained"]
                is not False
                or cpers_catalogue["formal_contract_ready"] is not False
                or cpers_catalogue["formal_cluster_power_gate_passes"] is not False
                or cpers_catalogue["test_unseal_count"] != 0
            ):
                raise RuntimeError("CPERS public catalogue evidence drift")
            methods[method] = {
                "license": gate(
                    "passed",
                    "Little Colorado and Krause Springs are USGS public-domain/CC0; "
                    "Ny-Ålesund ERT is CC BY 4.0",
                ),
                "integrity": gate(
                    "passed",
                    f"Krause Springs {len(krause_ert_manifest['members'])} members "
                    f"({krause_ert_manifest['total_bytes']} bytes) match provider MD5 "
                    "and local SHA-256; Ny-Ålesund Repository.zip matches provider "
                    f"MD5 and local SHA-256 ({svalbard_ert_manifest['total_bytes']} frozen bytes)",
                ),
                "contract": gate(
                    "passed",
                    "Ny-Ålesund supplies a complete training-side reciprocal DD "
                    "contract: EPSG:32633 electrode geometry, ABMN, resistance, "
                    "reciprocal mean and direct normal-reciprocal error for all "
                    "30,426 paired rows across 10 profiles",
                ),
                "cluster_power": gate(
                    "blocked",
                    "Krause adds four profiles and Ny-Ålesund adds 18 profiles "
                    "(10 with reciprocal errors) from one campaign; no DC consortium "
                    "currently qualifies for 223 correlation-adjusted leakage-safe "
                    "clusters; CPERS v2 has a sufficient nominal catalogue "
                    "(423 profiles; 292 raw surveys), but its policy requires "
                    "contributor permission before use and no permission or "
                    "training-only correlation audit is frozen",
                    external_contract[method],
                ),
                "dimension": gate(
                    registered["dimensionality"]["status"],
                    registered["dimensionality"]["reason"],
                ),
                "solver": gate(
                    registered["solver"]["status"], registered["solver"]["reason"]
                ),
                "reference": gate(
                    registered["independent_reference"]["status"],
                    registered["independent_reference"]["reason"],
                ),
                "resource": gate(
                    registered["resource_budget"]["status"],
                    registered["resource_budget"]["reason"],
                ),
            }
            continue
        if method == "csamt":
            if (
                mount_st_helens_csamt_manifest["station_count"] != 13
                or mount_st_helens_csamt_contract["raw_manifest_sha256"]
                != sha(mount_st_helens_csamt_manifest_path)
                or mount_st_helens_csamt_contract[
                    "all_edi_have_rho_phase_and_error_arrays"
                ] is not True
                or mount_st_helens_csamt_contract["controlled_source_station_upper_bound"]
                != 12
                or mount_st_helens_csamt_contract["source_contract"][
                    "exact_source_coordinates_present"
                ] is not False
                or mount_st_helens_csamt_contract[
                    "available_grounded_finite_line_solver_compatible"
                ] is not False
                or mount_st_helens_csamt_contract["observation_contract_ready"]
                is not False
                or mount_st_helens_csamt_contract["test_unseal_count"] != 0
            ):
                raise RuntimeError("Mount St. Helens CSAMT evidence drift")
            if (
                hualapai_csamt_manifest["license"] != "CC0-1.0"
                or hualapai_csamt_manifest["provider_member_count"] != 7
                or hualapai_csamt_manifest["metadata_snapshot_count"] != 2
                or hualapai_csamt_manifest["total_resource_count"] != 9
                or hualapai_csamt_contract["raw_manifest_sha256"]
                != sha(hualapai_csamt_manifest_path)
                or hualapai_csamt_contract["raw_line_file_count"] != 9
                or hualapai_csamt_contract["station_line_file_count"] != 9
                or hualapai_csamt_contract["inversion_line_file_count"] != 9
                or hualapai_csamt_contract["receiver_station_count"] != 543
                or hualapai_csamt_contract["scope"] != "permanently-training-only"
                or hualapai_csamt_contract["field_validation_eligible"] is not False
                or hualapai_csamt_contract["sealed_test_accessed"] is not False
                or hualapai_csamt_contract["source_coordinates_imputed"] is not False
                or hualapai_csamt_contract["site_mapping"]["lines_are_sites"] is not False
                or hualapai_csamt_contract["observation_contract_ready"] is not False
                or hualapai_csamt_contract["formal_cluster_power_gate_passes"] is not False
                or hualapai_reconciliation["raw_manifest_sha256"]
                != sha(hualapai_csamt_manifest_path)
                or hualapai_reconciliation["contract_sha256"]
                != sha(EVIDENCE / "usgs-hualapai-csamt-contract.json")
                or hualapai_reconciliation["legacy_hualapai_test_line_count"] != 6
                or hualapai_reconciliation["legacy_hualapai_test_role_status"]
                != "contaminated_and_superseded"
                or hualapai_reconciliation["hualapai_sealed_test_eligible"] is not False
                or hualapai_reconciliation["hualapai_formal_contribution"] != 0
            ):
                raise RuntimeError("Hualapai CSAMT evidence drift")
            granularity = csamt_split["provider_raw_granularity_audit"]
            methods[method] = {
                "license": gate(registered["license"]["status"], registered["license"]["reason"]),
                "integrity": gate(registered["integrity"]["status"], registered["integrity"]["reason"]),
                "contract": gate(
                    "blocked",
                    "common GGT-30 transmitter/GDP32-II receiver and Ex/Hy geometry documented; "
                    "per-acquisition transmitter endpoints and native error/covariance remain absent; "
                    "the CC0 Hualapai release adds 543 georeferenced stations and "
                    "official MTM source geometry/error floors, but the entire package "
                    "has been interpreted and is permanently training-only; "
                    "Mount St. Helens adds rho/phase error arrays but its approximate "
                    "inductive source lacks coordinates/orientation/moment/waveform and "
                    "does not match the grounded finite-line solver; "
                    "current public-data audit found no contract-complete replacement",
                    external_contract[method],
                ),
                "cluster_power": gate(
                    "blocked",
                    f"coordinate-unique stations={csamt_split['unique_station_coordinates']}; "
                    f"outcome-blind 250-m test cells={csamt_split['candidate_250m_cell_counts']['test']} "
                    f"but provider raw granularity is {granularity['provider_station_lines']} whole-line members, "
                    f"all {granularity['station_lines_mixing_candidate_partitions']} lines mix partitions; "
                    f"safe line-level upper bound={granularity['line_level_split_upper_bound']} <223; "
                    f"the Hualapai station count is {hualapai_csamt_contract['receiver_station_count']} "
                    f"but it is packaged in only {hualapai_csamt_contract['available_provider_line_clusters']} "
                    "provider lines, contributes zero sealed/formal clusters, and has no frozen correlation length",
                    "obtain station-granular sealed raw exports plus transmitter GPS/current logs, or a new "
                    "consortium with at least 223 independently packaged and correlation-separated clusters",
                ),
                "dimension": gate("blocked", "training response remains sealed by provider line granularity", "obtain station-granular training members"),
                "solver": gate(registered["solver"]["status"], registered["solver"]["reason"]),
                "reference": gate(
                    registered["independent_reference"]["status"],
                    registered["independent_reference"]["reason"],
                ),
                "resource": gate(
                    registered["resource_budget"]["status"],
                    registered["resource_budget"]["reason"],
                ),
            }
            continue
        contract_missing = "; ".join(observed.get("missing", []))
        if method == "sip_fdip":
            contract_missing += (
                "; current public-data audit found only small laboratory or "
                "repeated-column spectra, not a contract-complete field replacement"
            )
        methods[method] = {
            "license": gate(registered["license"]["status"], registered["license"]["reason"]),
            "integrity": gate(registered["integrity"]["status"], registered["integrity"]["reason"]),
            "contract": gate("blocked", contract_missing, external_contract[method]),
            "cluster_power": gate(
                "blocked",
                f"candidate clusters={observed.get('available_clusters')}; no frozen buffered split and training-only CRPS effect",
                external_contract[method],
            ),
            "dimension": gate(
                registered["dimensionality"]["status"],
                registered["dimensionality"]["reason"],
                (
                    "complete field contract and run training-only diagnostic"
                    if registered["dimensionality"]["status"] != "passed"
                    else None
                ),
            ),
            "solver": gate(registered["solver"]["status"], registered["solver"]["reason"]),
            "reference": gate(
                registered["independent_reference"]["status"],
                registered["independent_reference"]["reason"],
            ),
            "resource": gate(
                registered["resource_budget"]["status"],
                registered["resource_budget"]["reason"],
            ),
        }
    result = {
        "schema_version": "wp8-0-final-requirement-audit-v1",
        "status": "failed",
        "wp8_1_allowed": False,
        "methods": methods,
        "mt_seal_verification": {
            "raw_member_count": len(checked),
            "all_raw_members_readonly": True,
            "all_member_hashes_match": True,
            "merkle_root_matches": True,
            "train_members_interpreted": train["training_members_interpreted"],
            "calibration_members_interpreted": 0,
            "test_members_interpreted": 0,
            "test_unseal_count": 0,
            "xml_member_count": len(xml_checked),
            "all_xml_members_readonly": True,
            "all_xml_member_hashes_match": True,
            "xml_role_counts": xml_role_counts,
            "xml_training_members_interpreted": xml_covariance["training_members_interpreted"],
            "xml_buffer_members_interpreted": xml_covariance["buffer_members_interpreted"],
            "xml_calibration_members_interpreted": xml_covariance["calibration_members_interpreted"],
            "xml_test_members_interpreted": xml_covariance["test_members_interpreted"],
            "xml_covariance_periods_checked": xml_covariance["covariance_periods_checked"],
        },
        "tdip_seal_verification": {
            "cluster_unit": "acquisition_date",
            "train_dates_interpreted": tdip_train["training_dates_interpreted"],
            "buffer_dates_interpreted": 0,
            "calibration_dates_interpreted": 0,
            "test_dates_interpreted": 0,
            "test_unseal_count": 0,
            "sealed_test_dates": tdip_split["counts"]["test"],
            "temporal_correlation_length_days": tdip_train["temporal_correlation_length_days"],
            "effective_test_clusters": tdip_train["effective_cluster_counts"]["test"],
            "exposed_dates_excluded": tdip_split["excluded"]["endpoint_exposed"],
            "unpaired_dates_excluded": tdip_split["excluded"]["missing_reciprocal"],
        },
        "external_blocker_artifact": "wp8-0-final-infeasibility.json",
        "controlled_source_public_data_audit_sha256": sha(
            EVIDENCE / "controlled-source-public-data-audit.json"
        ),
        "sip_fdip_public_data_audit_sha256": sha(
            EVIDENCE / "sip-fdip-public-data-audit.json"
        ),
        "zenodo_tdip_full_decay_contract_sha256": sha(
            EVIDENCE / "zenodo-tdip-full-decay-contract.json"
        ),
        "zenodo_tdip_full_decay_training_diagnostics_sha256": sha(
            EVIDENCE / "zenodo-tdip-full-decay-training-diagnostics.json"
        ),
        "ip_vae_public_release_sha256": sha(
            EVIDENCE / "ip-vae-public-release.json"
        ),
        "ntgs_tdip_training_candidates_sha256": sha(
            EVIDENCE / "ntgs-tdip-training-candidates.json"
        ),
        "ntgs_ip_open_search_catalogue_sha256": sha(
            EVIDENCE / "ntgs-ip-open-search-catalogue.json"
        ),
        "ntgs_ip_explicit_candidates_sha256": sha(
            EVIDENCE / "ntgs-ip-explicit-candidates.json"
        ),
        "pangaea_brittany_ert_training_diagnostics_sha256": sha(
            EVIDENCE / "pangaea-brittany-ert-training-diagnostics.json"
        ),
        "svalbard_ert_training_contract_sha256": sha(
            EVIDENCE / "svalbard-ert-training-contract.json"
        ),
        "cpers_public_catalogue_sha256": sha(
            EVIDENCE / "cpers-public-catalogue.json"
        ),
        "guidel_sip_contract_sha256": sha(EVIDENCE / "guidel-sip-contract.json"),
        "guidel_sip_training_diagnostics_sha256": sha(
            EVIDENCE / "guidel-sip-training-diagnostics.json"
        ),
        "guidel_sip_repeatability_sha256": sha(
            EVIDENCE / "guidel-sip-repeatability.json"
        ),
        "tuwien_ice_sip_training_diagnostics_sha256": sha(
            EVIDENCE / "tuwien-ice-sip-training-diagnostics.json"
        ),
        "wfem_public_contract_references_sha256": sha(
            EVIDENCE / "wfem-public-contract-references.json"
        ),
        "usgs_hualapai_csamt_contract_sha256": sha(
            EVIDENCE / "usgs-hualapai-csamt-contract.json"
        ),
    }
    (EVIDENCE / "final-requirement-audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"methods": len(methods), "mt": result["mt_seal_verification"]}))


if __name__ == "__main__":
    main()
