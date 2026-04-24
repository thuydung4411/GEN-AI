import uuid
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from api.app.main import app
from api.app.dependencies.auth import get_current_user
from api.app.repositories.interfaces import AuthenticatedUser


@pytest.fixture
def mock_user():
    user_id = uuid.uuid4()
    return AuthenticatedUser(
        user_id=user_id,
        email="test@example.com",
        access_token="mock-token"
    )

@pytest.fixture
def client(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_unified_asset_upload_routing(client):
    """
    Verify that /v1/assets/upload correctly routes CSV to dataset lane 
    and PDF to knowledge lane.
    """
    # 1. Upload CSV
    csv_content = b"header1,header2\nval1,val2"
    response_csv = client.post(
        "/v1/assets/upload",
        files={"file": ("test.csv", csv_content, "text/csv")}
    )
    assert response_csv.status_code == 201
    data_csv = response_csv.json()
    assert data_csv["kind"] == "dataset"
    assert "asset_id" in data_csv
    assert "job_id" in data_csv

    # 2. Upload PDF
    pdf_content = b"%PDF-1.4\ntest content"
    response_pdf = client.post(
        "/v1/assets/upload",
        files={"file": ("test.pdf", pdf_content, "application/pdf")}
    )
    assert response_pdf.status_code == 201
    data_pdf = response_pdf.json()
    assert data_pdf["kind"] == "knowledge"
    assert "asset_id" in data_pdf
    assert "job_id" in data_pdf

def test_unified_asset_list(client):
    """
    Verify that /v1/assets returns a merged list.
    """
    response = client.get("/v1/assets")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_asset_detail_and_delete(client):
    """
    Verify GET detail and DELETE lifecycle.
    """
    # 1. Upload
    csv_content = b"h1,h2\nv1,v2"
    resp = client.post("/v1/assets/upload", files={"file": ("del.csv", csv_content, "text/csv")})
    asset_id = resp.json()["asset_id"]

    # 2. Get Detail
    resp_detail = client.get(f"/v1/assets/{asset_id}")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["id"] == asset_id
    assert resp_detail.json()["kind"] == "dataset"

    # 3. Delete
    resp_del = client.delete(f"/v1/assets/{asset_id}")
    assert resp_del.status_code == 204

    # 4. Verify Not Found
    resp_verify = client.get(f"/v1/assets/{asset_id}")
    assert resp_verify.status_code == 404


def test_workspace_isolation(mock_user):
    """
    Verify that User A cannot see User B's assets.
    """
    # 1. User A Uploads
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as client_a:
        resp = client_a.post("/v1/assets/upload", files={"file": ("usera.csv", b"a", "text/csv")})
        asset_id_a = resp.json()["asset_id"]

    # 2. User B Attempts Access
    user_b = AuthenticatedUser(user_id=uuid.uuid4(), email="userb@example.com", access_token="token-b")
    app.dependency_overrides[get_current_user] = lambda: user_b
    with TestClient(app) as client_b:
        # User B should NOT see User A's asset in their list
        resp_list = client_b.get("/v1/assets")
        data = resp_list.json()
        asset_ids = [item["id"] for item in data.get("items", [])]
        assert asset_id_a not in asset_ids

        # User B should NOT be able to get User A's asset detail
        resp_get = client_b.get(f"/v1/assets/{asset_id_a}")
        assert resp_get.status_code == 404
        
        # User B should NOT be able to delete User A's asset
        resp_del = client_b.delete(f"/v1/assets/{asset_id_a}")
        # Even if it returns 204 (No Content), it shouldn't have deleted it for User A.
        # But we'll verify User A can still see it.
    
    # 3. Verify User A still has it
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as client_a_again:
        resp_get = client_a_again.get(f"/v1/assets/{asset_id_a}")
        assert resp_get.status_code == 200

    app.dependency_overrides.clear()
