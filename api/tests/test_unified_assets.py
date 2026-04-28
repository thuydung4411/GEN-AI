import uuid
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app.core.config import Settings, get_settings
from api.app.dependencies.auth import get_current_user
from api.app.dependencies.services import get_asset_service
from api.app.main import create_app
from api.app.repositories.in_memory import (
    InMemoryAssetRepository,
    InMemoryDatasetRepository,
    InMemoryKnowledgeRepository,
)
from api.app.repositories.interfaces import AuthenticatedUser
from api.app.services.assets import AssetService
from api.app.services.datasets import DatasetService
from api.app.services.knowledge import KnowledgeService
from api.app.services.parsers.tabular import TabularParser
from api.app.services.storage import LocalStorageService


def build_asset_test_app(initial_user: AuthenticatedUser):
    temp_root = Path("tmp/test-storage") / str(uuid.uuid4())
    temp_root.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        storage_backend="local",
        local_storage_root=str(temp_root),
        auto_create_schema=False,
    )
    app = create_app(settings)

    workspaces_by_user = {}
    dataset_repo = InMemoryDatasetRepository(workspaces_by_user)
    knowledge_repo = InMemoryKnowledgeRepository(workspaces_by_user)
    asset_repo = InMemoryAssetRepository(dataset_repo, knowledge_repo)
    storage_service = LocalStorageService(str(temp_root))
    tabular_parser = TabularParser(str(temp_root))
    dataset_service = DatasetService(
        repository=dataset_repo,
        storage_service=storage_service,
        settings=settings,
        tabular_parser=tabular_parser,
    )
    knowledge_service = KnowledgeService(
        repository=knowledge_repo,
        storage_service=storage_service,
        settings=settings,
    )
    asset_service = AssetService(asset_repo, dataset_service, knowledge_service, settings)
    current_user = {"value": initial_user}

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = lambda: current_user["value"]
    app.dependency_overrides[get_asset_service] = lambda: asset_service
    return app, temp_root, current_user


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
    app, temp_root, _ = build_asset_test_app(mock_user)

    with TestClient(app) as c:
        yield c
    shutil.rmtree(temp_root, ignore_errors=True)

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
    client.post("/v1/assets/upload", files={"file": ("table.csv", b"a,b\n1,2", "text/csv")})
    client.post("/v1/assets/upload", files={"file": ("policy.txt", b"Policy text", "text/plain")})

    response = client.get("/v1/assets")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert {item["kind"] for item in data["items"]} == {"dataset", "knowledge"}


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
    app, temp_root, current_user = build_asset_test_app(mock_user)
    try:
        with TestClient(app) as client_a:
            resp = client_a.post("/v1/assets/upload", files={"file": ("usera.csv", b"a", "text/csv")})
            asset_id_a = resp.json()["asset_id"]

        # 2. User B Attempts Access
        user_b = AuthenticatedUser(user_id=uuid.uuid4(), email="userb@example.com", access_token="token-b")
        current_user["value"] = user_b
        with TestClient(app) as client_b:
            resp_list = client_b.get("/v1/assets")
            data = resp_list.json()
            asset_ids = [item["id"] for item in data.get("items", [])]
            assert asset_id_a not in asset_ids

            resp_get = client_b.get(f"/v1/assets/{asset_id_a}")
            assert resp_get.status_code == 404

            resp_del = client_b.delete(f"/v1/assets/{asset_id_a}")
            assert resp_del.status_code == 404

        # 3. Verify User A still has it
        current_user["value"] = mock_user
        with TestClient(app) as client_a_again:
            resp_get = client_a_again.get(f"/v1/assets/{asset_id_a}")
            assert resp_get.status_code == 200
    finally:
        app.dependency_overrides.clear()
        shutil.rmtree(temp_root, ignore_errors=True)
