import os
import uuid
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def chatbot_ui():
    #Test
    st.title("SQL Demo Chatbot")
    
    api_url = os.environ.get("API_URL")
    
    # Initialize session state variables
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = str(uuid.uuid4())
    if "user_id" not in st.session_state:
        st.session_state.user_id = "user1"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    conversation_id = st.session_state.conversation_id
    user_id = st.session_state.user_id
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    chat_input = st.chat_input("Input your question here")
    if chat_input:
        request_body = {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "request": chat_input
        }
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": chat_input})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(chat_input)
        
        # Get response from API and simulate streaming
        with st.chat_message("assistant"):
            response_container = st.empty()
            
            try:
                # Get complete response first
                response = requests.post(
                    api_url, 
                    json=request_body, 
                    stream=True  # Enable streaming
                )
                response.raise_for_status()

                # Collect streamed content
                full_response = ""

                for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                    if chunk:  # Filter out keep-alive chunks
                        full_response += chunk
                        response_container.markdown(full_response + "|")  # Show cursor

                response_container.markdown(full_response)

                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except requests.exceptions.RequestException as e:
                error_message = f"Error: {str(e)}"
                response_container.markdown(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

if __name__ == "__main__":
    chatbot_ui()