from typing import List, Annotated, Union
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

class SQLSchema(BaseModel):
    query: str = Field(..., description="query generated from the llm and then to be executed.")

class SQLAgentRequest(BaseModel):
    request: str
    user_id: str
    conversation_id: str
    
class State(TypedDict):
    question: Annotated[List[Union[str]], "question of the user"]
    response: Annotated[List[Union[str]], "response of the LLM"]
    conversation_id : str
    user_id : str