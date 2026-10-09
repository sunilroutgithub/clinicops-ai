import os
import secrets

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

load_dotenv()
security = HTTPBasic(auto_error=False)


def require_login(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
):
    if request.url.path == "/":  # health check stays public
        return

    password = os.getenv("APP_PASSWORD")
    user = os.getenv("APP_USER", "staff")
    if not password:
        raise HTTPException(503, "Server password is not configured")

    ok = (
        credentials is not None
        and secrets.compare_digest(credentials.username.encode(), user.encode())
        and secrets.compare_digest(credentials.password.encode(), password.encode())
    )
    if not ok:
        raise HTTPException(401, "Login required", headers={"WWW-Authenticate": "Basic"})