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
