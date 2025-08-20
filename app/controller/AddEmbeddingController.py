# --- Make sure to add this new import at the top of your file ---
from azure.storage.blob import BlobServiceClient

# ... (keep all your other existing imports)
import io
import os
import json
import uuid
import fitz
import base64
import markdown
from PIL import Image
from datetime import datetime
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from langchain_openai import AzureOpenAIEmbeddings
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader
from azure.search.documents.indexes.models import (
    FreshnessScoringFunction,
    FreshnessScoringParameters,
    ScoringProfile,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    TextWeights,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
)
from pydantic import BaseModel, Field
from typing import List, Annotated, Union
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

load_dotenv()

# --- (Your prompts remain unchanged) ---
prompt_image = """
               You are an AI assistant responsible for classifying documents for indexing. Your task is to decide whether a document should be indexed as text or as an image based on its content.

               ### **Decision Criteria:**
               1. **Index as Text**:
               - The document primarily consists of **readable text** that can be extracted via OCR with **high accuracy**.
               - The majority of information is in a **structured format** such as paragraphs, tables, or lists.
               - Diagrams or images, if present, **do not** carry critical information and still can be explained with only text. (e.g. A step by step image with descriptive caption below/next it.)

               2. **Index as Image**:
               - The document is **mostly diagrams, graphs (especially pie charts), or images** that contain essential information that **cannot be easily converted into text**.
               - The text is embedded within complex visuals where OCR extraction may **fail** or lose context.
               - The meaning of the document is **primarily conveyed through its visual elements**, such as engineering schematics, architectural blueprints, or heavily annotated flowcharts.

               ### **Output Format:**
               Return the output with json format and please use this formatting guide: {format_instructions}
               Fill the `description` with this instructions:
                - If the document should be indexed as text, respond with a description that highlights its textual content and structure.
                - If the document should be indexed as an image, respond with a description that emphasizes its visual elements and complexity.

               Fill the `type_index` with this instructions:
                - If the document should be indexed as text, respond with: "Index as Text".
                - If the document should be indexed as an image, respond with: "Index as Image".

               ### **Example Cases:**
               1. **A scanned contract document with clear paragraphs →** "Index as Text"
               2. **A flowchart describing a business process that will lose context with only OCR extraction →** "Index as Image"
               """

# New prompt for image description/summarization
prompt_image_description = """
You are an AI assistant that creates detailed descriptions of images for embedding and retrieval purposes.

Your task is to analyze the provided image and create a comprehensive textual description that captures:
1. **Visual Elements**: Charts, graphs, diagrams, workflows, processes, etc.
2. **Data Insights**: Key findings, trends, or information presented
3. **Structure**: How information is organized or flows
4. **Context**: What the image is trying to communicate or demonstrate

The description should be detailed enough that someone could understand the key information without seeing the image, but concise enough for effective embedding and retrieval.

### **Output Format:**
Provide a detailed paragraph description of the image content.
"""


class EmbeddingProces:
    def __init__(self):
        # Good practice to initialize clients once if possible, but your current approach is fine.
        pass

    # --- NEW METHOD to handle uploading images to Blob Storage ---
    def upload_image_to_blob(self, base64_image_data, original_file_name, page_number):
        """Uploads a base64 encoded image to Azure Blob Storage and returns the URL."""
        try:
            # Assumes you have these in your env_setting.py
            connection_string = os.environ.get("BLOB_CONNECTION_STRING2")
            container_name = os.environ.get("CONTAINER_NAME")

            if not connection_string or not container_name:
                raise ValueError("Azure Storage connection string and container name must be configured.")

            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            
            # Create a unique name for the blob to avoid collisions
            file_basename = os.path.splitext(original_file_name)[0]
            blob_name = f"{file_basename}_page_{page_number}_{uuid.uuid4()}.png"
            
            # Decode the base64 string into bytes
            image_bytes = base64.b64decode(base64_image_data)
            
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
            
            # Upload the image bytes
            blob_client.upload_blob(image_bytes, blob_type="BlockBlob", overwrite=True)
            
            print(f"Successfully uploaded image for page {page_number} to: {blob_client.url}")
            return blob_client.url

        except Exception as e:
            print(f"ERROR: Failed to upload image for page {page_number} to blob storage. {e}")
            return None

    def az_docint(self, file_path):
        # This method remains unchanged
        loader = AzureAIDocumentIntelligenceLoader(
            api_endpoint=os.getenv("DOC_INT_ENDPOINT"),
            api_key=os.getenv("DOC_INT_API_KEY"),
            url_path=file_path,
            api_model=os.getenv("DOC_INT_API_MODEL"),
            analysis_features=["ocrHighResolution"],
        )
        documents = loader.load()
        markdown_result = markdown.markdown(documents[0].page_content, extensions=["tables"])
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_text(markdown_result)
        embeddings = AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_MODEL_NAME"),
            openai_api_version=os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
        )
        embedding_function = embeddings.embed_query
        sample_embedding = embedding_function("Sample text")
        embedding_dimension = len(sample_embedding)
        return texts, embedding_dimension, embeddings
        
    def create_index(self, embedding_dimension, index_name):
        # This method remains unchanged. 'image_path' as String is correct for a URL.
        vector_search = VectorSearch(
            profiles=[VectorSearchProfile(name="myHnswProfile", algorithm_configuration_name="myHnsw")],
            algorithms=[HnswAlgorithmConfiguration(name="myHnsw", parameters={"m":4, "efConstruction":400, "efSearch":500, "metric":"cosine"})]
        )
        semantic_config = SemanticConfiguration(
            name = "my-semantic-config",
            prioritized_fields = SemanticPrioritizedFields(title_field = SemanticField(field_name="title"), content_fields = [SemanticField(field_name="content")])
        )
        semantic_search = SemanticSearch(configurations=[semantic_config])
        fields = [
            SearchField(name="chunk_id", type=SearchFieldDataType.String, retrievable=True, searchable=True, sortable=True, facetable=False, key=True, filterable=True, analyzer_name="keyword"),
            SearchField(name="parent_id", type=SearchFieldDataType.String, retrievable=True, searchable=False, sortable=True, filterable=True, facetable=False),
            SearchField(name="content", type=SearchFieldDataType.String, retrievable=True, searchable=True, index_analyzer_name="keyword", search_analyzer_name="standard"),
            SearchField(name="title", type=SearchFieldDataType.String, retrievable=True, searchable=True, index_analyzer_name="keyword", search_analyzer_name="standard"),
            SearchField(name="min_access_level", type=SearchFieldDataType.Int32, retrievable=True, searchable=False),
            SearchField(name="max_access_level", type=SearchFieldDataType.Int32, retrievable=True, searchable=False),
            SearchField(name="image_path", type=SearchFieldDataType.String, retrievable=True, searchable=True, index_analyzer_name="keyword", search_analyzer_name="standard"),
            SearchField(name="text_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=embedding_dimension, vector_search_profile_name="myHnswProfile", searchable=True),
        ]
        search_client = SearchIndexClient(endpoint = os.getenv("AZURE_SEARCH_ENDPOINT"), credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")))
        search_index = SearchIndex(name = index_name, fields = fields, vector_search = vector_search, semantic_search = semantic_search)
        result = search_client.create_or_update_index(search_index)
        return result

    def get_embeddings_instance(self):
        # This method remains unchanged
        return AzureOpenAIEmbeddings(
            azure_deployment=os.getenv("AZURE_OPENAI_MODEL_NAME"),
            openai_api_version=os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
        )

    def get_llm_instance(self):
        # This method remains unchanged
        return AzureChatOpenAI(
          azure_endpoint = os.getenv("AZURE_ENDPOINT"),
          azure_deployment = os.getenv("AZURE_DEPLOYMENT"),
          openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION"),
          api_key = os.getenv("AZURE_OPENAI_API_KEY"),
          temperature = 0
        )

    def image_indexing_decider(self, base64_image):
        # This method remains unchanged
        llm = self.get_llm_instance()
        class ImageSchema(BaseModel):
            description: str = Field(..., description="Description that contain the gist of the current task")
            type_index: str = Field(..., description="Type of the output")
        human_message = HumanMessage(content=[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}])
        chat_prompt = ChatPromptTemplate.from_messages([("system", prompt_image), MessagesPlaceholder("input")])
        parser = JsonOutputParser(pydantic_object=ImageSchema)
        chain = chat_prompt | llm
        result = chain.invoke({"input": [human_message], "format_instructions": parser.get_format_instructions()})
        result_content = result.content.replace("```json", "").replace("```", "")
        return json.loads(result_content)

    def describe_image(self, base64_image):
        # This method remains unchanged
        llm = self.get_llm_instance()
        human_message = HumanMessage(content=[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}])
        chat_prompt = ChatPromptTemplate.from_messages([("system", prompt_image_description), MessagesPlaceholder("input")])
        chain = chat_prompt | llm | StrOutputParser()
        description = chain.invoke({"input": [human_message]})
        return description

    def process_pdf_pages_multimodal(self, file_bytes: bytes, original_filename: str):
        processed_pages = []
        # Key change: open from a byte stream, not a file path
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page_count = len(doc)
        for i in range(page_count):
            page = doc.load_page(i)
            page_text = page.get_text()
            zoom = 1.5
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            output = io.BytesIO()
            img.save(output, format="PNG")
            output.seek(0)
            image_base64 = base64.b64encode(output.getvalue()).decode("utf-8")
            decision = self.image_indexing_decider(image_base64)
            page_data = {
                "page_number": i + 1, "text_content": page_text, "image_base64": image_base64,
                "index_decision": decision, "original_filename": original_filename
            }
            processed_pages.append(page_data)
        doc.close()
        return processed_pages

    # --- FIXED: Re-added the 'else' to fix the logic bug ---
    def create_multimodal_chunks(self, processed_pages):
        chunks_to_upload = []
        embeddings = self.get_embeddings_instance()
        
        for page_data in processed_pages:
            decision = page_data["index_decision"]
            page_num = page_data["page_number"]
            original_filename = page_data["original_filename"]
            
            if decision["type_index"] == "Index as Text":
                print(f"Page {page_num}: Processing as text")
                text_content = page_data["text_content"]
                if text_content.strip():
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                    text_chunks = text_splitter.split_text(text_content)
                    for i, chunk in enumerate(text_chunks):
                        chunk_embedding = embeddings.embed_query(chunk)
                        doc = {
                            "chunk_id": str(uuid.uuid4()), "parent_id": str(uuid.uuid4()), "content": chunk,
                            "title": f"{original_filename} - Page {page_num} - Text Chunk {i+1}",
                            "image_path": None, "min_access_level": 10, "max_access_level": 62,
                            "text_vector": chunk_embedding,
                        }
                        chunks_to_upload.append(doc)
            # This 'else' is CRITICAL. It was missing.
            else: 
                print(f"Page {page_num}: Processing as image")
                image_url = self.upload_image_to_blob(
                    page_data["image_base64"], original_filename, page_num
                )
                if not image_url:
                    print(f"Skipping page {page_num} because image upload failed.")
                    continue
                description = self.describe_image(page_data["image_base64"])
                desc_embedding = embeddings.embed_query(description)
                doc = {
                    "chunk_id": str(uuid.uuid4()), "parent_id": str(uuid.uuid4()), "content": description,
                    "title": f"{original_filename} - Page {page_num} - Visual Content",
                    "image_path": image_url, "min_access_level": 10, "max_access_level": 62,
                    "text_vector": desc_embedding,
                }
                chunks_to_upload.append(doc)
        
        return chunks_to_upload
    # --- END OF MODIFIED SECTION ---

    def upload_to_index(self, index_name, texts, embeddings, file_path):
        # This method remains unchanged
        documents_to_upload = []
        for i, text_chunk in enumerate(texts):
            chunk_embedding = embeddings.embed_query(text_chunk)
            doc = {
                "chunk_id": str(uuid.uuid4()), "parent_id": str(uuid.uuid4()), "content": text_chunk,
                "title": f"{file_path}", "image_path": None, "min_access_level": 20, "max_access_level": 62,
                "text_vector": chunk_embedding,
            }
            documents_to_upload.append(doc)
        search_documents_client = SearchClient(endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"), index_name=index_name, credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")))
        upload_embeddings = search_documents_client.upload_documents(documents=documents_to_upload)
        return upload_embeddings

    def upload_multimodal_chunks(self, index_name, chunks):
        # This method remains unchanged
        search_documents_client = SearchClient(endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"), index_name=index_name, credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY")))
        upload_result = search_documents_client.upload_documents(documents=chunks)
        return upload_result

    def flow_multimodal_append_from_bytes(self, file_bytes: bytes, original_filename: str, index_name: str):
        try:
            print(f"Processing PDF with multimodal approach: {original_filename}")
            processed_pages = self.process_pdf_pages_multimodal(file_bytes, original_filename)
            print(f"Processed {len(processed_pages)} pages")
            chunks = self.create_multimodal_chunks(processed_pages)
            print(f"Created {len(chunks)} chunks")
            upload_result = self.upload_multimodal_chunks(index_name, chunks)
            print(f"Successfully uploaded chunks to {index_name}")
            return {
                "status": "success",
                "message": f"Successfully added multimodal content from {original_filename}",
                "pages_processed": len(processed_pages), "chunks_created": len(chunks),
                "text_chunks": len([c for c in chunks if c["image_path"] is None]),
                "image_chunks": len([c for c in chunks if c["image_path"] is not None]),
            }
        except Exception as e:
            print(f"Error in multimodal flow: {str(e)}")
            return {"status": "error", "message": f"Error: {str(e)}"}

    def flow(self, file_path, index_name):
        # This method remains unchanged
        try:
            texts, embedding_dimension, embeddings = self.az_docint(file_path)
            creating_index = self.create_index(embedding_dimension, index_name)
            upload_to_index = self.upload_to_index(index_name, texts, embeddings, file_path)
            return {"data": f"Creating index and embedding successful in {index_name}"}
        except Exception as e:
            print(f"error: {str(e)}")
            return {"data": f"error:{str(e)}"}


# Your usage example remains the same
AHMEmbeddingController = EmbeddingProces()
result = AHMEmbeddingController.flow_multimodal_append_from_bytes("Company Paid Leave Policy.pdf", "postman-test")