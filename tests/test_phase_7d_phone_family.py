"""Phase 7D: phone origin must not be guessed from a keypad alone."""
from routes.equipment_subtype import infer_equipment_subtype

def test_phone_family_needs_independent_cues():
    base={"board_type":"Dense Logic / Controller Board","keypad_intelligence":{"supported":True}}
    assert "Mobile Phone" not in infer_equipment_subtype(base)["subtype"]
    base["phone_family_evidence"]={"handset_mainboard_outline":True,"handset_contact_layout":True}
    assert "Mobile Phone" not in infer_equipment_subtype(base)["subtype"]
    base["phone_family_evidence"]["rf_antenna_section"]=True
    found=infer_equipment_subtype(base)
    assert found["subtype"]=="Likely Mobile Phone Main PCB; Model Unconfirmed"
    assert found["confidence"]=="moderate"
    assert "grade" not in found and "price" not in found
    base["phone_family_evidence"]["conflicting_equipment_origin"]=True
    assert "Mobile Phone" not in infer_equipment_subtype(base)["subtype"]

def test_keypad_without_phone_geometry_stays_unconfirmed():
    case={"board_type":"Keypad / Handheld Controller Board",
          "keypad_intelligence":{"supported":True},
          "phone_family_evidence":{"handset_mainboard_outline":False,
                                   "handset_contact_layout":True,
                                   "rf_antenna_section":True}}
    assert "Mobile Phone" not in infer_equipment_subtype(case)["subtype"]

def test_nec_controller_negative_control_never_becomes_phone():
    case={"board_type":"Dense Logic / Controller Board",
          "board_type_reason":"NEC controller PCB K480 68S32X16A8PH01A REV:01",
          "phone_family_evidence":{"handset_mainboard_outline":False,
                                   "handset_contact_layout":True,
                                   "rf_antenna_section":True,
                                   "phone_connector_arrangement":True}}
    result=infer_equipment_subtype(case)
    assert "Mobile Phone" not in result["subtype"]
    assert "Unconfirmed" in result["subtype"] or "Unresolved" in result["subtype"]

def test_untrusted_string_flags_do_not_count_as_verified_geometry():
    case={"board_type":"Dense Logic / Controller Board",
          "phone_family_evidence":{"handset_mainboard_outline":"false",
                                   "handset_contact_layout":True,
                                   "rf_antenna_section":True}}
    assert "Mobile Phone" not in infer_equipment_subtype(case)["subtype"]

def test_conflict_blocks_phone_even_with_three_corroborators():
    case={"board_type":"Dense Logic / Controller Board",
          "phone_family_evidence":{"handset_mainboard_outline":True,
                                   "handset_contact_layout":True,
                                   "rf_antenna_section":True,
                                   "phone_connector_arrangement":True,
                                   "conflicting_equipment_origin":True}}
    assert "Mobile Phone" not in infer_equipment_subtype(case)["subtype"]

def test_case_merges_explicit_phone_evidence_only_after_same_board_check():
    from routes.case_reasoner import _collect_phone_family_evidence
    views=[
       {"phone_family_evidence":{"handset_mainboard_outline":True,
                                   "handset_contact_layout":True}},
       {"phone_family_evidence":{"rf_antenna_section":True}},
    ]
    assert _collect_phone_family_evidence(views, False)=={}
    combined=_collect_phone_family_evidence(views, True)
    assert combined["handset_mainboard_outline"] is True
    assert combined["rf_antenna_section"] is True
    assert infer_equipment_subtype({"board_type":"General PCB","phone_family_evidence":combined})["subtype"]=="Likely Mobile Phone Main PCB; Model Unconfirmed"

def test_keypad_alone_does_not_create_phone_case_evidence():
    from routes.case_reasoner import _collect_phone_family_evidence
    views=[{"keypad_intelligence":{"supported":True},"board_type":"Keypad / Handheld Controller Board"}]
    assert _collect_phone_family_evidence(views, True)=={}

def test_explicit_conflicting_origin_overrides_phone_evidence_across_views():
    from routes.case_reasoner import _collect_phone_family_evidence
    views=[{"phone_family_evidence":{"handset_mainboard_outline":True,
                                      "handset_contact_layout":True}},
           {"phone_family_evidence":{"rf_antenna_section":True,
                                      "conflicting_equipment_origin":True}}]
    combined=_collect_phone_family_evidence(views, True)
    assert "Mobile Phone" not in infer_equipment_subtype({"board_type":"General PCB","phone_family_evidence":combined})["subtype"]

def test_visual_candidate_requires_good_outline_and_keypad():
    from routes.phone_visual_evidence import observe_handset_candidate
    fp={"board_aspect":3.1,"coverage":"whole_or_large_view","geometry_quality":"good"}
    keypad={"supported":True,"contact_count":12}
    observed=observe_handset_candidate(fp,keypad)
    assert observed["handset_mainboard_outline"] is True
    assert observed["handset_contact_layout"] is True
    assert observed["rf_antenna_section"] is False
    assert "Mobile Phone" not in infer_equipment_subtype({
        "board_type":"General PCB", "phone_family_evidence":observed})["subtype"]

def test_no_phone_candidate_for_rectangular_controller():
    from routes.phone_visual_evidence import observe_handset_candidate
    fp={"board_aspect":1.45,"coverage":"whole_or_large_view","geometry_quality":"good"}
    observed=observe_handset_candidate(fp,{"supported":True,"contact_count":12})
    assert observed["handset_mainboard_outline"] is False
    assert observed["handset_contact_layout"] is False

def test_partial_board_does_not_claim_handset_outline():
    from routes.phone_visual_evidence import observe_handset_candidate
    fp={"board_aspect":3.2,"coverage":"detail_or_partial_view","geometry_quality":"low"}
    assert observe_handset_candidate(fp,{"supported":True,"contact_count":12})["handset_mainboard_outline"] is False

def test_line_of_gold_vias_is_not_phone_keypad():
    from routes.phone_visual_evidence import observe_handset_candidate
    fp={"board_aspect":3.0,"coverage":"whole_or_large_view","geometry_quality":"good"}
    contacts=[{"x":20+i*18,"y":50,"radius":5} for i in range(12)]
    result=observe_handset_candidate(fp,{"supported":True,"contact_count":12,"contacts":contacts})
    assert result["handset_mainboard_outline"] is True
    assert result["handset_contact_layout"] is False
    assert result["rf_antenna_section"] is False

def test_two_dimensional_contact_grid_remains_candidate_not_confirmed_phone():
    from routes.phone_visual_evidence import observe_handset_candidate
    fp={"board_aspect":3.0,"coverage":"whole_or_large_view","geometry_quality":"good"}
    contacts=[{"x":40+col*35,"y":50+row*38,"radius":6} for row in range(4) for col in range(3)]
    result=observe_handset_candidate(fp,{"supported":True,"contact_count":12,"contacts":contacts})
    assert result["handset_contact_layout"] is True
    assert result["keypad_spatial_evidence"] == "two_axis_contact_spread"
    assert result["rf_antenna_section"] is False
    assert "Mobile Phone" not in infer_equipment_subtype({"board_type":"General PCB","phone_family_evidence":result})["subtype"]
