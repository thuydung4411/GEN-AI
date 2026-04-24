import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from api.app.core.config import Settings


@dataclass(slots=True)
class StoredFile:
    backend: str
    path: str


class StorageService(Protocol):
    async def save(self, *, path: str, content: bytes, content_type: str) -> StoredFile: ...

    async def delete(self, *, path: str) -> None: ...


class LocalStorageService:
    def __init__(self, root: str):
        self._root = Path(root)

    async def save(self, *, path: str, content: bytes, content_type: str) -> StoredFile:
        target = self._root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, content)
        return StoredFile(backend="local", path=path)

    async def delete(self, *, path: str) -> None:
        target = self._root / path
        if target.exists():
            await asyncio.to_thread(target.unlink)


class SupabaseStorageService:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def save(self, *, path: str, content: bytes, content_type: str) -> StoredFile:
        headers = {
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
            "apikey": self._settings.supabase_service_role_key,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        url = (
            f"{self._settings.supabase_url}/storage/v1/object/"
            f"{self._settings.supabase_storage_bucket}/{path}"
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, content=content)

        response.raise_for_status()
        return StoredFile(backend="supabase", path=path)

    async def delete(self, *, path: str) -> None:
        headers = {
            "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
            "apikey": self._settings.supabase_service_role_key,
        }
        url = (
            f"{self._settings.supabase_url}/storage/v1/object/"
            f"{self._settings.supabase_storage_bucket}/{path}"
        )

        async with httpx.AsyncClient(timeout=20.0) as client:
            await client.delete(url, headers=headers)


def build_storage_service(settings: Settings) -> StorageService:
    if settings.storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError("Supabase storage backend requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return SupabaseStorageService(settings)

    return LocalStorageService(settings.local_storage_root)
