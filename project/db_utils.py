
from datetime import datetime as dt, timedelta
import jwt
import datetime
import psycopg2
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

load_dotenv()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Database connection parameters
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DATABASE_HOST'),
        database=os.getenv('DATABASE_NAME'),
        port=os.getenv('DATABASE_PORT'),
        user=os.getenv('DATABASE_USERNAME'),
        password=os.getenv('DATABASE_PASSWORD')
    )

# Function to execute a query
def execute_query(query, fetch_all=True):
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(query)
    result = cursor.fetchall() if fetch_all else cursor.fetchone()
    cursor.close()
    connection.close()
    return result




# Security settings
SECRET_KEY = os.getenv('SECRETKEY')
ALGORITHM = os.getenv('TOKEN_ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('TOKEN_LIMIT', 15))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to create JWT token
def create_jwt_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()
    expire = dt.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Function to verify JWT token
def verify_token(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise credentials_exception

