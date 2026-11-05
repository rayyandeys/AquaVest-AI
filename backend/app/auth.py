import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, UserSession

COOKIE_NAME = 'aquavest_session'
SESSION_HOURS = 12


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 310_000)
    return f'pbkdf2_sha256$310000${salt.hex()}${digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        method, rounds, salt, expected = encoded.split('$')
        if method != 'pbkdf2_sha256': return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_session(response: Response, db: Session, user: User):
    token = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                       expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_HOURS * 3600, httponly=True,
                        secure=False, samesite='strict', path='/')


def clear_session(response: Response, request: Request, db: Session):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        digest = hashlib.sha256(token.encode()).hexdigest()
        db.execute(delete(UserSession).where(UserSession.token_hash == digest))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='strict')


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, 'Sign in to access your demo portfolio')
    digest = hashlib.sha256(token.encode()).hexdigest()
    session = db.scalar(select(UserSession).where(UserSession.token_hash == digest))
    now = datetime.now(timezone.utc)
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session and session.expires_at.tzinfo is None else (session.expires_at if session else now)
    if not session or expires <= now:
        if session:
            db.delete(session); db.commit()
        raise HTTPException(401, 'Your session expired. Please sign in again.')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Account no longer exists')
    return user


def public_user(user: User):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'cash_balance': float(user.cash_balance)}
