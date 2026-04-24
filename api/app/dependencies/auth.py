from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.app.core.config import get_settings
from api.app.core.security import SupabaseAuthVerifier
from api.app.repositories.interfaces import AuthenticatedUser

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_verifier() -> SupabaseAuthVerifier:
    return SupabaseAuthVerifier(get_settings())


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: SupabaseAuthVerifier = Depends(get_auth_verifier),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    return await verifier.verify_access_token(credentials.credentials)
