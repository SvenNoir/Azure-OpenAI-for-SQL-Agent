import os
import json
from fastapi import FastAPI
from fastapi import APIRouter
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from app.controller.LanggraphController import SQLAgent
from app.controller.AddEmbeddingController import AHMEmbeddingController
from app.controller.CreateIndexController import AHMCreateIndexController
from app.schema.LanggraphModel import SQLAgentRequest, IndexSchema, AddEmbeddingSchema
from fastapi import UploadFile, File, Form


load_dotenv()

app = FastAPI()

app_route = APIRouter()

def generate_stream(request: str, user_id: str, conversation_id: str, access_level: int):
    try:
        for token in SQLAgent.agent_graph(request, user_id, conversation_id, access_level):
            yield token
    except Exception as e:
        yield json.dumps({'error': str(e)})

@app_route.post("/agent-test")
def sql_agent_test(query: SQLAgentRequest):
    return StreamingResponse(
        generate_stream(query.request, query.user_id, query.conversation_id, query.access_level),
        media_type="text/plain"
    )

@app_route.post("/create-index")
def create_index(index_name: IndexSchema):
    return AHMCreateIndexController.create_index(index_name=index_name.index_name)

@app_route.post("/add-embedding")
def add_embedding(file_bytes : UploadFile = File(...), original_filename: str = Form(...), index_name: str = Form(...)):
    return AHMEmbeddingController.flow_multimodal_append_from_bytes(file_bytes= file_bytes, original_filename=original_filename, index_name=index_name)

def api_config(app):
    app.include_router(
        app_route
    )

    @app.get("/")
    def get_desc():
        return {
            "app_name": os.environ.get("APP_NAME"),
            "app_version": os.environ.get("APP_VERSION")
        }

