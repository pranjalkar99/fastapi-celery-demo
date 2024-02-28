from celery.result import AsyncResult
from fastapi import Body, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from utils import *
from fastapi import Depends, FastAPI,Header, HTTPException, status
from fastapi.responses import HTMLResponse
import psutil,json

load_dotenv()
from db_utils import *

from worker import create_task





app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

TABLE = os.getenv('TABLE_NAME')

import os

def read_alllogs():
    logs_folder_path = "logs"  # Adjust the path accordingly
    logs_content = ""

    try:
        for filename in os.listdir(logs_folder_path):
            if filename.endswith(".log") or filename.endswith(".txt"):
                file_path = os.path.join(logs_folder_path, filename)
                with open(file_path, "r") as file:
                    logs_content += f"\n=== {filename} ===\n\n"
                    logs_content += file.read()
    except FileNotFoundError:
        return "Logs folder not found"
    except Exception as e:
        return f"Error reading logs: {str(e)}"

    return logs_content
    

@app.get("/device-stats", dependencies=[Depends(authenticate)], response_class=JSONResponse)
async def get_device_stats():
    # Get CPU usage
    cpu_usage = psutil.cpu_percent()

    # Get memory usage
    memory = psutil.virtual_memory()
    memory_usage = {
        "total": memory.total,
        "available": memory.available,
        "used": memory.used,
        "percent": memory.percent
    }

    # Get disk space
    disk = psutil.disk_usage("/")
    disk_space = {
        "total": disk.total,
        "used": disk.used,
        "free": disk.free,
        "percent": disk.percent
    }

    device_stats = {
        "CPU Usage": f"{cpu_usage}%",
        "Memory Usage": memory_usage,
        "Disk Space": disk_space
    }

    return device_stats


@app.get("/", dependencies=[Depends(authenticate)], response_class=HTMLResponse)
async def home(request: Request):
    # device_stats = await get_device_stats()
    logs_content = read_alllogs()

    return templates.TemplateResponse(
        "home.html",
        context={
            "request": request,
                # "device_stats": json.dumps(device_stats),
            "logs_content": logs_content
        }
    )




@app.post("/tasks", status_code=201)
def run_task(payload: dict = Body(...), current_user: dict = Depends(verify_token)):
    folder_id = payload["folder_id"]
    images = payload.get("images", [])  # Assuming images is a list in the payload
    
    webhook_url = get_webhook_url(current_user["sub"])

    aws_bucket = get_aws_bucket_name(current_user["sub"])

    task = create_task.delay(folder_id, images, webhook_url, aws_bucket)
    return JSONResponse({"task_id": task.id})

@app.get("/tasks/{task_id}")
def get_status(task_id: str, current_user: dict = Depends(verify_token)):
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
async def create_token(
    business_id: str= Header(..., description="Business ID"), 
    business_api_key: str = Header(..., description="Business API Key"),
    secret_key: str = Header(..., description="Secret Key")
):
    query = f"SELECT * FROM {TABLE} WHERE business_id = %s AND business_api_key = %s AND secret_key = %s;"
    params = (business_id, business_api_key, secret_key)
    
    result = execute_query(query, params, fetch_all=False)

    if result:
        # If credentials are valid, create and return a secure JWT token
        token_data = {"sub": business_id, "scopes": ["business"]}
        return {"access_token": create_jwt_token(token_data), "token_type": "bearer"}
    else:
        # If credentials are invalid, raise an HTTPException with 401 Unauthorized status
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/set-webhook")
def set_webhook(
    webhook_url: str,
    current_user: dict = Depends(verify_token)
):
    update_webhook_url(user_id=current_user["sub"], webhook_url=webhook_url)
    
    return {"message": "Webhook set successfully"}