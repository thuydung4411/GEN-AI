from pathlib import Path
import shutil
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from fastapi import status, HTTPException

from api.app.core.config import Settings, get_settings
from api.app.dependencies.auth import get_current_user
from api.app.dependencies.services import get_dataset_service, get_knowledge_service
from api.app.main import create_app
from api.app.repositories.in_memory import InMemoryDatasetRepository, InMemoryKnowledgeRepository
from api.app.repositories.interfaces import AuthenticatedUser
from api.app.services.datasets import DatasetService
from api.app.services.parsers.tabular import TabularParser
from api.app.services.knowledge import KnowledgeService
from api.app.services.storage import LocalStorageService

# Global state for testing auth overrides
test_user_context = {"user": None}

def build_test_client():
    temp_root = Path("tmp/test-storage")
    temp_root.mkdir(parents=True, exist_ok=True)
    storage_root = temp_root / str(uuid4())
    storage_root.mkdir(parents=True, exist_ok=True)
    
    settings = Settings(
        storage_backend="local",
        local_storage_root=str(storage_root),
        max_upload_size_mb=0.001, 
        auto_create_schema=False,
    )
    
    app = create_app(settings)
    
    # Repos and Services
    dataset_repo = InMemoryDatasetRepository()
    knowledge_repo = InMemoryKnowledgeRepository()
    storage_service = LocalStorageService(str(storage_root))
    tabular_parser = TabularParser(str(storage_root))
    
    ds_service = DatasetService(repository=dataset_repo, storage_service=storage_service, settings=settings, tabular_parser=tabular_parser)
    kn_service = KnowledgeService(repository=knowledge_repo, storage_service=storage_service, settings=settings)

    # Overrides
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_dataset_service] = lambda: ds_service
    app.dependency_overrides[get_knowledge_service] = lambda: kn_service
    
    def override_get_current_user():
        u = test_user_context["user"]
        if u is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return u
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    client = TestClient(app)
    return client, storage_root


def test_auth_guard():
    client, storage_root = build_test_client()
    try:
        test_user_context["user"] = None
        
        # Test Dataset list
        res1 = client.get("/v1/datasets")
        assert res1.status_code == 401
        
        # Test Knowledge list
        res2 = client.get("/v1/knowledge")
        assert res2.status_code == 401
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_max_upload_size_limit():
    client, storage_root = build_test_client()
    try:
        test_user_context["user"] = AuthenticatedUser(
            user_id=uuid4(), email="u@e.com", access_token="t"
        )
        
        large_content = b"x" * 2000
        response = client.post(
            "/v1/datasets/upload",
            files={"file": ("data.csv", large_content, "text/csv")},
        )
        assert response.status_code == 413
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_workspace_isolation():
    client, storage_root = build_test_client()
    try:
        u1 = AuthenticatedUser(user_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), email="a@e.com", access_token="t1")
        u2 = AuthenticatedUser(user_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), email="b@e.com", access_token="t2")

        # U1 uploads
        test_user_context["user"] = u1
        client.post("/v1/datasets/upload", files={"file": ("a.csv", b"a", "text/csv")})
        client.post("/v1/knowledge/upload", files={"file": ("a.txt", b"a", "text/plain")})
        
        # U1 sees them
        assert len(client.get("/v1/datasets").json()["items"]) == 1
        assert len(client.get("/v1/knowledge").json()) == 1

        # U2 sees nothing
        test_user_context["user"] = u2
        assert len(client.get("/v1/datasets").json()["items"]) == 0
        assert len(client.get("/v1/knowledge").json()) == 0
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_lane_separation():
    client, storage_root = build_test_client()
    try:
        test_user_context["user"] = AuthenticatedUser(user_id=uuid4(), email="u@e.com", access_token="t")
        
        # Knowledge rejects CSV
        res_k = client.post("/v1/knowledge/upload", files={"file": ("data.csv", b"a", "text/csv")})
        assert res_k.status_code == 400
        
        # Dataset rejects PDF
        res_d = client.post("/v1/datasets/upload", files={"file": ("doc.pdf", b"a", "application/pdf")})
        assert res_d.status_code == 400
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)


def test_real_wiring_probe():
    # Only override the auth part, let the services wire themselves
    # This detects NameError/ImportError in dependencies/services.py
    settings = Settings(auto_create_schema=False)
    app = create_app(settings)
    
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(user_id=uuid4(), email="m@e.com", access_token="t")
    app.dependency_overrides[get_settings] = lambda: settings
    
    client = TestClient(app)
    # If the app starts and resolves dependencies without error, wiring is OK
    # It might return a 500 because of real DB missing, but NameError will be caught.
    res = client.get("/v1/knowledge")
    assert res.status_code != 500 or "NameError" not in res.text
