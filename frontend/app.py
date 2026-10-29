import streamlit as st
import requests

st.set_page_config(page_title="RAGbook", page_icon="🤖")

st.title("🤖 RAGbook")
st.markdown("Upload a PDF and ask questions about it")

import os

BACKEND_URL = (
    st.secrets.get("BACKEND_URL")
    or os.environ.get("BACKEND_URL")
    or "http://localhost:8000"
)

# Sidebar for uploading documents
with st.sidebar:
    st.header("Documents")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded_file:
        if st.button("Upload document"):
            with st.spinner("uploading..."):
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                try:
                    response = requests.post(f"{BACKEND_URL}/upload", files=files)
                    if response.status_code == 200:
                        st.success("Document uploaded successfully!")
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

# Chat interface
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/query", 
                    json={"query": prompt}
                )
                if response.status_code == 200:
                    answer = response.json().get("answer")
                    if not isinstance(answer, str) or not answer.strip():
                        answer = "Sorry, I couldn't find an answer to your question. Please try rephrasing or uploading a different document."
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error(f"Error: {response.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")
