import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/wp8/evidence/feasibility-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_po_river_repairs_dc_contract_without_overstating_clusters() -> None:
    design_path = EVIDENCE / "po-river-dc-streamer-design-v2.json"
    design = load(design_path.name)
    audit = load("po-river-dc-streamer-training-audit-v2.json")
    assert audit["design_sha256"] == sha256(design_path)
    assert design["partition_counts"]["quarantine_response_exposed"] == 8
    assert design["remaining_test_population_sealed"] is True
    assert audit["per_observation_standard_deviation_present"] is True
    assert audit["remaining_test_response_rows_interpreted"] == 0
    assert audit["correlation_separated_test_station_count"] == 38
    assert audit["cluster_gate_passed"] is False
    assert audit["power_gate_passed"] is False


def test_tdip_training_only_audit_keeps_sealed_roles_closed() -> None:
    design = load("zenodo-tdip-field-design-v1.json")
    audit = load("zenodo-tdip-training-audit-v1.json")
    assert design["selection_frozen_before_response_access"] is True
    assert design["archive_members_extracted"] is False
    assert audit["training_groups"] == ["n12_n13", "n7_n6_n1"]
    assert audit["total_ip_observations"] == 122_892
    assert audit["per_observation_standard_deviation_contract"] is True
    assert audit["observed_processed_time_windows"] == 11
    assert audit["twenty_window_contract_ready"] is False
    assert audit["test_responses_interpreted"] == 0
    assert audit["power_gate_possible"] is False


def test_usgs_aem_training_expansion_is_training_only_and_unit_aware() -> None:
    design_path = EVIDENCE / "usgs-aem-training-expansion-design-v1.json"
    design = load(design_path.name)
    audit = load("usgs-aem-training-response-diagnostics-v1.json")
    assert design["selection_frozen_before_payload_access"] is True
    assert design["usgs_calibration_surveys"] == []
    assert design["usgs_test_surveys"] == []
    assert audit["design_sha256"] == sha256(design_path)
    assert audit["completed_netcdf_training_survey_count"] >= 3
    assert audit["training_response_values_interpreted"] >= 9_695_455
    semantics = {record["uncertainty_semantics"] for record in audit["records"]}
    assert semantics == {
        "absolute_standard_deviation",
        "relative_standard_deviation_factor",
    }
    assert audit["calibration_responses_interpreted"] == 0
    assert audit["test_responses_interpreted"] == 0
    assert audit["power_gate_passed"] is False
    tempest = load("usgs-tempest-2022-training-diagnostics-v1.json")
    assert tempest["design_sha256"] == sha256(design_path)
    assert tempest["processed_rows"] == 449_501
    assert tempest["unique_lines"] == 385
    assert tempest["valid_response_noise_pairs"] == 13_485_030
    assert tempest["formal_response_uncertainty_contract_ready"] is True
    assert tempest["test_responses_interpreted"] == 0
    assert tempest["power_gate_passed"] is False


def test_csamt_whole_line_split_exposes_training_only() -> None:
    split_path = EVIDENCE / "csamt-line-split-v2.json"
    manifest_path = (
        ROOT
        / "validation/wp8/data/csamt-consortium-line-split-v2"
        / "training-only/training-manifest.json"
    )
    split = json.loads(split_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    contract = load("csamt-training-line-contract-v2.json")
    assert split["selection_frozen_before_response_access"] is True
    assert split["partition_line_counts"] == {
        "test": 14,
        "buffer": 4,
        "train": 9,
        "calibration": 3,
    }
    assert manifest["design_sha256"] == sha256(split_path)
    assert manifest["extracted_roles"] == ["train"]
    assert manifest["test_response_members_opened"] == 0
    assert contract["training_manifest_sha256"] == sha256(manifest_path)
    assert contract["frequency_range_hz"] == [0.25, 8192.0]
    assert contract["components"] == ["Ex", "Hy"]
    assert contract["exact_transmitter_endpoints_present"] is False
    assert contract["formal_finite_source_observation_contract_ready"] is False
    assert contract["line_level_test_cluster_upper_bound"] == 14


def test_baotu_wfem_split_proves_payload_contract_is_incomplete() -> None:
    split_path = EVIDENCE / "baotu-wfem-line-split-v1.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    audit = load("baotu-wfem-training-audit-v1.json")
    assert split["selection_frozen_before_response_interpretation"] is True
    assert split["partition_line_counts"] == {
        "test": 14,
        "train": 10,
        "buffer": 2,
        "calibration": 1,
    }
    assert audit["design_sha256"] == sha256(split_path)
    assert audit["training_rows_interpreted"] == 44_074
    assert audit["observed_columns"] == ["Station", "Fre", "Rho_mn"]
    assert audit["receiver_coordinates_present"] is False
    assert audit["source_geometry_present"] is False
    assert audit["per_observation_error_present"] is False
    assert audit["formal_observation_contract_ready"] is False
    assert audit["line_level_test_cluster_upper_bound"] == 14
    assert audit["test_response_values_interpreted"] == 0


def test_guidel_repairs_sip_observation_contract_only() -> None:
    training = load("guidel-sip-training-diagnostics.json")
    repeatability = load("guidel-sip-repeatability.json")

    assert training["partition"] == "training-only"
    assert training["processing_contract"]["abmn_quadrupoles"] == 56
    assert training["processing_contract"]["selected_frequency_count"] == 30
    assert (
        training["processing_contract"]["complex_observations_after_processing"]
        == 1_680
    )
    assert (
        training["geometry_contract"][
            "relative_geometry_reconstructable_without_interpolation"
        ]
        is True
    )
    assert training["test_unseal_count"] == 0
    adjacent = repeatability["adjacent_dipoles_frequency_ge_0_1_hz"]
    assert adjacent["complex_observations"] == 364
    assert adjacent["relative_amplitude_sigma"]["p95"] < 0.01
    assert adjacent["phase_sigma_mrad"]["p95"] < 9
    assert (
        repeatability["interpretation"]["repeat_based_uncertainty_contract"]
        == "passed_training_only"
    )
    assert repeatability["interpretation"]["formal_cluster_gate"] == "failed"
    assert repeatability["interpretation"]["formal_power_gate"] == "failed"
    assert repeatability["test_unseal_count"] == 0


def test_martin2020_sip_strengthens_training_without_overstating_clusters() -> None:
    audit = load("zenodo-martin2020-field-sip-training-audit-v1.json")
    archive = ROOT / audit["source"]["archive_path"]

    assert audit["partition"] == "permanently-training-only"
    assert archive.stat().st_size == audit["source"]["archive_bytes"]
    assert sha256(archive) == audit["source"]["archive_sha256"]
    assert audit["profiles"]["IP1"]["quadrupole_count"] == 522
    assert audit["profiles"]["IP1"]["frequency_count"] == 14
    assert audit["profiles"]["IP5"]["quadrupole_count"] == 535
    assert audit["profiles"]["IP5"]["frequency_count"] == 11
    assert audit["totals"]["complex_observations"] == 13_193
    assert audit["totals"]["unique_quadrupole_midpoints_upper_bound"] == 196
    gate = audit["formal_gate_assessment"]
    assert gate["minimum_independent_test_clusters"] == 223
    assert gate["independent_profile_upper_bound"] == 2
    assert gate["cluster_gate_passes"] is False
    assert gate["power_gate_passes"] is False
    assert audit["formal_test_responses_opened"] == 0
    assert audit["test_unseal_count"] == 0
    assert audit["formal_test_result"] is None


def test_sevier_csamt_candidate_does_not_overstate_unavailable_payload() -> None:
    candidate = load("usgs-sevier-csamt-public-candidate-v1.json")

    assert candidate["license"] == "US Government public domain"
    assert candidate["sciencebase_file_inventory"]["declared_bytes"] == 283_450
    assert (
        candidate["sciencebase_file_inventory"]["declared_md5"]
        == "b219f6e62627772b020bb35d87be6211"
    )
    assert candidate["sciencebase_file_inventory"]["published_flag"] is False
    assert (
        candidate["sciencebase_file_inventory"][
            "anonymous_download_http_status_observed"
        ]
        == 404
    )
    assert candidate["payload_acquisition"]["downloaded"] is False
    assert candidate["payload_acquisition"]["raw_response_values_interpreted"] == 0
    assert candidate["formal_assessment"]["observation_contract_ready"] is False


def test_wuxi_csamt_training_evidence_preserves_test_seal() -> None:
    design = load("geodoi-wuxi-csamt-outcome-blind-design-v1.json")
    training = load("geodoi-wuxi-csamt-training-audit-v1.json")

    assert design["freeze"]["response_values_seen"] is False
    assert design["processed_line_roles"]["test"] == [7800, 8000]
    assert design["raw_acquisition_date_roles"]["test"] == [
        "20110406",
        "20110408",
    ]
    assert design["workbook_geometry_protocol"]["test_response_unseals"] == 0
    assert training["test_unseals"] == 0
    assert training["archive_inventory"]["processed_csamt_lines"] == 14
    assert training["archive_inventory"]["training_cmd_cms_pairs"] == 64
    observations = training["training_cmd_observations"]
    assert observations["frequency_blocks"] == 1723
    assert observations["unique_frequency_count"] == 27
    assert observations["rows_with_percent_uncertainty_fields"] == 13_784
    geometry = training["fieldwork_log_and_coordinate_audit"]
    assert geometry["source_receiver_distance_m"] == 7000
    assert geometry["transmitter_dipole_length_m"] == 1550
    assert geometry["coordinate_rows"] == 803
    assert geometry["receiver_coordinates_reconstructable"] is True
    assert geometry["test_response_values_read"] == 0
    contract = training["contract_assessment"]
    assert contract["receiver_coordinates_reconstructable_from_field_log_and_coordinate_workbook"] is True
    assert contract["transmitter_endpoint_coordinates_present"] is False
    assert contract["observation_contract_passed"] is False
    assert contract["cluster_contract_passed"] is False
    assert contract["power_contract_passed"] is False


def test_ntgs_cr20130857_csamt_design_audit_is_response_blind() -> None:
    audit = load("ntgs-cr20130857-csamt-design-audit-v1.json")
    archive = ROOT / audit["archive_path"]

    assert archive.stat().st_size == audit["archive_bytes"]
    assert sha256(archive) == audit["archive_sha256"]
    assert audit["published_line_count"] == 13
    assert audit["published_sounding_count"] == 205
    assert audit["coordinate_file_count"] == 13
    assert audit["coordinate_row_count"] == 217
    assert audit["response_payload_members_opened"] == 0
    assert audit["test_response_members_opened"] == 0
    transmitter = audit["transmitter_contract"]
    assert transmitter["center_gda94_zone_53"] == [478230, 7405490]
    assert transmitter["orientation_deg_true"] == 90
    assert transmitter["length_m"] == 1995
    assert transmitter["sampled_waveform_present"] is False
    assert audit["absolute_sounding_upper_bound"] == 205
    assert audit["line_level_cluster_upper_bound"] == 13
    assert audit["observation_contract_ready"] is False
    assert audit["cluster_gate_passes"] is False
    assert audit["power_gate_passes"] is False


def test_ntgs_cr20130857_training_headers_do_not_unseal_test() -> None:
    design = load("ntgs-cr20130857-csamt-design-audit-v1.json")
    training = load("ntgs-cr20130857-csamt-training-header-audit-v1.json")

    assert training["design_sha256"] == sha256(
        EVIDENCE / "ntgs-cr20130857-csamt-design-audit-v1.json"
    )
    assert design["role_assignment_frozen_before_response_access"] is True
    assert design["line_roles"]["test"] == ["7412500N", "7412900N"]
    assert training["training_raw_members_opened"] == 10
    assert training["calibration_raw_members_opened"] == 0
    assert training["test_raw_members_opened"] == 0
    assert training["test_response_values_interpreted"] == 0
    assert training["training_response_values_interpreted"] == 0
    assert training["training_acquisition_header_count"] == 970
    assert training["unique_frequency_hz"] == [
        4.0,
        8.0,
        16.0,
        32.0,
        64.0,
        128.0,
        256.0,
        512.0,
        1024.0,
        2048.0,
        4096.0,
        8192.0,
    ]
    assert training["sampled_transmitter_waveform_present"] is False
    assert training["observation_contract_ready"] is False


def test_usgs_2026_aem_candidates_stop_before_futile_payload_download() -> None:
    audit = load("usgs-aem-2026-unexposed-metadata-audit-v1.json")

    assert audit["audit_mode"] == "response_blind"
    assert audit["response_payloads_downloaded"] == 0
    assert audit["response_values_interpreted"] == 0
    assert audit["test_unseal_count"] == 0
    candidates = {candidate["doi"]: candidate for candidate in audit["candidates"]}
    assert candidates["10.5066/P18JCA5M"]["line_records"] == 146
    assert candidates["10.5066/P14TP9LW"]["line_records"] == 236
    for candidate in candidates.values():
        assert all(candidate["metadata_contract"].values())
        assert candidate["response_payload"]["downloaded"] is False
    geometry = audit["combined_geometry"]
    assert geometry["raw_line_records"] == 382
    assert geometry["frozen_training_only_correlation_range_km"] == 3.51
    assert geometry["effective_cluster_upper_bound"] == 44
    assert geometry["required_test_clusters"] == 223
    assert geometry["passes_cluster_gate"] is False
    assert audit["decision"] == "abort_before_response_payload"


def test_taiwan_eri_metadata_exceeds_dc_cluster_count_without_response_access() -> None:
    audit = load("taiwan-eri-metadata-audit-v1.json")

    assert audit["license"] == "CC-BY-4.0"
    assert audit["declared_profile_count"] == 265
    assert audit["public_folder_count"] == 532
    assert audit["public_file_count"] == 4_838
    assert audit["file_extension_counts"][".stg"] == 728
    assert audit["file_extension_counts"][".urf"] == 941
    assert audit["exact_unique_profile_centres"] == 251
    assert audit["training_correlation_range_m"] == 64
    assert audit["effective_spatial_clusters_at_training_range"] == 246
    assert audit["required_test_clusters"] == 223
    assert audit["cluster_count_gate_possible"] is True
    assert audit["paired_crps_effect_size_available"] is False
    assert audit["power_gate_passed"] is False
    assert audit["response_payloads_downloaded"] == 0
    assert audit["response_values_interpreted"] == 0
    assert audit["test_unseal_count"] == 0


def test_taiwan_eri_training_power_preserves_exact_223_component_test() -> None:
    design = load("taiwan-eri-design-v1.json")
    power = load("taiwan-eri-training-power-v1.json")

    assert design["selection_frozen_before_response_payload_access"] is True
    assert design["exact_unique_profile_centres"] == 251
    assert design["component_count"] == 246
    assert design["role_counts"] == {"training": 23, "test": 223}
    assert design["design_cluster_gate_passes"] is True
    assert design["response_values_interpreted"] == 0
    assert design["test_unseal_count"] == 0
    assert power["training_only"] is True
    assert power["observation_contract"]["training_component_count"] == 23
    assert power["observation_contract"]["training_observation_count"] == 26_356
    assert power["observation_contract"]["abmn_xyz_present"] is True
    assert (
        power["observation_contract"]["per_observation_repeat_error_present"]
        is True
    )
    assert power["paired_training_components"] == 23
    assert power["required_paired_crps_clusters_conservative"] == 99
    assert power["required_clusters_all_metrics"] == 223
    assert power["available_correlation_adjusted_test_clusters"] == 223
    assert power["wp8_0_power_gate_passes"] is True
    assert power["test_files_downloaded"] == 0
    assert power["test_responses_interpreted"] == 0
    assert power["test_unseal_count"] == 0
    assert power["formal_test_result"] is None


def test_heavy_metal_sip_single_site_stops_before_large_zip() -> None:
    audit = load("mendeley-heavy-metal-sip-metadata-audit-v1.json")

    assert audit["audit_mode"] == "response_blind"
    assert audit["license"] == "CC-BY-4.0"
    assert audit["site_count"] == 1
    assert audit["declared_receiver_channels"] == 8
    assert audit["declared_pseudorandom_sequences_per_measurement"] == 27
    assert audit["response_blind_independent_cluster_upper_bound"] == 1
    assert audit["required_test_clusters"] == 223
    assert audit["cluster_gate_passes"] is False
    assert audit["power_gate_passes"] is False
    assert audit["decision"] == "abort_before_response_payload"
    assert audit["response_payloads_downloaded"] == 0
    assert audit["response_values_interpreted"] == 0


def test_qiabuqia_wfem_rejects_request_only_station_design() -> None:
    audit = load("qiabuqia-wfem-metadata-audit-v1.json")

    assert audit["audit_mode"] == "response_blind"
    assert audit["declared_line_count"] == 6
    assert audit["declared_station_count"] == 306
    assert audit["declared_station_spacing_m"] == 100
    assert audit["raw_station_count_exceeds_required_test_clusters"] is True
    assert audit["anonymous_public_download"] is False
    assert audit["correlation_adjusted_cluster_count"] is None
    assert audit["observation_contract_verifiable_from_public_payload"] is False
    assert audit["cluster_gate_passes"] is False
    assert audit["power_gate_passes"] is False
    assert audit["decision"] == "reject_request_only_candidate"
    assert audit["response_payloads_downloaded"] == 0
    assert audit["response_values_interpreted"] == 0


def test_ntgs_pine_creek_ip_archive_contains_processed_products_only() -> None:
    audit = load("ntgs-pine-creek-ip-container-audit-v1.json")

    assert audit["license"] == "CC-BY-4.0"
    assert audit["archive_downloaded_anonymously"] is True
    assert audit["archive_size_bytes"] == 51_784_997
    assert audit["archive_file_count"] == 730
    assert audit["open_file_report_count"] == 24
    assert audit["distinct_chargeability_resistivity_product_ids"] == 104
    assert audit["unadjusted_product_count_below_requirement"] is True
    assert audit["native_observation_files_present"] is False
    assert audit["voltage_present"] is False
    assert audit["current_present"] is False
    assert audit["abmn_geometry_present"] is False
    assert audit["ip_decay_windows_present"] is False
    assert audit["observation_gate_passes"] is False
    assert audit["cluster_gate_passes"] is False
    assert audit["power_gate_passes"] is False
    assert audit["response_archives_downloaded"] == 1
    assert audit["response_values_interpreted"] == 0


def test_ntgs_angularli_csamt_repairs_exact_finite_source_geometry() -> None:
    audit = load("ntgs-angularli-csamt-contract-v1.json")

    assert audit["license"] == "CC-BY-4.0"
    assert audit["archive_size_bytes"] == 16_004_010
    assert audit["transmitter"]["type"] == "bipole"
    assert audit["transmitter"]["length_m"] == 1_770
    assert audit["transmitter"]["azimuth_deg"] == 0
    assert audit["transmitter"]["endpoint_coordinates_derivable"] is True
    assert audit["transmitter"]["endpoint_1_northing_m"] == 8_690_336
    assert audit["transmitter"]["endpoint_2_northing_m"] == 8_692_106
    assert audit["transmitter"]["per_frequency_current_present"] is True
    assert audit["transmitter"]["sampled_waveform_present"] is False
    assert audit["receiver"]["unique_centers"] == 24
    assert audit["receiver"]["components"] == ["Ex", "Hy"]
    assert audit["observations"]["row_count"] == 417
    assert audit["observations"]["frequency_count"] == 21
    assert audit["observations"]["per_observation_percent_errors_present"] is True
    assert audit["formal_finite_source_observation_contract_ready"] is False
    assert audit["cluster_gate_passes"] is False


def test_ntgs_tdip_coordinate_design_freezes_exact_223_test_clusters() -> None:
    design = load("ntgs-pine-creek-tdip-coordinate-design-v1.json")

    assert design["selection_frozen_before_sealed_response_interpretation"] is True
    assert design["training_only_correlation"]["unique_receiver_centres"] == 492
    assert design["training_only_correlation"]["frozen_range_m"] == 250
    assert design["sealed_coordinate_audit"]["response_columns_parsed"] == []
    assert design["sealed_coordinate_audit"]["raw_rows_with_geometry"] == 77_604
    assert design["sealed_coordinate_audit"]["unique_receiver_centres"] == 1_729
    assert (
        design["sealed_coordinate_audit"]["strictly_separated_packed_centres"]
        == 247
    )
    assert design["role_assignment"]["calibration_count"] == 24
    assert design["role_assignment"]["test_count"] == 223
    assert len(design["role_assignment"]["test"]) == 223
    assert design["cluster_count_gate_possible"] is True
    assert design["paired_crps_effect_size_available"] is False
    assert design["sealed_response_values_interpreted"] == 0
    assert design["test_unseal_count"] == 0


def test_ntgs_tdip_training_power_clears_prospective_gate() -> None:
    power = load("ntgs-pine-creek-tdip-training-power-v1.json")

    assert power["training_only"] is True
    assert power["observation_contract"]["unique_receiver_centres"] == 492
    assert (
        power["observation_contract"]["correlation_separated_paired_centres"]
        == 17
    )
    assert power["observation_contract"]["decay_window_count"] == 20
    assert power["paired_training_clusters"] == 17
    assert power["required_paired_crps_clusters_conservative"] == 106
    assert power["required_clusters_all_metrics"] == 223
    assert power["available_correlation_adjusted_test_clusters"] == 223
    assert power["wp8_0_power_gate_passes"] is True
    assert power["sealed_response_values_interpreted"] == 0
    assert power["test_unseal_count"] == 0
    assert power["formal_test_result"] is None


def test_usgs_floatem_training_design_clears_tem_cluster_and_power_gates() -> None:
    audit = load("usgs-floatem-training-design-power-v1.json")

    assert audit["license"] == "US-public-domain"
    assert audit["training_only_correlation"]["stable_upper_edge_m"] == 260
    assert audit["training_only_correlation"]["safety_factor"] == 1.25
    assert audit["training_only_correlation"]["frozen_range_m"] == 325.0
    assert audit["training_only_power"]["paired_training_clusters"] == 130
    assert (
        audit["training_only_power"][
            "required_paired_crps_clusters_conservative"
        ]
        == 321
    )
    assert audit["sealed_coordinate_inventory"]["unique_positions"] == 30_669
    assert (
        audit["sealed_coordinate_inventory"]["response_columns_interpreted"]
        == 0
    )
    assert audit["sealed_packing"]["packed_position_count"] == 465
    assert audit["role_assignment"]["calibration_count"] == 24
    assert audit["role_assignment"]["test_count"] == 321
    assert audit["role_assignment"]["buffer_count"] == 120
    assert audit["wp8_0_cluster_gate_passes"] is True
    assert audit["wp8_0_power_gate_passes"] is True
    assert audit["sealed_response_values_interpreted"] == 0
    assert audit["test_unseal_count"] == 0
    assert audit["formal_test_result"] is None


def test_public_csamt_search_additions_are_training_only_and_fail_closed() -> None:
    audit = load("zenodo-csamt-public-search-audit-v1.json")
    records = {str(row["record_id"]): row for row in audit["records"]}

    pycsamt = records["5674430"]
    assert pycsamt["controlled_source_station_count"] == 47
    assert pycsamt["controlled_source_observation_count"] == 799
    assert pycsamt["natural_source_excluded_from_csamt_count"] is True
    assert pycsamt["transmitter_endpoint_coordinates_present"] is False
    assert pycsamt["sampled_transmitter_waveform_present"] is False
    assert pycsamt["cluster_gate_passes"] is False

    pilgrim = records["DGGS-RDF-2020-9"]
    assert pilgrim["raw_component_file_count"] == 99
    assert pilgrim["field_log_location_count"] == 20
    assert pilgrim["receiver_electrode_endpoints_present"] is True
    assert pilgrim["transmitter_endpoint_coordinates_present"] is False
    assert pilgrim["sampled_transmitter_waveform_present"] is False
    assert pilgrim["observation_contract_ready"] is False
    assert pilgrim["cluster_gate_passes"] is False
    assert audit["formal_test_responses_opened"] == 0
    assert audit["test_unseal_count"] == 0


def test_restored_usgs_sevier_csamt_raw_package_remains_fail_closed() -> None:
    audit = load("usgs-sevier-fault-csamt-raw-audit-v2.json")

    assert audit["source"]["provider_parent_zip_restored"] is True
    assert audit["source"]["archive_bytes"] == 328_632
    assert audit["partition"] == "permanently-training-only"
    assert audit["lines"]["Sv1"]["stations"]["station_count"] == 101
    assert audit["lines"]["Sv2"]["stations"]["station_count"] == 40
    assert audit["lines"]["Sv1"]["raw"]["unique_frequency_count"] == 11
    assert audit["lines"]["Sv2"]["raw"]["unique_frequency_count"] == 12
    assert audit["gate_assessment"]["electric_and_magnetic_components_present"] is True
    assert audit["gate_assessment"]["transmitter_endpoint_coordinates_present"] is False
    assert audit["gate_assessment"]["sampled_transmitter_waveform_present"] is False
    assert audit["gate_assessment"]["independent_profile_upper_bound"] == 2
    assert audit["gate_assessment"]["minimum_independent_test_clusters"] == 223
    assert audit["gate_assessment"]["observation_contract_passes"] is False
    assert audit["gate_assessment"]["cluster_gate_passes"] is False
    assert audit["gate_assessment"]["power_gate_passes"] is False
    assert audit["formal_test_responses_opened"] == 0
    assert audit["test_unseal_count"] == 0
    assert audit["formal_test_result"] is None


def test_ntgs_cr20100883_csamt_inventory_and_design_fail_closed() -> None:
    inventory = load("ntgs-cr20100883-response-blind-inventory-v1.json")
    design = load("ntgs-cr20100883-csamt-design-audit-v1.json")

    assert inventory["archive_bytes"] == 2_579_440_118
    assert inventory["archive_member_count"] == 8_818
    assert inventory["method_name_member_counts"]["csamt"] == 242
    assert inventory["method_name_member_counts"]["pdip"] == 270
    assert inventory["response_payload_members_opened"] == 0
    assert inventory["test_response_members_opened"] == 0
    assert inventory["central_directory_only"] is True

    assert design["survey_line_count"] == 5
    assert design["published_sounding_count"] == 111
    assert design["transmitter_geometry_unambiguous_line_count"] == 4
    assert design["lines"]["Trinity-L35"][
        "transmitter_geometry_unambiguous"
    ] is False
    assert design["sampled_transmitter_waveform_present"] is False
    assert design["independent_cluster_upper_bound"] == 111
    assert design["minimum_independent_test_clusters"] == 223
    assert design["observation_contract_ready"] is False
    assert design["cluster_gate_passes"] is False
    assert design["power_gate_passes"] is False
    assert design["response_payload_members_opened"] == 0
    assert design["test_response_members_opened"] == 0


def test_sip_debye_net_field_spectra_do_not_overstate_spatial_support() -> None:
    audit = load("sip-fdip-public-data-audit.json")
    candidates = {row["id"]: row for row in audit["candidates"]}
    candidate = candidates["github-sip-debye-net-2026"]

    assert candidate["complex_spectra"] == 140
    assert candidate["experimental_series"] == 11
    assert candidate["frequencies_per_spectrum"] == 19
    assert candidate["complex_uncertainty_per_observation"] is True
    assert candidate["canadian_malartic_field_spectra"] == 26
    assert candidate["field_coordinate_or_abmn_geometry"] is False
    assert candidate["independent_spatial_cluster_count_derivable"] is False
    assert (
        audit["conclusions"]["contract_complete_field_replacement_found"]
        is False
    )
    assert audit["conclusions"]["method_substitution_allowed"] is False


def test_vineyard_field_sip_repairs_observation_only() -> None:
    audit = load("zenodo-vineyard-field-sip-audit-v1.json")

    assert audit["archive"]["bytes"] == 326_775_934
    assert audit["archive"]["md5"] == "ef21c75b57afd66727291d12adf0c7f3"
    assert len(audit["raw_data"]["das1_files"]) == 6
    assert all(row["has_abmn_geometry"] for row in audit["raw_data"]["das1_files"])
    assert all(row["has_complex_response"] for row in audit["raw_data"]["das1_files"])
    assert all(row["has_repeat_uncertainty"] for row in audit["raw_data"]["das1_files"])
    assert audit["raw_data"]["independent_spatial_cluster_upper_bound"] == 2
    assert audit["gate_assessment"]["observation_pass"] is True
    assert audit["gate_assessment"]["clusters_pass"] is False
    assert audit["gate_assessment"]["power_pass"] is False


def test_geodata_cn_locked_method_metadata_is_response_blind() -> None:
    audit = load("geodata-cn-locked-methods-metadata-audit-v1.json")
    records = {row["id"]: row for row in audit["records"]}
    wfem = records["sichuan-central-wfem-2017"]

    assert audit["formal_test_responses_opened"] == 0
    assert audit["test_unseal_count"] == 0
    assert wfem["doi"] == "10.12041/geodata.37412589003507.ver1.db"
    assert wfem["access_group_id"] == 7
    assert wfem["anonymous_entity_download"] is False
    assert wfem["documented_fields"] == {
        "station": True,
        "frequency": True,
        "source_current": True,
        "electric_field": True,
        "relative_error": True,
        "apparent_resistivity": True,
        "receiver_coordinates": True,
    }
    assert wfem["sampled_transmitter_waveform_public"] is False
    assert wfem["source_endpoint_coordinates_public"] is False
    assert wfem["formal_observation_contract_ready"] is False
    assert wfem["cluster_gate_passes"] is False
    assert wfem["power_gate_passes"] is False
    assert all(row["response_entity_opened"] is False for row in records.values())
    active_source_ids = {
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
    active_source = [records[key] for key in active_source_ids]
    assert len(records) == 13
    assert all(row["access_group_id"] == 7 for row in active_source)
    assert all(row["catalogue_is_online"] is False for row in active_source)
    assert all(
        row["anonymous_entity_download"] is False for row in active_source
    )
    assert all(
        row["sampled_transmitter_waveform_public"] is False
        for row in active_source
    )
    assert all(
        row["formal_cluster_contribution"] == 0 for row in active_source
    )
    assert sorted(
        row["public_document_design_audit"]["nominal_station_upper_bound"]
        for row in active_source
        if row["public_document_design_audit"]["nominal_station_upper_bound"]
        is not None
    ) == [21, 80, 160, 300, 300]
    assert (
        audit["conclusion"]["offline_active_source_candidates_found"] == 9
    )
    assert (
        audit["conclusion"]["nominal_csamt_station_upper_bound_at_least_223"]
        == 2
    )
    assert (
        audit["conclusion"]["new_locked_sip_fdip_population_found"] is False
    )
    assert audit["conclusion"]["formal_gate_change"] is False


def test_streambed_sip_release_is_strong_but_only_two_sites() -> None:
    audit = load("zenodo-streambed-sip-audit-v1.json")

    assert audit["doi"] == "10.5281/zenodo.3627361"
    assert audit["license"] == "cc-by-4.0"
    assert audit["formal_test_responses_opened"] == 0
    assert audit["test_unseal_count"] == 0
    assert len(audit["sites"]) == 2
    assert all(row["coordinate_count"] == 160 for row in audit["sites"])
    assert all(row["profile_count"] == 5 for row in audit["sites"])
    assert all(row["sip_recording_files"] == 50 for row in audit["sites"])
    assert all(row["response_rows"] == 20_400 for row in audit["sites"])
    assert all(
        row["unique_abmn_quadrupoles"] == 408 for row in audit["sites"]
    )
    assert all(
        row["uncertainty_columns_present"] is True for row in audit["sites"]
    )
    assert audit["totals"]["response_rows"] == 40_800
    assert audit["totals"]["unique_site_profile_clusters_upper_bound"] == 10
    assert audit["totals"]["independent_spatial_cluster_upper_bound"] == 2
    assert audit["gate_assessment"]["cluster_gate_passes"] is False
    assert audit["gate_assessment"]["power_gate_passes"] is False


def test_bc_aris_ip_catalogue_is_response_blind_and_split_before_audit() -> None:
    catalogue_path = EVIDENCE / "bc-aris-ip-digital-catalogue-v1.json"
    catalogue = load(catalogue_path.name)
    split = load("bc-aris-ip-discovery-split-v1.json")

    assert catalogue["schema_version"] == "wp8-bc-aris-ip-digital-catalogue-v1"
    assert catalogue["query"]["response_payloads_opened"] is False
    assert catalogue["query"]["archive_members_listed"] is False
    assert catalogue["query"]["pdf_response_tables_opened"] is False
    assert catalogue["catalogue_counts"] == {
        "reported_records": 103,
        "parsed_unique_records": 103,
        "records_with_archive_endpoint": 102,
        "head_verified_archive_endpoints": 104,
        "head_verified_total_bytes": 45_139_610_874,
    }
    assert catalogue["gate_assessment"]["formal_clusters_added"] == 0
    assert catalogue["gate_assessment"]["formal_gate_changed"] is False

    assert split["schema_version"] == "wp8-bc-aris-ip-discovery-split-v1"
    assert split["catalogue_sha256"] == sha256(catalogue_path)
    assert split["role_counts"] == {
        "training-discovery": 30,
        "sealed-candidate-test": 73,
    }
    assert (
        split["formal_status"]["sealed_candidate_test_responses_opened"] == 0
    )
    sealed = [
        row
        for row in split["assignments"]
        if row["role"] == "sealed-candidate-test"
    ]
    assert len(sealed) == 73
    assert all(row["response_opened"] is False for row in sealed)
    assert all(row["archive_members_listed"] is False for row in sealed)


def test_bc_aris_training_audit_finds_tdip_but_keeps_test_set_sealed() -> None:
    audit = load("bc-aris-ip-training-classification-v1.json")

    assert (
        audit["schema_version"]
        == "wp8-bc-aris-ip-training-classification-v1"
    )
    assert audit["audit_scope"] == {
        "training_discovery_reports_total": 30,
        "training_reports_classified": 30,
        "training_archives_opened": 21,
        "training_reports_classified_from_official_pdf_only": 9,
        "official_pdf_files_opened_for_remaining_reports": 12,
        "sealed_candidate_test_reports_total": 73,
        "sealed_candidate_test_responses_opened": 0,
        "classification_is_training_only": True,
    }
    classes = audit["classification"]
    assert len(classes["explicit_time_domain_ip_reports"]) == 20
    assert len(classes["derived_scalar_or_no_qualifying_raw_sip_reports"]) == 8
    assert len(classes["placeholder_only_reports"]) == 2
    assert classes["qualifying_sip_fdip_reports"] == []
    assert len(audit["opened_archive_fingerprints"]) == 21
    assert len(audit["opened_official_pdf_fingerprints"]) == 12
    assert audit["formal_status"]["formal_sip_fdip_clusters_added"] == 0
    assert audit["formal_status"]["formal_gate_changed"] is False


def test_san_antonio_amt_has_raw_receivers_but_incomplete_source_contract() -> None:
    audit = load("usgs-san-antonio-controlled-source-amt-audit-v1.json")

    assert audit["archive"]["bytes"] == 105_815_157
    assert audit["archive"]["members"] == 87
    assert audit["survey"]["sites"] == 29
    assert audit["survey"]["controlled_source_use_per_site_known"] is False
    assert audit["byte_audit"]["impedance_frequency_rows"] == 1_682
    assert audit["byte_audit"]["complex_impedance_tensor_present"] is True
    assert audit["byte_audit"]["raw_receiver_time_series_present"] is True
    assert all(
        value is False for value in audit["missing_source_contract"].values()
    )
    assert audit["gate_assessment"]["independent_cluster_upper_bound"] == 29
    assert audit["gate_assessment"]["observation_contract_pass"] is False
    assert audit["gate_assessment"]["formal_gate_changed"] is False


def test_full_waveform_csamt_candidate_is_request_only_and_too_small() -> None:
    audit = load(
        "csamt-full-waveform-current-recorder-access-audit-v1.json"
    )

    assert audit["source"]["doi"] == "10.5194/gi-8-139-2019"
    field = audit["field_experiment"]
    assert field["receiver_count"] == 15
    assert field["csamt_frequency_count"] == 41
    assert field["continuous_current_waveform_recorded"] is True
    assert field["gps_time_stamped"] is True
    access = audit["access_audit"]
    assert access["anonymous_raw_data_download"] is False
    assert access["raw_current_samples_public"] is False
    assert access["raw_receiver_samples_public"] is False
    assert audit["gate_assessment"]["source_contract_byte_auditable"] is False
    assert audit["gate_assessment"]["independent_cluster_upper_bound"] == 15
    assert audit["gate_assessment"]["formal_gate_changed"] is False


def test_sip_debye_net_has_uncertainty_but_only_26_field_stations() -> None:
    audit = load("github-sip-debye-net-field-audit-v1.json")

    assert audit["download_audit"]["bytes"] == 68_593
    assert (
        audit["download_audit"]["sha256"]
        == "7ec8c6cc663ea09b14427947fdacf63edf94df0e308d7e200e50cd118eba82b3"
    )
    contract = audit["published_dataset_contract"]
    assert contract["total_spectra"] == 140
    assert contract["frequency_count_per_spectrum"] == 19
    assert contract["real_and_imaginary_standard_deviations_present"] is True
    assert audit["population_breakdown_from_article_table_1"]["field_total"] == 26
    assert audit["population_breakdown_from_article_table_1"][
        "laboratory_or_core_total"
    ] == 114
    assert audit["field_subset"]["profile_count"] == 1
    assert audit["field_subset"]["station_coordinates_in_repository"] is False
    assert (
        audit["gate_assessment"]["independent_field_cluster_upper_bound"] == 26
    )
    assert audit["gate_assessment"]["cluster_gate_passes"] is False
    assert audit["gate_assessment"]["power_gate_passes"] is False
    assert audit["gate_assessment"]["formal_gate_changed"] is False


def test_ess_dive_tempest_has_field_ip_but_sip_only_in_lab() -> None:
    audit = load("ess-dive-tempest-ip-sip-metadata-audit-v1.json")

    assert audit["source"]["license"] == "CC0-1.0"
    assert audit["source"]["anonymous_public_access"] is True
    assert [row["bytes"] for row in audit["public_objects"]] == [
        18_394_493,
        738_508_613,
    ]
    assert all(row["downloaded"] is False for row in audit["public_objects"])
    field = audit["field_contract_from_eml"]
    assert field["eri_ip_transect_lengths_m"] == [100, 42]
    assert field["field_ip_frequency_count"] == 1
    assert field["field_ip_frequency_hz"] == 10.0
    assert field["field_spectral_ip"] is False
    lab = audit["laboratory_sip_contract_from_eml"]
    assert lab["undisturbed_core_count"] == 6
    assert lab["brine_solution_count"] == 7
    assert lab["frequency_count"] == 50
    assert lab["field_measurements"] is False
    gate = audit["gate_assessment"]
    assert gate["independent_qualifying_field_cluster_upper_bound"] == 0
    assert gate["cluster_gate_passes"] is False
    assert gate["power_gate_passes"] is False
    assert gate["formal_gate_changed"] is False


def test_kanstein_slag_heap_is_qualifying_sip_but_not_public_data() -> None:
    audit = load("kanstein-slag-heap-sip-access-audit-v1.json")

    design = audit["field_design"]
    assert design["profile_count"] == 2
    assert design["electrode_count"] == 40
    assert design["frequency_count"] == 14
    assert design["qualifying_field_sip"] is True
    access = audit["public_access_audit"]
    assert access["bert_repository_full_git_history_searched"] is True
    assert access["bert_history_contains_sip_or_fdip_code"] is True
    assert access["bert_history_contains_kanstein_raw_sip_response"] is False
    assert access["bert_history_contains_example_res"] is False
    assert access["anonymous_raw_field_response_download_found"] is False
    gate = audit["gate_assessment"]
    assert gate["independent_field_cluster_upper_bound_if_obtained"] == 2
    assert gate["observation_contract_byte_auditable"] is False
    assert gate["cluster_gate_passes"] is False
    assert gate["power_gate_passes"] is False
    assert gate["formal_gate_changed"] is False
