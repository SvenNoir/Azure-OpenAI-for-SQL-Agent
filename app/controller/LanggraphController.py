import os
import json
import pyodbc
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_openai import AzureOpenAIEmbeddings
from langgraph.graph import START, END, StateGraph
from app.schema.LanggraphModel import SQLSchema, State, RouteSchema, AISearchSchema
from app.tools.LanggraphTools import query_execution, ChatHistory
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

load_dotenv()



routing_prompt = """
                  <role>
                  You are an AI-powered "Intelligent Query Router". Your sole purpose is to analyze the user's request and decide which of two specialized agents is best suited to handle it. You do not answer the user's question yourself. Your only output is the name of the correct route in a JSON format.
                  </role>

                  <core_decision_logic>
                  This is the central logic you must follow to make your decision.

                  1.  When to Route to `azure_search_embedding`:
                      Route to this path if the user's question requires: **understanding of concepts, qualitative information, summaries, or finding explanations within unstructured documents.** This route is for questions about the "why" and "how" based on reports, articles, and analyses.

                      Keywords for `azure_search_embedding`: **"why", "what is the reason", "summarize", "explain", "outlook", "review", "consumer profile", "motivation", "impact of", "trend analysis", "report findings", "what does the document say about"**

                  2.  When to Route to `query_agent`:
                      Route to this path if the user's question requires: **retrieval of specific data points, calculations, aggregations (count, sum, average), or filtering a structured dataset based on precise criteria.** This route is for questions that can be answered by querying a database with specific columns like price, year, and brand.

                      Keywords for `query_agent`: **"how many", "list all", "count", "average price", "total sales", "which cars", "show me", "compare", "find cars with...", "what is the most expensive", "cars older than", "cars with mileage less than", "brand", "model_year", "kilometer", "price", "fuel type"**
                  </core_decision_logic>

                  <general_context>
                  1. The user may give you structured or unstructured data, based on its case.
                  2. Today's date is {today_date}.
                  3. Here is the list of the past conversation: {chat_history}
                  </general_context>

                  <instructions>
                  1.  **Analyze Intent:** Carefully read the `<user_input>` and consider the `<chat_history>` to determine the user's primary goal. Are they asking for a factual number from a database, or an explanation from a document?

                  2.  **Apply Core Logic:** Compare the user's intent against the rules and keywords in the `<core_decision_logic>` section.

                  3.  **Prioritize Specificity:** If the user's question mentions specific database fields (e.g., "price", "model_year", "kilometer") or asks for a count/list of items, it **must** be routed to `query_agent`, even if it also contains general terms. The need for a precise, structured data query overrides a general conceptual query.

                  4.  **Final Output:** Your response **MUST** be a single, valid JSON object with this format instructions: {format_instructions}

                      **DO NOT** provide any explanation, preamble, or any text outside of this JSON structure.
                  </instructions>
                 """


prompt_sql = """
              <role>
                You are an AI Assistant of automotive company. You are in charge of creating SQL query in accurate and detail and execute it with the tools provided/binded with you.
                There are some instructions that you have to obey. There are some context of user that might help you to deliver the correct output query.
                Also you will be given some table and its schema, to make the context clearer.
              </role>

              <context>
                1. The user may give ask you in 2 different language (Bahasa and English), Make sure you adapt with the user question.
                2. Todays date is {today_date}.
                3. The columns field in query may contain escape character such as "dummy field", so make sure you use "[]" for every field defined in query.
                4. The user may ask multiple task and deep analysis. Make sure you list the user needs before generating the query.
                5. **MANDATORY** Execute the generated query with tools provided to you.
                6. Chat History: {chat_history}
              </context>

              <table_info>
                <car_sales>
                  This table is used to store the car sales information.
                  <description>
                    [dbo].[car_sales].[id] = A unique numerical identifier for each car listing in the database.
                    [dbo].[car_sales].[name] = A descriptive title for the car listing, typically used for display.
                    [dbo].[car_sales].[price] = The asking price of the vehicle in a local currency.
                    [dbo].[car_sales].[brand] = The manufacturer or brand of the car.
                    [dbo].[car_sales].[model_name] = The specific model name of the car.
                    [dbo].[car_sales].[variant] = The specific trim level, package, or version of the model, which often dictates features.
                    [dbo].[car_sales].[series] = 	A manufacturer-specific code or name for the vehicle's series, generation, or chassis code.
                    [dbo].[car_sales].[model_year] = The year the vehicle was manufactured.
                    [dbo].[car_sales].[kilometer] = The total distance the vehicle has been driven, as shown on the odometer. Measured in kilometers.
                    [dbo].[car_sales].[model_type] = The body style or category of the vehicle.
                    [dbo].[car_sales].[gearbox] = The type of transmission in the vehicle.
                    [dbo].[car_sales].[fuel] = The type of fuel the vehicle's engine requires.
                    [dbo].[car_sales].[status] = The current condition or sales status of the vehicle.
                    [dbo].[car_sales].[cc] = The engine's displacement in cubic centimeters (cc), a measure of engine size.
                    [dbo].[car_sales].[color] = The primary exterior color of the vehicle.
                    [dbo].[car_sales].[seating_capacity] = The total number of seats in the vehicle, including the driver.
                  </description>

                  <notes>
                    [dbo].[car_sales].[id] = Primary Key. This ensures that every row is unique and can be referenced directly.
                    [dbo].[car_sales].[name] = This field appears to be a concatenation of other fields like model_year, brand, model_name, and series.
                    [dbo].[car_sales].[price] = Using decimal is excellent for currency as it prevents floating-point rounding errors. This format supports values up to 99,999,999.99.
                    [dbo].[car_sales].[brand] = e.g., Toyota, Ford, BMW, Honda.
                    [dbo].[car_sales].[model_name] = e.g., Camry, Mustang, X5, Civic.
                    [dbo].[car_sales].[variant] = e.g., GXL, Sport, Titanium, M-Sport.
                    [dbo].[car_sales].[series] = This is often a more technical identifier than the model name.
                    [dbo].[car_sales].[model_year] = While bigint works, a standard int would be sufficient for storing a year.
                    [dbo].[car_sales].[kilometer] = Represents the vehicle's mileage.
                    [dbo].[car_sales].[model_type] = e.g., Sedan, SUV, Hatchback, Ute, Coupe.
                    [dbo].[car_sales].[gearbox] = Common values would be 'Automatic' or 'Manual'.
                    [dbo].[car_sales].[fuel] = e.g., Unleaded Petrol, Diesel, Hybrid, Electric.
                    [dbo].[car_sales].[status] = (Common values: 'Used', 'New', 'Demo').
                    [dbo].[car_sales].[cc] = Common integer value.
                    [dbo].[car_sales].[color] = e.g., Grey, White, Black, Blue.
                    [dbo].[car_sales].[seating_capacity] = Common integer value.
                  </notes>
                </car_sales>
              </table_info>

              <instructions>
                1. Analyze the user input or question carefully, list every variable, field, etc from the user input or question based on the user necessity. You are only going to use Microsoft SQL Server syntax to create the query.
                2. **Handle Multi-Part Questions in a Single Query**: If the user asks multiple questions or requests multiple distinct insights (e.g., using bullet points or numbered lists), you **MUST** generate a single, consolidated SQL query that answers all parts in one execution.
                   - **DO NOT** generate multiple separate SQL queries for a single user request.
                   - The best technique for this is to use **scalar subqueries** in the main `SELECT` list. Each subquery should be designed to answer one of the user's points.
                   - For example: `SELECT (subquery_for_goal_1) AS [Insight1], (subquery_for_goal_2) AS [Insight2], ...`
                2.**Apply Smart Time Aggregation**: Your primary goal is to provide insightful summaries, not raw data dumps. When a user asks for data over a time range, you MUST infer the correct aggregation level.
                   - **If the time range is long (e.g., multiple months, a quarter, a year):** Aggregate the data by a larger time unit (e.g., `MONTH` or `WEEK`). Do NOT return daily or hourly records unless the user explicitly asks for them. For example, a request for "Q1 trend" should be grouped by month.
                   - **If the time range is short (e.g., "last week", "from Monday to Friday"):** Daily aggregation is appropriate.
                   - **Always use an aggregate function** (like `SUM()`, `AVG()`, `COUNT()`) when grouping by a time period.
                3. Create a robust query and make sure the the syntax of the query is not returning error. Make sure all fields in query using '[]' to evade syntax error.
                4. Make sure every field in the generated query is listed in the table schema above and mapped into its correct table.
                5. Make sure each column name in generated query using format "[database_name].[table_name].[column_name]" to evade incorrect syntax.
                6. If the generated query is not using mathematically aggregate function such as "sum", "avg", etc then add distinct logic into the query.
                7. Parse the output into this JSON format with query only based on this format instructions: {format_instructions}.
              </instructions>

              <reflection>
                1. Carefully review the generated query, make sure the query follows the Microsoft SQL Server syntax and match the user request.
                2. If a subquery is used in the SELECT clause, ensure it returns only one column. If multiple values are needed from that subquery, either format them into a string or refactor the logic using CROSS JOIN or APPLY.
                3. Make sure each column name in generated query using format "[database_name].[table_name].[column_name]" to evade incorrect syntax.
                4. When using subqueries in SELECT or with comparison operators, ensure they return only one value, and if multiple values are possible, use TOP 1, STRING_AGG, or restructure the query with JOIN or APPLY to avoid scalar subquery errors.
                5. Make sure you use the tools provided to execute the generated query.
                6. **Check for appropriate aggregation.** Have I aggregated the data to a reasonable time unit (e.g., monthly for a quarterly trend) to avoid returning an excessive number of rows? Or did the user specifically ask for daily-level detail?
                7. **Check for Query Consolidation.** If the user's request contained multiple parts or bullet points, did I successfully combine them into a single query? Or did I incorrectly generate multiple queries? I must use techniques like scalar subqueries to produce a single, efficient query.
              </reflection>
             """

ai_search_prompt = """
                    <role>
                    You are a highly intelligent and meticulous AI assistant named 'Insight'. Your primary function is to analyze provided context and answer user questions with precision and clarity.

                    Your core principles are:
                    1.  **Truthfulness:** You MUST base your answers exclusively on the information within the `<supporting_context>` section. Do not use any prior knowledge or external information.
                    2.  **Clarity:** You must present information in a clear, well-structured, and easy-to-understand manner.
                    3.  **Honesty about Limitations:** If the answer is not present in the context, you must state that clearly and directly. Do not speculate or invent information.
                    </role>

                    <general_context>
                    1. The user may give you structured or unstructured data, based on its case.
                    2. Today's date is {today_date}.
                    3. Here is the list of the past conversation: {chat_history}.
                    4. The user's access level is: {user_access_level}.
                    </general_context>

                    <supporting_context>
                    {retrieved_context}
                    </supporting_context>

                    <instructions>
                    Follow these steps meticulously to formulate your response:

                    1.  **Analyze the User's Intent:**
                        *   Carefully read the `<user_input>` and review the `<chat_history>` to fully understand the user's specific question, its nuances, and the context of their inquiry.
                        *   Identify the key entities, concepts, and the core information they are seeking.

                    2.  **Scrutinize the Supporting Context:**
                        *   Thoroughly review all the text, data, and descriptions within the `<supporting_context>`. This is your ONLY source of truth.
                        *   Identify all relevant passages, figures, and data points that directly or indirectly address the user's intent.

                    3.  **Synthesize a Direct and Comprehensive Answer:**
                        *   Begin your response by directly addressing the user's primary question.
                        *   Synthesize information from multiple parts of the context if necessary. Do not just list disconnected snippets; weave them into a coherent and logical narrative.
                        *   When quoting numbers, percentages, specific names (e.g., 'Toyota Avanza'), or key phrases, ensure they are exactly as they appear in the context to maintain accuracy.
                        *   Maintain a helpful, neutral, and professional tone.

                    4.  **Handle Insufficient Information:**
                        *   If the `<supporting_context>` does not contain the information needed to answer the user's question, you MUST explicitly state that.
                        *   Use clear and unambiguous phrases like, "Based on the provided information, I cannot find details about..." or "The documents do not contain specific data on..."
                        *   Do not apologize for the lack of information. Simply state the fact.

                    5.  **Format the Output for Readability:**
                        *   Use clear paragraphs to separate ideas.
                        *   Use bullet points or numbered lists when presenting lists of items, steps, or key findings (e.g., top car models, reasons for buying). This makes the information scannable and easy to digest.
                        *   Use **bold** formatting to highlight the most critical pieces of information, such as key conclusions, figures, or answers to direct questions.

                    6.  **Provide Citations (Crucial for Trust):**
                        *   If the retrieved context includes metadata like page numbers or section titles, cite the source of your information. This builds user trust and allows for verification.
                        *   For example, if you state that the top reason for buying a car is to upgrade, you might add `[Source: Page 5, Profil Konsumen 2021]`.
                        *   If the context is a single block of text without metadata, you do not need to add a citation. The goal is to link the answer back to the evidence whenever possible.
                    
                    7. **Parse The Output**
                        *   The last step is to parse the output into this format instructions: {format_instructions}
                    </instructions>
                   """


summary_prompt = """
                 <role>
                 You are an AI assistant who has a task to rephrase the previous LLM output into comprehensive and detailed explanation.
                 There are some instructions that you have to obey. There are some context of user that might help you to deliver the correct output query.
                 </role>

                 <general_context>
                 1. The user may give you structured or unstructured data, based on its case.
                 2. Today's date is {today_date}.
                 3. Here is the list of the past conversation: {chat_history}
                 </general_context>

                 <supporting_context>
                 {context}
                 </supporting_context>

                 <instructions>
                 1. Analyze the user input in detail, you have to find the pattern between user input and the database execution result (including query used) in <supporting_context> material.
                 2. Construct the corresponding relation or pattern and rephrase it into explanation in detail and comprehensive.
                 3. **IF THE QUERY AND DATABASE EXECUTION RESULT ARE AVAILABLE**, always include query used and the database execution result (**MUST IN DATAFRAME**) in output explanation.
                    **IF THE QUERY AND DATABASE EXECUTION RESULT ARE NOT AVAILABLE** do not include them in the output!
                 </instructions>

                 <user_input>
                 {user_input}
                 </user_input>
                 """

class LanggraphAgent:
  def __init__(self):
      self.today_date = datetime.now().strftime("%Y-%m-%d")
      self.llm = AzureChatOpenAI(
          azure_endpoint = os.environ.get("AZURE_ENDPOINT"),
          azure_deployment = os.environ.get("AZURE_DEPLOYMENT"),
          openai_api_version = os.environ.get("AZURE_OPENAI_API_VERSION"),
          api_key = os.environ.get("AZURE_OPENAI_API_KEY"),
          temperature = 0
      )
      self.llm_with_tool = self.llm.bind_tools([query_execution])
      self.chat_history = ChatHistory()

  def route_fixing(self, state: State):
      if state["response"]["status"] ==  "success":
        return "summary"
      else:
        return "fixing_query"
  def choose_route(self, state: State):
      if state["response"]["route"] ==  "query_agent":
        return "query_agent"
      elif state["response"]["route"] ==  "azure_search_embedding":
        return "azure_search_embedding"

  def vector_search(self, state:State):
    query = state["question"]
    access_level_filter = state["access_level"]
    
    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.environ.get("AZURE_OPENAI_MODEL_NAME"),
        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.environ.get("AZURE_OPENAI_MODEL_DEPLOYMENT_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_KEY"),
    )
    search_vector = embeddings.embed_query(query)

    search_client = SearchClient(
      endpoint=os.environ.get("AZURE_SEARCH_ENDPOINT"),
      index_name="postman-test",
      credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_KEY"))
      )

    # Perform the hybrid search
    search_results = search_client.search(
          search_text=query, 
          top=3,
          select="content, image_path, title",
          vector_queries=[
              VectorizedQuery(
                  vector=search_vector, 
                  k_nearest_neighbors=20, 
                  fields="text_vector"
              )
          ],
          filter= f"min_access_level le {access_level_filter} and max_access_level ge {access_level_filter}"
      )
    
    list_retrieved_data = []
    for result in search_results:
        retrieved_item = {
            "content": result.get("content"),
            "image_path": result.get("image_path"),
            "title": result.get("title")
        }
        list_retrieved_data.append(retrieved_item)

    output_structure = {
        "data": list_retrieved_data
    }

    return output_structure
  


  def route_agent(self, state: State):
    conversation_id = state["conversation_id"]
    list_chat_history = self.chat_history.get_chat_history(conversation_id, 6)
    request = state["question"]
    user_input = HumanMessage(content=request)

    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", routing_prompt),
            ("user", "<user_input>\n{user_input}\n</user_input>")
        ]
    )

    parser = JsonOutputParser(pydantic_object=RouteSchema)
    final_chain = chat_prompt | self.llm
    result = final_chain.invoke(
       {
          "user_input": [user_input], 
          "today_date": self.today_date, 
          "format_instructions": parser.get_format_instructions(), 
          "chat_history": list_chat_history,
       }
    )

    #print("route_agent result:", result.content)

    self.chat_history.store_chat(conversation_id=conversation_id, user_id=state["user_id"], message=request, role="user")

    output_structure = {
        "response": json.loads(result.content.replace("```json", "").replace("```", ""))
    }
    return output_structure


  def query_agent(self, state: State):
    conversation_id = state["conversation_id"]
    list_chat_history = self.chat_history.get_chat_history(conversation_id, 6)
    request = state["question"]
    user_input = HumanMessage(content=request)
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", prompt_sql),
            MessagesPlaceholder("input")
        ]
    )

    parser = JsonOutputParser(pydantic_object = SQLSchema)
    final_chain = chat_prompt | self.llm_with_tool
    result = final_chain.invoke({"input": [user_input], "today_date": self.today_date, "format_instructions": parser.get_format_instructions(), "chat_history": list_chat_history})

    for i, tool_name in enumerate(result.tool_calls):
      result_execution = query_execution.invoke(tool_name['args'])

    #self.chat_history.store_chat(conversation_id=conversation_id, user_id=state["user_id"], message=request, role="user")

    output_structure = {
        "response": result_execution
    }
    return output_structure
  
  def ai_search_agent(self, state: State):
    conversation_id = state["conversation_id"]
    list_chat_history = self.chat_history.get_chat_history(conversation_id, 6)
    question = state["question"]
    access_level = state["access_level"]
    
    retrieved_docs = self.vector_search(state)["data"]

    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ai_search_prompt),
            MessagesPlaceholder(variable_name="user_message_with_image")
        ]
    )

    multimodal_content = [{"type": "text", "text": question}]
    
    image_url_to_add = None

    if retrieved_docs and isinstance(retrieved_docs, list):
        for doc in retrieved_docs:

            if isinstance(doc, dict) and doc.get("image_path"):
                image_url_to_add = doc["image_path"]
                print(f"Found image to include: {image_url_to_add}")
                break


    if image_url_to_add:
        multimodal_content.insert(0, {
            "type": "image_url",
            "image_url": {"url": image_url_to_add}
        })

    final_user_message = HumanMessage(content=multimodal_content)
    

    parser = JsonOutputParser(pydantic_object = AISearchSchema)
    final_chain = chat_prompt | self.llm
    
    result = final_chain.invoke(
       {
          "user_message_with_image": [final_user_message],
          "today_date": self.today_date, 
          "format_instructions": parser.get_format_instructions(), 
          "chat_history": list_chat_history, 
          "retrieved_context": retrieved_docs,
          "user_access_level": access_level
       }
    )
    

    output_structure = {
        "response": result
    }
    return output_structure


  def summary_agent(self, state: State):
    conversation_id = state["conversation_id"]
    list_chat_history = self.chat_history.get_chat_history(conversation_id, 6)
    request = state["question"]
    user_input = HumanMessage(content=request)
    result_execution = state["response"]
    print(result_execution)
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", summary_prompt),
            ("human", "{user_input}")
        ]
    )

    final_chain = chat_prompt | self.llm | StrOutputParser()
    #result = final_chain.invoke({"user_input": user_input, "context": result_execution, "today_date": self.today_date})
    result = final_chain.stream(
       {
          "user_input": user_input, 
          "context": result_execution, 
          "today_date": self.today_date, 
          "chat_history": list_chat_history
       }
    )

    token_stream = ""
    for token in result:
      token_stream += token
      yield {"response":token_stream}
    
    self.chat_history.store_chat(conversation_id=conversation_id, user_id=state["user_id"], message=token_stream, role="assistant")
    

  def agent_graph(self, question, user_id, conversation_id, access_level):
    builder = StateGraph(State)

    builder.add_node("route_agent", self.route_agent)
    builder.add_node("query_agent", self.query_agent)
    builder.add_node("azure_search_embedding", self.ai_search_agent)
    builder.add_node("summary_agent", self.summary_agent)

    builder.add_edge(START, "route_agent")
    builder.add_conditional_edges(
       "route_agent",
       self.choose_route,
       {
          "query_agent": "query_agent",
          "azure_search_embedding": "azure_search_embedding"
       }
    )
    builder.add_edge("azure_search_embedding", "summary_agent")
    builder.add_edge("query_agent", "summary_agent")
    builder.add_edge("summary_agent", END)

    graph = builder.compile()

    #with open("graph.png", "wb") as f:
    #  f.write(graph.get_graph().draw_mermaid_png())
    
    run_graph = graph.stream(
       {
          "question": question, 
          "response": [], 
          "list_chat_history":[], 
          "conversation_id":conversation_id, 
          "user_id":user_id,
          "access_level": access_level
       },
       stream_mode = "messages"
    )

    for token, metadata in run_graph:
      print(token.content)
      yield token.content


SQLAgent = LanggraphAgent()