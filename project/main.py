from celery.result import AsyncResult
from fastapi import Body, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from fastapi import Depends, FastAPI,Header, HTTPException, status

load_dotenv()
from db_utils import *

from worker import create_task


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")



@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", context={"request": request})


@app.post("/tasks", status_code=201, )
def run_task(payload: dict = Body(...)):
    folder_id = payload["folder_id"]
    images = payload.get("images", [])  # Assuming images is a list in the payload
    task = create_task.delay(folder_id, images)
    return JSONResponse({"task_id": task.id})

@app.get("/tasks/{task_id}")
def get_status(task_id: str):
    task_result = AsyncResult(task_id)

    if isinstance(task_result.result, TypeError):
        # Handle TypeError case
        error_message = str(task_result.result)
        result = {
            "batch_task_id": task_id,
            "batch_task_status": task_result.status,
            "batch_error_message": error_message
        }
    else:
        # Normal case
        result = {
            "batch_task_id": task_id,
            "batch_task_status": task_result.status,
            "batch_task_result": task_result.result,
            
        
        }

    return JSONResponse(content=result)

@app.post("/create-token")
async def create_token(business_id: str, business_api_key: str, secret_key: str):
    # query = f"SELECT * FROM users WHERE business_id = '{business_id}' AND business_api_key = '{business_api_key}' AND secret_key = '{secret_key}';"
    # result = execute_query(query, fetch_all=False)
    ## Assuming correct until in gcp, so that db connection works
    result = True # just dummy
    if result:
        business_id = "demo123"
        # If credentials are valid, create and return a secure JWT token
        token_data = {"sub": business_id, "scopes": ["business"]}
        return {"access_token": create_jwt_token(token_data), "token_type": "bearer"}
    else:
        # If credentials are invalid, raise an HTTPException with 401 Unauthorized status
        raise HTTPException(status_code=401, detail="Unauthorized")

