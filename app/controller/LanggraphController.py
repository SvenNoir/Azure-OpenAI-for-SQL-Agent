import os
import pyodbc
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import START, END, StateGraph
from app.schema.LanggraphModel import SQLSchema, State
from app.tools.LanggraphTools import query_execution, ChatHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

load_dotenv()

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
                 3. Always include query used and the database execution result (**MUST IN DATAFRAME**) in output explanation
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

    self.chat_history.store_chat(conversation_id=conversation_id, user_id=state["user_id"], message=request, role="user")

    output_structure = {
        "response": result_execution
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
    result = final_chain.stream({"user_input": user_input, "context": result_execution, "today_date": self.today_date, "chat_history": list_chat_history})

    token_stream = ""
    for token in result:
      token_stream += token
      yield {"response":token_stream}
    
    self.chat_history.store_chat(conversation_id=conversation_id, user_id=state["user_id"], message=token_stream, role="assistant")
    

  def agent_graph(self, question, user_id, conversation_id):
    builder = StateGraph(State)

    builder.add_node("query_agent", self.query_agent)
    builder.add_node("summary_agent", self.summary_agent)

    builder.add_edge(START, "query_agent")
    builder.add_edge("query_agent", "summary_agent")
    builder.add_edge("summary_agent", END)

    graph = builder.compile()

    with open("graph.png", "wb") as f:
      f.write(graph.get_graph().draw_mermaid_png())
    
    run_graph = graph.stream({"question": question, "response": [], "list_chat_history":[], "conversation_id":conversation_id, "user_id":user_id}, stream_mode = "messages")

    for token, metadata in run_graph:
      yield token.content


SQLAgent = LanggraphAgent()