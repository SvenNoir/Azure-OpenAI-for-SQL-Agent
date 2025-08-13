#import os
#import json
#import logging
#import azure.functions as func
#from dotenv import load_dotenv
#from app.schema.LanggraphModel import SQLAgentRequest
#from app.controller.LanggraphController import SQLAgent

import azure.functions as func
import logging
import json
import os
from dotenv import load_dotenv
from app.controller.LanggraphController import SQLAgent
from fastapi_settings.route import api_config, app as fastapi_app
#from fastapi.responses import StreamingResponse
#from azurefunctions.extensions.http.fastapi import Request, StreamingResponse

load_dotenv()

api_config(fastapi_app)

app = func.AsgiFunctionApp(app = fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)

#app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
#
#
#@app.route(route="test1")  # Root route
#def test1(req: func.HttpRequest) -> func.HttpResponse:
#    logging.info('Getting app description')
#    
#    try:
#        response_data = {
#            "app_name": os.environ.get("APP_NAME"),
#            "app_version": os.environ.get("APP_VERSION")
#        }
#        
#        return func.HttpResponse(
#            json.dumps(response_data),
#            status_code=200,
#            mimetype="application/json"
#        )
#        
#    except Exception as e:
#        logging.error(f"Error: {str(e)}")
#        return func.HttpResponse(
#            json.dumps({"error": str(e)}),
#            status_code=500,
#            mimetype="application/json"
#        )
#
#def generate_stream_content(request: str, user_id: str, conversation_id: str):
#    try:
#        tokens = []
#        for token in SQLAgent.agent_graph(request, user_id, conversation_id):
#            tokens.append(token)
#        return json.dumps({'content': ''.join(tokens)})
#        #for token in SQLAgent.agent_graph(request, user_id, conversation_id):
#        #    yield json.dumps({'content': token})
#    except Exception as e:
#        return json.dumps({'error': str(e)})
#
#@app.route(route="test2")
#def test2(req: func.HttpRequest) -> func.HttpResponse:
#    logging.info('Processing SQL agent test request')
#    
#    try:
#        req_body = req.get_json()
#        if not req_body:
#            return func.HttpResponse(
#                json.dumps({"error": "Request body is required"}),
#                status_code=400,
#                mimetype="application/json"
#            )
#        
#        required_fields = ['request', 'user_id', 'conversation_id']
#        for field in required_fields:
#            if field not in req_body:
#                return func.HttpResponse(
#                    json.dumps({"error": f"Missing required field: {field}"}),
#                    status_code=400,
#                    mimetype="application/json"
#                )
#        
#        response_content = generate_stream_content(
#            req_body['request'], 
#            req_body['user_id'], 
#            req_body['conversation_id']
#        )
#        
#        #return StreamingResponse(response_content, media_type="text/plain")
#        return func.HttpResponse(
#            response_content,
#            status_code=200,
#            mimetype="text/plain"
#        )
#    
#    except Exception as e:
#        logging.error(f"Error: {str(e)}")
#        return func.HttpResponse(
#            json.dumps({"error": str(e)}),
#            status_code=500,
#            mimetype="application/json"
#        )