import uuid
from typing import Annotated

import httpx
import structlog
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import User, get_session

logger = structlog.get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


class ClerkUser(BaseModel):
    clerk_id: str
    email: str
    name: str | None = None
    avatar_url: str | None = None


async def verify_clerk_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
) -> ClerkUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")

    token = credentials.credentials

    try:
        # Verify with Clerk's JWKS endpoint
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.clerk.com/v1/tokens/verify",
                headers={
                    "Authorization": f"Bearer {settings.clerk_secret_key}",
                    "Content-Type": "application/json",
                },
                json={"token": token},
            )

        if resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        payload = resp.json()
        return ClerkUser(
            clerk_id=payload.get("sub", ""),
            email=payload.get("email", ""),
            name=payload.get("name"),
            avatar_url=payload.get("image_url"),
        )

    except httpx.HTTPError:
        # Fallback: decode JWT locally (for development)
        try:
            payload = jwt.decode(
                token,
                settings.clerk_jwt_verification_key,
                algorithms=["RS256"],
                options={"verify_exp": True},
            )
            return ClerkUser(
                clerk_id=payload.get("sub", ""),
                email=payload.get("email", ""),
                name=payload.get("name"),
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}",
            )


async def get_current_user(
    clerk_user: Annotated[ClerkUser, Depends(verify_clerk_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Get or create user from Clerk identity."""
    result = await session.execute(
        select(User).where(User.clerk_id == clerk_user.clerk_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            clerk_id=clerk_user.clerk_id,
            email=clerk_user.email,
            name=clerk_user.name,
            avatar_url=clerk_user.avatar_url,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Created new user", clerk_id=clerk_user.clerk_id)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_session)]
