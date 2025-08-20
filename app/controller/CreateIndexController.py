import os
import dotenv

from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials import AzureKeyCredential

from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    #AzureOpenAIParameters,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchIndex,
    VectorSearchAlgorithmKind,
    HnswParameters
)

dotenv.load_dotenv()

class CreateIndex:
    def __init__(self):
        azure_search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        azure_search_key = os.getenv("AZURE_SEARCH_KEY")
        self.azure_openai_model_dimensions = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS"))

        self.azure_credential = AzureKeyCredential(str(azure_search_key))
        self.index_client = SearchIndexClient(endpoint=azure_search_endpoint, credential= self.azure_credential)

    def create_index(self, index_name):
        try:
            fields = [  
                SearchField(name="chunk_id", type=SearchFieldDataType.String, retrievable=True, searchable=True, sortable=True, filterable=True, facetable=False, key=True, analyzer_name='keyword'),  
                SearchField(name="parent_id", type=SearchFieldDataType.String, retrievable=True, searchable=False, sortable=True, filterable=True, facetable=False),  
                SearchField(name="content", type=SearchFieldDataType.String, retrievable=True, searchable=True, index_analyzer_name="keyword", search_analyzer_name="standard"),  
                SearchField(name="title", type=SearchFieldDataType.String, retrievable=True, searchable=True, index_analyzer_name="keyword", search_analyzer_name="standard"), 
                SearchField(name="min_access_level", type=SearchFieldDataType.Int32, retrievable=True, searchable=False, filterable=True),
                SearchField(name="max_access_level", type=SearchFieldDataType.Int32, retrievable=True, searchable=False, filterable=True),
                SearchField(name="image_path", type=SearchFieldDataType.String, retrievable=True, searchable=True, index_analyzer_name="keyword", search_analyzer_name="standard"),  
                SearchField(name="text_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=self.azure_openai_model_dimensions, vector_search_profile_name="myHnswProfile", searchable=True),
            ]

            # Configure the vector search configuration
            # This can also be done via the Azure portal
            vector_search = VectorSearch(
                        profiles=[
                            VectorSearchProfile(name="myHnswProfile",
                            algorithm_configuration_name="myHnsw",)
                        ],
                        algorithms=[
                            HnswAlgorithmConfiguration(
                                name="myHnsw",
                                parameters={
                                    "m":4,
                                    "efConstruction":400,
                                    "efSearch":500,
                                    "metric":"cosine"
                                }
                            )
                        ]
                    )

            semantic_config = SemanticConfiguration(  
                name="my-semantic-config",  
                prioritized_fields=SemanticPrioritizedFields(  
                    content_fields=[SemanticField(field_name="title")]  
                ),  
            )

            # Create the semantic search with the configuration  
            semantic_search = SemanticSearch(configurations=[semantic_config])  

            # Create the search index
            index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search, semantic_search=semantic_search)  
            result = self.index_client.create_or_update_index(index)
            print(f"{result.name} created")
            
            return f"Index {result.name} created successfully."
       
        except Exception as e:
            return f"Error creating index: {str(e)}"
        

AHMCreateIndexController = CreateIndex()