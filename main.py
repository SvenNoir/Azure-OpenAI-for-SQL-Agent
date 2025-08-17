import os
import uvicorn
from fastapi_settings.route import api_config, app

os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_ENDPOINT"] = os.environ.get("LANGCHAIN_ENDPOINT")
os.environ["LANGCHAIN_TRACING"] = os.environ.get("LANGCHAIN_TRACING")
os.environ["LANGCHAIN_PROJECT"] = os.environ.get("LANGCHAIN_PROJECT")

api_config(app)

if __name__ == "__main__":
    uvicorn.run(app, host = "localhost", port=8000)