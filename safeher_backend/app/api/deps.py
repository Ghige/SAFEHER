from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from uuid import UUID

from app.config import settings
from app.db.session import get_db
from app.models.user import User

# Swagger/OpenAPI OAuth2 password flow posts form data to tokenUrl (not JSON login).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Validate JWT token and return the current user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user = db.query(User).filter(User.id == UUID(user_id)).first()
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    if user is None:
        raise credentials_exception
    return user


def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require phone OTP verification before SOS and alert mutations."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Phone number not verified. Complete OTP verification first.",
        )
    return current_user
