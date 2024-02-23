from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker, declarative_base
from databases import Database
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Depends, HTTPException, status, Form
from sqlalchemy.ext.declarative import DeclarativeMeta
from fastapi.security import HTTPBasic, HTTPBasicCredentials


import os

app = FastAPI()


security = HTTPBasic()

DATABASE_URL = os.getenv('DATABASE_URL')

CLIENT_ACCESS_ID = os.getenv('CLIENT_ACCESS_ID')
CLIENT_ACCESS_KEY = os.getenv('CLIENT_ACCESS_KEY')

engine = create_engine(DATABASE_URL)
metadata = MetaData()

Base: DeclarativeMeta = declarative_base()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("username", String, unique=True, index=True),
    Column("password_hash", String),
)

Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
database = Database(DATABASE_URL)

# JWT settings
SECRET_KEY = os.getenv('SECRETKEY')
ALGORITHM = os.getenv('TOKEN_ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2PasswordBearer for token retrieval
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(String, unique=True, index=True)
    password_hash = Column(String)


@app.post("/register/")
async def register_user(business_id: str = Form(...), business_api_key: str = Form(...), db: Session = Depends(get_db),  credentials: HTTPBasicCredentials = Depends(security),):
    # Check if username is already registered

    if credentials.client_access_id != CLIENT_ACCESS_ID or credentials.client_access_key != CLIENT_ACCESS_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    if db.query(Client).filter(Client.business_id == business_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    hashed_password = get_password_hash(business_api_key)
    user = Client(username=business_id, password_hash=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "User registered successfully"}

@app.post("/token/")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer", "expires_on": access_token_expires}

@app.get("/secure/")
async def secure_endpoint(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    return {"message": "You are authorized!", "username": payload["sub"]}
