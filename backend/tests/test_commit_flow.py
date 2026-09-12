"""Integration tests for the Commit to QMS Ledger flow and 21 CFR 211.198 immutability enforcement."""
import pytest
import httpx


@pytest.mark.asyncio
async def test_commit_rejects_missing_required_fields(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Pre-commit validation must return 422 with a structured list of missing QMS fields."""
    # 1. Create a fresh draft complaint
    create_res = await async_client.post("/complaints/", json={})
    assert create_res.status_code == 201
    cid = cleanup_test_complaint(create_res.json()["id"])

    # 2. Attempt commit immediately without filling required fields
    commit_res = await async_client.patch(f"/complaints/{cid}/commit")
    assert commit_res.status_code == 422
    data = commit_res.json()
    assert "missing_fields" in data["detail"]
    missing = data["detail"]["missing_fields"]
    assert "customer_name" in missing
    assert "product_name" in missing
    assert "batch_lot_number" in missing
    assert "complaint_description" in missing


@pytest.mark.asyncio
async def test_successful_commit_flow_and_audit_trail(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Successful commit updates status to committed, populates committed_at & severity_final, writes audit log."""
    # 1. Create complaint
    create_res = await async_client.post("/complaints/", json={})
    assert create_res.status_code == 201
    cid = cleanup_test_complaint(create_res.json()["id"])

    # 2. Populate all required QMS fields
    update_payload = {
        "customer_name": "Apollo Hospitals Central",
        "product_name": "Metformin Hydrochloride 500mg",
        "batch_lot_number": "MET-2024-Q10",
        "manufacturing_date": "2024-02-15",
        "expiry_date": "2026-02-14",
        "affected_quantity": "120 blister packs",
        "complaint_category": "Packaging Defect",
        "complaint_description": "Blister seal integrity compromised leading to visible discoloration of tablets.",
        "severity_suggested": "Major",
        "priority": "High",
        "suggested_next_action": "Quarantine retained samples and inspect sealing line 2.",
    }
    patch_res = await async_client.patch(f"/complaints/{cid}", json=update_payload)
    assert patch_res.status_code == 200

    # 3. Execute Commit to QMS Ledger
    commit_res = await async_client.patch(f"/complaints/{cid}/commit")
    assert commit_res.status_code == 200
    committed = commit_res.json()["complaint"]

    assert committed["status"] == "committed"
    assert committed["committed_at"] is not None
    assert committed["severity_final"] == "Major"

    # 4. Verify immutable audit trail record
    audit_res = await async_client.get(f"/complaints/{cid}/audit-log")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    status_log = next((log for log in logs if log["field_name"] == "status"), None)
    assert status_log is not None
    assert status_log["new_value"] == "committed"
    assert status_log["actor"] == "user"


@pytest.mark.asyncio
async def test_post_commit_immutability_enforcement(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Committed complaints must reject all further PATCH and POST /copilot/chat operations with 403 Forbidden."""
    # 1. Create and populate complaint
    create_res = await async_client.post("/complaints/", json={})
    cid = cleanup_test_complaint(create_res.json()["id"])

    await async_client.patch(f"/complaints/{cid}", json={
        "customer_name": "St. Jude Clinic",
        "product_name": "Paracetamol Infusion 10mg/mL",
        "batch_lot_number": "PAR-2024-X",
        "manufacturing_date": "2024-01-10",
        "affected_quantity": "30 bottles",
        "complaint_category": "Particulate Matter",
        "complaint_description": "Foreign particulate matter observed suspended in infusion solution.",
        "severity_suggested": "Critical",
        "priority": "High",
    })

    # 2. Commit complaint
    commit_res = await async_client.patch(f"/complaints/{cid}/commit")
    assert commit_res.status_code == 200

    # 3. Attempt subsequent PATCH /complaints/{id} -> MUST return 403 Forbidden
    edit_res = await async_client.patch(f"/complaints/{cid}", json={"product_name": "Tampered Product"})
    assert edit_res.status_code == 403
    assert "Committed complaints cannot be modified" in edit_res.json()["detail"]

    # 4. Attempt subsequent POST /copilot/chat -> MUST return 403 Forbidden
    chat_res = await async_client.post("/copilot/chat", json={
        "complaint_id": cid,
        "message": "Actually change the product name to New Name",
    })
    assert chat_res.status_code == 403
    assert "21 CFR 211.198" in chat_res.json()["detail"]
