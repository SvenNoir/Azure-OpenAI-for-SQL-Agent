import os
import uvicorn
from fastapi_settings.route import api_config, app

os.environ["LANGCHAIN_API_KEY"] = "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"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Vhatbot-GYS"

api_config(app)

if __name__ == "__main__":
    uvicorn.run(app, host = "localhost", port=8000)