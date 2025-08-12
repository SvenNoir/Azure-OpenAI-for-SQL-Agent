import azure.functions as func
from fastapi_settings.route import api_config, app as fastapi_app

api_config(fastapi_app)

app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)

