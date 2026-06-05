from fastapi import FastAPI, Form, UploadFile, File, Depends, Request
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi_limiter.depends import RateLimiter
from fastapi import Header, HTTPException
from fastapi.staticfiles import StaticFiles
from DATABASE.SQL_Database import connect
from DATABASE.Redis_Connection import redis_cache
from Security.Advance_Logger import logger
from Security.JWT_token import create_token, decode_token
from Security.get_secretes import load_env_from_secret
from RAG.EmbeddingsGenerationnStorage import EmbeddingsALL
from fastapi.responses import FileResponse
from Files_Management.Files_Parser import ParseFile
from RAG.Vector_Store import Vector
from fastapi_limiter import FastAPILimiter
from pydantic import BaseModel
from urllib.parse import urlparse
import redis.asyncio as redis
from pathlib import Path
import asyncio
import os
import tempfile
import shutil


REDIS_URL = load_env_from_secret("REDIS_HOST")

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_cache.initialize()
    await FastAPILimiter.init(redis_cache.get_client())
    yield
    if redis_cache.pool:
        await redis_cache.pool.disconnect()

Embedding_Generator = EmbeddingsALL()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static", html=True), name="static")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    client_token: str
    visitor_id: str
    message: str

class UrlUpdateRequest(BaseModel):
    allowed_url: str

def get_user_id(authorization: str = Header(...)):
    try:
        token = authorization.split(" ")[1]  # "Bearer <token>"
        return decode_token(token)
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    with open("templates/landing.html", "r", encoding="utf-8") as file:
        return file.read()
    
@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("templates/login.html", "r", encoding="utf-8") as file:
        return file.read()

@app.get("/signin", response_class=HTMLResponse)
async def signin_page():
    with open("templates/signin.html", "r", encoding="utf-8") as file:
        return file.read()

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    with open("templates/dashboard.html", "r", encoding="utf-8") as file:
        return file.read()


@app.post("/login", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def login( email: str = Form(...), password: str = Form(...) ):
    try:
        user = connect.login_user(email=email, password=password)
        if user:
            logger.info(user)
            token = create_token(user_id=user["id"], email=email)
            return JSONResponse(
                        {
                            "success": True,
                            "message": "Login successful",
                            "token": token,
                            "user": {
                                "id": user["id"],
                                "name": user["name"],
                                "email": user["email"],
                                "user_id": user["user_id"]
                            }
                        }
                    )
        else:
            return JSONResponse(
                {
                    "success": False,
                    "message": "User not found"
                }
            )
    except Exception as e:
        logger.error("Frontend_Connection.login", e)

@app.post("/signin", dependencies=[Depends(RateLimiter(times=3, seconds=60))])
async def signin(name: str = Form(...), url: str = Form(...), email: str = Form(...), password: str = Form(...)):
    try:
        existing_id = connect.get_Id_From_email(email=email)
        if existing_id:
            return JSONResponse({"success": False, "message": "Email already registered"})
        
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return JSONResponse({"success": False, "message": "Provide a fully formatted deployment URL."})
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}".lower()

        user_token = connect.create_user(name=name, url=base_url, email=email, password=password)
        if user_token:
            user_id = connect.get_Id_From_client_token(client_token=user_token)
            token = create_token(user_id=user_id, email=email)
            return JSONResponse({
                "success": True,
                "message": "sign-in successful",
                "token": token,
                "user": {
                    "id": user_id,
                    "name": name,
                    "email": email,
                    "user_token": user_token
                }
            })
        return JSONResponse({"success": False, "message": "Failed to complete account registration."})
    except Exception as e:
        logger.error("Frontend_Connection.signin", e)
        return JSONResponse({"success": False, "message": "Internal error handling signin profiles."})

@app.get("/getSettings")
async def get_settings(user_id: int = Depends(get_user_id)):
    try:
        user_data = connect.get_user_by_id(user_id) 
        return JSONResponse({
            "success": True,
            "allowed_url": user_data.url,
            "client_token": user_data.user_id
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})
    
@app.post("/updateUrl")
async def update_url(req: UrlUpdateRequest, user_id: int = Depends(get_user_id)):
    try:
        parsed_url = urlparse(req.allowed_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return JSONResponse({"success": False, "message": "Invalid format. Provide a complete base URL."})
        
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}".lower()
        connect.update_user_allowed_url(user_id=user_id, allowed_url=base_url)
        return JSONResponse({"success": True, "message": f"Allowed base domain targeted to {base_url}"})
    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})
    
@app.post("/addDocument", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def add_document(user_id: int = Depends(get_user_id), files: list[UploadFile] = File(...) ):
    try:
        uploaded_files = []
        failed_files = []

        for file in files:
            try:
                temp_path = None

                suffix = os.path.splitext( file.filename )[1]
                file_name = file.filename
                file_extension = Path(file_name).suffix

                BLACKLISTED_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.z', '.exe'}
                if file_extension in BLACKLISTED_EXTENSIONS:
                    failed_files.append({
                        "filename": file.filename,
                        "reason": "Blocked extension"
                    })
                    continue
                
                MAX_FILE_SIZE = 15 * 1024 * 1024  
                file.file.seek(0, os.SEEK_END)
                actual_size = file.file.tell()
                file.file.seek(0)

                if actual_size > MAX_FILE_SIZE:
                    failed_files.append({
                        "filename": file.filename,
                        "reason": "File too large"
                    })

                    continue

                # Create temp file
                with tempfile.NamedTemporaryFile( delete=False, suffix=suffix ) as temp_file:
                    shutil.copyfileobj( file.file, temp_file )
                    temp_path = temp_file.name

                extracted_text = await ParseFile.parse_any_file(
                    temp_path
                )

                stored_ = await Embedding_Generator.generate_and_store_embeddings(user_id=user_id, file_name=file_name, extension=file_extension, Text=extracted_text)
                if stored_:
                    uploaded_files.append(
                        file.filename
                    )
                else:
                    logger.error("add_document", "Failed to add document.")
                    failed_files.append({
                            "filename": file.filename,
                            "reason": "Embedding failed"
                        })
                
            except Exception as e:
                logger.error("for_loop.add_document", e)
                failed_files.append({
                "filename": file.filename,
                "reason": str(e)
            })
            
            finally:

                if (temp_path and os.path.exists(temp_path)):
                    os.remove(temp_path)

        await redis_cache.invalidate_user_cache(user_id=user_id)

        return JSONResponse({
            "success": True,
            "uploaded": uploaded_files,
            "failed": failed_files
        })
    
    except Exception as e:
        logger.error("add_documents", e)
        return JSONResponse(
            {
                "success": False,
                "message": str(e)
            }
        )
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/show_documents")
async def show_documents(user_id: int = Depends(get_user_id)):
    try:
        cache_key = f"user_docs_meta:{user_id}"

        cached_metadata = await redis_cache.get_json(cache_key)
        if cached_metadata is not None:
            return JSONResponse({
                "success": True,
                "message": "Here is the list (cached)",
                "Documents_data": cached_metadata
            })
        
        result = connect.get_documents_data_by_userId(user_id=user_id)
        if result:
            json_compatible_data = jsonable_encoder(result)
            await redis_cache.set_json(cache_key, json_compatible_data, ex=600)
            return JSONResponse(
                {
                    "success": True,
                    "message": "Here is the list",
                    "Documents_data": json_compatible_data
                }
            )
        return JSONResponse(
            {
                "success": False,
                "message": "Failed to fetch data",
                "Documents_data": []
            }
        )
    except Exception as e:
        logger.error("show_documents", e)
        return JSONResponse(
            {
                "success": False,
                "message": "Failed to fetch data",
                "Documents_data": []
            }
        )
    
@app.post("/delete_document")
async def delete_document_from_id(Document_id: int, user_id: int = Depends(get_user_id)):
    try:
        result = connect.delete_document(user_id=user_id, document_id=Document_id)
        Vector_ = Vector.delete_vectors_by_document_id(document_id=Document_id, user_id=user_id)
        if result and Vector_:
            await redis_cache.invalidate_user_cache(user_id=user_id)
            return JSONResponse(
                {
                    "success": True,
                    "message": "Document Deleted",
                    "Numbers_Of_Document_deleted": result
                }
            )
        return JSONResponse(
                {
                    "success": False,
                    "message": "Failed to fetch data",
                    "Numbers_Of_Document_deleted": 0
                }
            )
    except Exception as e:
        logger.error("delete_document_from_id", e)
        return JSONResponse(
            {
                "success": False,
                "message": "Failed to fetch data",
                "Numbers_Of_Document_deleted": 0
            }
        )
from fastapi.encoders import jsonable_encoder

@app.post("/getclientsdata")
async def get_client_data(user_id: int = Depends(get_user_id)):
    try:
        data = connect.get_client_data_by_userid(user_id=user_id)
        
        if data is not None and not isinstance(data, (list, tuple, set)):
            data = [data]
        elif data is None:
            data = []

        processed_list = []
        for row in data:
            if hasattr(row, "_mapping"): 
                processed_list.append(dict(row._mapping))
            elif hasattr(row, "keys") and callable(getattr(row, "keys", None)): 
                processed_list.append({key: getattr(row, key, None) for key in row.keys()})
            elif isinstance(row, dict):
                processed_list.append(row)
            else:
                try:
                    processed_list.append(dict(row))
                except (TypeError, ValueError):
                    processed_list.append({k: v for k, v in vars(row).items() if not k.startswith('_')})

        json_compatible_data = jsonable_encoder(processed_list)
        
        return JSONResponse(
            {
                "success": True,
                "message": "Here is the client data",
                "Client_data": json_compatible_data
            }
        )
    except Exception as e:
        logger.error("get_client_data", e)
        return JSONResponse(
            {
                "success": False,
                "message": f"Serialization failure handled: {str(e)}",
                "Client_data": []
            },
            status_code=500
        )

@app.post("/chat")
async def handle_incoming_request(req: ChatRequest, request: Request):
    client_token = req.client_token
    message = req.message
    visitor_id = req.visitor_id

    user_id = connect.get_Id_From_client_token(client_token=client_token)
    if not user_id:
        raise HTTPException(status_code=404, detail="Invalid client token")

    origin = request.headers.get("origin") or request.headers.get("referer")

    user_data = connect.get_user_by_id(user_id)
    allowed_base_url = user_data.url if user_data else None

    if allowed_base_url:
        if not origin:
            raise HTTPException(status_code=403, detail="Requests must originate from a verified web application environment.")
        
        parsed_origin = urlparse(origin)
        request_base_url = f"{parsed_origin.scheme}://{parsed_origin.netloc}".lower()

        # Check if the clean base domain matches
        if request_base_url != allowed_base_url.strip().lower():
            raise HTTPException(status_code=403, detail="Domain unauthorized for deployment.")

    ans = await EmbeddingsALL.answer_from_embeddings(user_id=user_id, user_query=message, visitor_id=visitor_id)
    return {"reply": ans}


@app.get("/widget.js")
async def serve_widget():
    return FileResponse("static/widget.js", media_type="application/javascript")