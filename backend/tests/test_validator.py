"""Unit tests for the Validator Node (Pharma QMS rules, chronology, entity integrity)."""
import pytest
from datetime import date
from app.agents.nodes.validator import validator_node, REQUIRED_QMS_FIELDS


def test_validator_detects_missing_required_fields():
    """Validator must flag missing core QMS fields."""
    state = {
        "extracted_data": {
            "customer_name": "Apollo Pharmacy",
            # product_name missing
            # batch_lot_number missing
            "complaint_category": "Packaging Defect",
            "affected_quantity": "50 vials",
        }
    }
    result = validator_node(state)
    missing = result.get("missing_fields", [])
    assert "Product Name" in missing
    assert "Batch / Lot Number" in missing
    assert "Customer / Reporting Entity" not in missing


def test_validator_date_chronology_violation():
    """Validator must flag when manufacturing date is after or equal to expiry date."""
    state = {
        "extracted_data": {
            "customer_name": "City Hospital",
            "product_name": "Amoxicillin 500mg",
            "batch_lot_number": "BAT-2024-01",
            "complaint_category": "Discoloration",
            "affected_quantity": "100 capsules",
            "manufacturing_date": "2025-06-01",
            "expiry_date": "2024-06-01",  # chronological violation
        }
    }
    result = validator_node(state)
    errors = result.get("validation_errors", [])
    assert any("must precede Expiry date" in err for err in errors)
    assert result.get("is_valid") is False


def test_validator_all_valid():
    """Validator passes completely when all required fields and valid dates are supplied."""
    state = {
        "extracted_data": {
            "customer_name": "Memorial Health System",
            "product_name": "Ceftriaxone 1g Injection",
            "batch_lot_number": "CFX-2024-88A",
            "complaint_category": "Sterility",
            "affected_quantity": "24 vials",
            "manufacturing_date": "2024-01-15",
            "expiry_date": "2026-01-14",
            "complaint_date": "2024-08-10",
        }
    }
    result = validator_node(state)
    assert result.get("is_valid") is True
    assert len(result.get("missing_fields", [])) == 0
    assert len(result.get("validation_errors", [])) == 0
    assert "Data integrity checks passed" in result.get("status_message", "")


def test_validator_expired_product_notice():
    """Validator records notice when complaint is reported past expiry date."""
    state = {
        "extracted_data": {
            "customer_name": "Memorial Health System",
            "product_name": "Ceftriaxone 1g Injection",
            "batch_lot_number": "CFX-2024-88A",
            "complaint_category": "Efficacy",
            "affected_quantity": "10 vials",
            "manufacturing_date": "2022-01-01",
            "expiry_date": "2023-01-01",
            "complaint_date": "2024-05-01",  # past expiry
        }
    }
    result = validator_node(state)
    errors = result.get("validation_errors", [])
    assert any("past its labelled expiry date" in err for err in errors)
