"""Integration tests for ComplaintIQ core and Phase 6 bonus API endpoints."""
import pytest
import httpx


@pytest.mark.asyncio
async def test_health_check(async_client: httpx.AsyncClient):
    """Health check endpoint must return status ok."""
    res = await async_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "ComplaintIQ" in data["service"]


@pytest.mark.asyncio
async def test_crud_complaint_lifecycle(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Verifies creation, retrieval, and updating of complaint draft."""
    # 1. Create complaint draft
    res = await async_client.post("/complaints/", json={})
    assert res.status_code == 201
    cid = cleanup_test_complaint(res.json()["id"])
    assert cid.startswith("CC-")

    # 2. Retrieve complaint
    get_res = await async_client.get(f"/complaints/{cid}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == cid
    assert get_res.json()["status"] == "pending_triage"

    # 3. Patch complaint
    patch_res = await async_client.patch(f"/complaints/{cid}", json={
        "customer_name": "Sunrise Healthcare",
        "product_name": "Ibuprofen 400mg Tablets",
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["customer_name"] == "Sunrise Healthcare"
    assert patch_res.json()["product_name"] == "Ibuprofen 400mg Tablets"


@pytest.mark.asyncio
async def test_completeness_endpoint(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Completeness endpoint evaluates 8 QMS checks and returns score."""
    res = await async_client.post("/complaints/", json={})
    cid = cleanup_test_complaint(res.json()["id"])

    comp_res = await async_client.get(f"/complaints/{cid}/completeness")
    assert comp_res.status_code == 200
    data = comp_res.json()

    assert data["complaint_id"] == cid
    assert data["total_checks"] == 8
    assert data["can_commit"] is False
    assert len(data["items"]) == 8


@pytest.mark.asyncio
async def test_duplicates_endpoint(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Duplicates endpoint executes vector similarity check without error."""
    res = await async_client.post("/complaints/", json={})
    cid = cleanup_test_complaint(res.json()["id"])

    dup_res = await async_client.get(f"/complaints/{cid}/duplicates")
    assert dup_res.status_code == 200
    data = dup_res.json()
    assert data["complaint_id"] == cid
    assert "duplicates" in data
    assert isinstance(data["duplicates"], list)


@pytest.mark.asyncio
async def test_chat_messages_endpoint(async_client: httpx.AsyncClient, cleanup_test_complaint):
    """Chat messages endpoint returns message history for complaint."""
    res = await async_client.post("/complaints/", json={})
    cid = cleanup_test_complaint(res.json()["id"])

    chat_res = await async_client.get(f"/complaints/{cid}/chat-messages")
    assert chat_res.status_code == 200
    assert isinstance(chat_res.json(), list)
