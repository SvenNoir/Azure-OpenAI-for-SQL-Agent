from typing import List, Annotated, Union
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

class SQLSchema(BaseModel):
    query: str = Field(..., description="query generated from the llm and then to be executed.")

class RouteSchema(BaseModel):
    route: str = Field(..., description="route chosen from the llm output.")

class AISearchSchema(BaseModel):
    data_summary: str = Field(..., description="Summary of the data retrieved from the AI search.")

class IndexSchema(BaseModel):
    index_name: str = Field(..., description="Name of the index.")

class AddEmbeddingSchema(BaseModel):
    file_path: str = Field(..., description="Path to the file to be embedded.")
    index_name: str = Field(..., description="Name of the index to add the embedding.")

class SQLAgentRequest(BaseModel):
    request: str
    user_id: str
    conversation_id: str
    access_level: int
    
class State(TypedDict):
    question: Annotated[List[Union[str]], "question of the user"]
    response: Annotated[List[Union[str]], "response of the LLM"]
    conversation_id : str
    user_id : str
    access_level: int