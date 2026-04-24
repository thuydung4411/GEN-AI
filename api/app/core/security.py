from uuid import UUID

import httpx
from fastapi import HTTPException, status

from api.app.core.config import Settings
from api.app.repositories.interfaces import AuthenticatedUser


class SupabaseAuthVerifier:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def verify_access_token(self, access_token: str) -> AuthenticatedUser:
        if not self._settings.supabase_url or not self._settings.supabase_anon_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Supabase auth is not configured.",
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "apikey": self._settings.supabase_anon_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self._settings.supabase_url}/auth/v1/user", headers=headers)

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
            )

        payload = response.json()
        user_id = payload.get("id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification did not return a user id.",
            )

        return AuthenticatedUser(
            user_id=UUID(user_id),
            email=payload.get("email"),
            access_token=access_token,
        )
