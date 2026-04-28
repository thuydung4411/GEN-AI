import pytest
from worker.app.services.parser import DatasetParser
from api.app.models.entities import AssetKind, JobStatus

def test_parse_empty_text():
    parser = DatasetParser()
    empty_content = b"   \n  "
    
    with pytest.raises(ValueError, match="extracted NO text output"):
        parser.parse("text/plain", empty_content)

def test_parse_empty_docx():
    # An empty docx might raise a python-docx format error or no text
    from docx import Document
    import io
    doc = Document()
    bytes_io = io.BytesIO()
    doc.save(bytes_io)
    content = bytes_io.getvalue()
    
    parser = DatasetParser()
    with pytest.raises(ValueError, match="extracted NO text output"):
        parser.parse("application/vnd.openxmlformats-officedocument.wordprocessingml.document", content)

def test_chunker_includes_workspace_safety(monkeypatch):
    from worker.app.services.models import ExtractedDataset
    from worker.app.services.chunker import DatasetChunker
    
    doc = ExtractedDataset(content="Hello world test dataset", metadata={"parser": "test"})
    chunker = DatasetChunker(chunk_size=10, chunk_overlap=2)
    chunks = list(chunker.chunk(doc))
    
    assert len(chunks) > 0
    assert "parser" in chunks[0].metadata
    # Ensure chunks output deterministic chunk_index
    assert chunks[0].chunk_index == 0
    assert chunks[-1].chunk_index == len(chunks) - 1

@pytest.mark.anyio
async def test_process_job_fail_on_empty_dataset():
    # We can mock the DB session and Embedder
    from worker.app.main import process_job
    from worker.app.services.storage import StorageReader
    import copy
    
    class MockEngine:
        pass
        
    class MockSessionMaker:
        def __call__(self):
            return self
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def execute(self, stmt, params=None):
            class MockRes:
                def scalar_one_or_none(self):
                    return self.scalar()
                def scalar(self):
                    class FakeDoc:
                        storage_path = "test"
                        mime_type = "text/plain"
                    return FakeDoc()
            return MockRes()
        async def scalar(self, stmt, params=None):
            class FakeDoc:
                storage_path = "test"
                mime_type = "text/plain"
            return FakeDoc()
        async def commit(self):
            pass
        async def rollback(self):
            pass
            
    class MockSettings:
        storage_local_path = "/tmp"

    storage = StorageReader(None)
    # mock read
    async def mock_read(path):
        return b"  \n "
    storage.read = mock_read
    
    class MockTabularParser:
        def parse_and_materialize(self, *args, **kwargs):
            raise ValueError("extracted NO text output")
    
    job_info = {
        "id": "job1",
        "asset_id": "doc1",
        "asset_version_id": "ver1",
        "asset_kind": AssetKind.dataset,
        "dataset_id": "doc1",
        "dataset_version_id": "ver1",
        "workspace_id": "ws1"
    }
    
    # Process job should catch the ValueError and call fail_job.
    # fail_job updates ingestion_jobs and datasets.
    # We can track the execute calls in the mock session.
    execute_calls = []
    class TrackingSession(MockSessionMaker):
        async def execute(self, stmt, params=None):
            execute_calls.append(str(stmt).strip())
            return await super().execute(stmt, params)
        async def scalar(self, stmt, params=None):
            execute_calls.append(str(stmt).strip())
            return await super().scalar(stmt, params)

    session_maker = TrackingSession()
    await process_job(MockSettings(), job_info, session_maker, storage, MockTabularParser(), None)
    
    # Check if 'UPDATE ingestion_jobs SET status' to 'failed' happened
    failed_job_update = any("failed" in call or "JobStatus.failed" in call or "error_message" in call for call in execute_calls)
    assert failed_job_update, "Expected job to be marked failed when dataset is empty"


@pytest.mark.anyio
async def test_process_knowledge_happy_path():
    from worker.app.main import process_job
    from worker.app.services.storage import StorageReader
    
    import tempfile

    class MockSettings:
        storage_local_path = tempfile.gettempdir()

    class TrackingSession:
        def __init__(self):
            self.execute_calls = []
            self.added_items = []
        def __call__(self): return self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        async def scalar(self, stmt):
            class FakeVer:
                storage_path = "test.docx"
            return FakeVer()
        async def execute(self, stmt, params=None):
            self.execute_calls.append(str(stmt).strip())
            class MockRes:
                def scalar_one_or_none(self):
                    return None
                def scalar(self):
                    class FakeVer:
                        storage_path = "test.docx"
                    return FakeVer()
            return MockRes()
        def add_all(self, items):
            self.added_items.extend(items)
        async def commit(self): pass
        async def rollback(self): pass

    storage = StorageReader(None)
    async def mock_read(path): return b"test pdf content"
    storage.read = mock_read
    
    captured_file_paths = []

    class MockKnowledgeParser:
        async def process_file(self, *args, **kwargs):
            captured_file_paths.append(args[0])
            from api.app.models.entities import KnowledgeChunk
            from uuid import uuid4
            return [KnowledgeChunk(id=uuid4(), knowledge_version_id=kwargs.get("knowledge_version_id"), chunk_index=0, content="test", metadata_json={})]
            
    job_info = {
        "id": "job1",
        "asset_id": "doc1",
        "asset_version_id": "ver1",
        "asset_kind": AssetKind.knowledge,
        "knowledge_asset_id": "doc1",
        "knowledge_version_id": "ver1",
        "workspace_id": "ws1"
    }

    session_maker = TrackingSession()
    await process_job(MockSettings(), job_info, session_maker, storage, None, MockKnowledgeParser())


    
    # Assert processing state
    assert any("UPDATE assets SET status = 'processing'" in call for call in session_maker.execute_calls)
    assert any("UPDATE knowledge_assets SET status = 'processing'" in call for call in session_maker.execute_calls)
    # Assert idempotency cleanup
    assert any("DELETE FROM knowledge_chunks WHERE" in call for call in session_maker.execute_calls)
    # Assert chunks added
    assert len(session_maker.added_items) == 1
    assert captured_file_paths and captured_file_paths[0].endswith(".docx")
    # Assert ready state
    assert any("UPDATE assets SET status = 'ready'" in call for call in session_maker.execute_calls)
    assert any("UPDATE knowledge_assets SET status = 'ready'" in call for call in session_maker.execute_calls)
    assert any("UPDATE ingestion_jobs SET status = 'ready'" in call for call in session_maker.execute_calls)

@pytest.mark.anyio
async def test_process_knowledge_fails_on_empty_chunks():
    from worker.app.main import process_job
    from worker.app.services.storage import StorageReader

    import tempfile

    class MockSettings:
        storage_local_path = tempfile.gettempdir()

    class TrackingSession:
        def __init__(self):
            self.execute_calls = []
        def __call__(self): return self
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        async def scalar(self, stmt):
            class FakeVer:
                storage_path = "test"
            return FakeVer()
        async def execute(self, stmt, params=None):
            self.execute_calls.append(str(stmt).strip())
            class MockRes:
                def scalar_one_or_none(self):
                    return None
            return MockRes()
        def add_all(self, items):
            raise AssertionError("Knowledge chunks should not be added when parser returns empty output")
        async def commit(self): pass
        async def rollback(self): pass

    storage = StorageReader(None)
    async def mock_read(path): return b"test docx content"
    storage.read = mock_read

    class MockKnowledgeParser:
        async def process_file(self, *args, **kwargs):
            return []

    job_info = {
        "id": "job1",
        "asset_id": "doc1",
        "asset_version_id": "ver1",
        "asset_kind": AssetKind.knowledge,
        "knowledge_asset_id": "doc1",
        "knowledge_version_id": "ver1",
        "workspace_id": "ws1"
    }

    session_maker = TrackingSession()
    await process_job(MockSettings(), job_info, session_maker, storage, None, MockKnowledgeParser())

    assert any("UPDATE ingestion_jobs SET status = 'failed'" in call for call in session_maker.execute_calls)
    assert any("UPDATE assets SET status = 'failed'" in call for call in session_maker.execute_calls)
    assert any("UPDATE knowledge_assets SET status = 'failed'" in call for call in session_maker.execute_calls)
