
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

TABLE = os.getenv('TABLE_NAME')

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
def execute_query(query, params=None, fetch_all=True):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute(query, params)
        result = cursor.fetchall() if fetch_all else cursor.fetchone()
        return result
    finally:
        cursor.close()
        connection.close()



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


def update_webhook_url(user_id: str, webhook_url: str):
    # Check if the user with the given user_id exists before updating the webhook_url
    check_user_query = f"SELECT id FROM {TABLE} WHERE business_id = %s;"
    check_user_params = (user_id,)
    existing_user = execute_query(check_user_query, check_user_params, fetch_all=False)

    if existing_user:
        # If the user exists, update the webhook_url
        update_query = f"UPDATE {TABLE} SET webhook_url = %s WHERE user_id = %s;"
        update_params = (webhook_url, user_id)
        execute_query(update_query, update_params)
    else:
        # If the user does not exist, you might want to handle this case accordingly
        raise HTTPException(status_code=404, detail="User not found")


def get_webhook_url(business_id: str):
    # Query to retrieve the webhook_url for the given user_id
    query = f"SELECT webhook_url FROM {TABLE} WHERE business_id = %s;"
    params = (business_id,)
    
    # Execute the query to get the webhook_url
    result = execute_query(query, params, fetch_all=False)

    if result:
        return result[0]  # Assuming the result is a single value (webhook_url)
    else:
        
        raise HTTPException(status_code=404, detail="Webhook url not configured...")

def get_aws_bucket_name(business_id: str):

    query = f"SELECT aws_bucket FROM {TABLE} WHERE business_id = %s;"
    params = (business_id,)

    result = execute_query(query, params, fetch_all=False)

    if result:
        return result[0]  # Assuming the result is a single value (webhook_url)
    else:
        
        raise HTTPException(status_code=404, detail="AWS Bucket not configured...")
