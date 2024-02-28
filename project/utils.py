from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


import os


security = HTTPBasic()


CLIENT_ACCESS_ID = os.getenv('CLIENT_ACCESS_ID')
CLIENT_ACCESS_KEY = os.getenv('CLIENT_ACCESS_KEY')


def authenticate( credentials: HTTPBasicCredentials = Depends(security),):
    # Check if username is already registered

    if credentials.client_access_id != CLIENT_ACCESS_ID or credentials.client_access_key != CLIENT_ACCESS_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Basic"},
        )

    



