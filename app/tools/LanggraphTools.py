import os
import uuid
import pyodbc
from dotenv import load_dotenv
from datetime import datetime
from langchain_core.tools import tool
from azure.cosmos import CosmosClient, PartitionKey

load_dotenv()

@tool
def query_execution(query):
    """
    This tool is used to run the SQL query against the database.
    This tool is mandatory to be used when the user asks or inputs a question about the data in databases.
    Args:
        query: SQL query string to execute
    return:
        data result from the generated SQL query execution.
    """
    db_url = os.environ.get("SQL_DB_CONNECTION")
    db_connect = pyodbc.connect(db_url, autocommit=True)
    
    cursor = db_connect.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    result_dict = []
    columns = [column[0] for column in cursor.description]
    for row in rows:
        result_dict.append(dict(zip(columns, row)))

    cursor.close()
    db_connect.close()

    return result_dict



class ChatHistory:
    def __init__(self):
        self.cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
        self.cosmos_credential_key = os.environ.get("COSMOS_CREDENTIAL_KEY")
        self.cosmos_consistency_level = os.environ.get("COSMOS_CONSISTENCY_LEVEL")
        self.cosmos_database = os.environ.get("COSMOS_DATABASE")
        self.cosmos_container = os.environ.get("COSMOS_CONTAINER")
        self.cosmos_partition_key = os.environ.get("COSMOS_PARTITION_KEY")

        self.cosmos_client = CosmosClient(
            self.cosmos_endpoint,
            credential=self.cosmos_credential_key,
            consistency_level=self.cosmos_consistency_level
        )
        self.database = self.cosmos_client.create_database_if_not_exists(id=self.cosmos_database)
        self.container = self.database.create_container_if_not_exists(
                    id=self.cosmos_container,
                    partition_key=PartitionKey(path=self.cosmos_partition_key),
                )

    def get_chat_history(self, conversation_id, num_last_message):
        query = f"""
                 select top {num_last_message} *
                 from c
                 where c.conversationid = '{conversation_id}'
                 order by c.timestamp desc
                """

        items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query = True
        ))

        # Reverse the list to show messages in chronological order
        return items[::-1]


    def store_chat(self, user_id, conversation_id, message, role, messageType = "text", metadata = None):

        if metadata is None:
           metadata = {"language": "en", "version": 1}

        message_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        sender_id = user_id if role.lower() == 'user' else 'assistant'
        item = {
            "id": message_id,
            "conversationid": conversation_id,
            "sender_id": sender_id,
            "role": role,
            "timestamp": timestamp,
            "message": message,
            "messageType": messageType,
            "metadata": metadata
        }
        self.container.upsert_item(item)
        return True
