import os
import json
from fastapi import FastAPI
from fastapi import APIRouter
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.controller.LanggraphController import SQLAgent

app = FastAPI()

app_route = APIRouter()

class SQLAgentRequest(BaseModel):
    request: str
    user_id: str
    conversation_id: str

def generate_stream(request: str, user_id: str, conversation_id: str):
    try:
        for token in SQLAgent.agent_graph(request, user_id, conversation_id):
            yield json.dumps({'content': token})
    except Exception as e:
        yield json.dumps({'error': str(e)})

@app_route.post("/agent-test")
def sql_agent_test(query: SQLAgentRequest):
    return StreamingResponse(
        generate_stream(query.request, query.user_id, query.conversation_id),
        media_type="text/plain"
    )

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

