import os
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_ollama import OllamaLLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_text_splitters import RecursiveCharacterTextSplitter
import shutil

app = FastAPI()

# Configuration
OLLAMA_MODEL = "llama3.2:1b"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text:v1.5"
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BACKEND_DIR, "chroma_db")
DATA_DIR = os.path.join(BACKEND_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Vector Store and LLM
embeddings = OllamaEmbeddings(model=OLLAMA_EMBEDDING_MODEL)
vector_store = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
llm = OllamaLLM(model=OLLAMA_MODEL)

def format_documents(documents):
    return "\n\n".join(document.page_content for document in documents)


qa_prompt = PromptTemplate.from_template(
    "Answer the question using only the following context. "
    "If the context does not contain the answer, say you do not know.\n\n"
    "Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
)
qa_chain = (
    {
        "context": vector_store.as_retriever() | RunnableLambda(format_documents),
        "question": RunnablePassthrough(),
    }
    | qa_prompt
    | llm
    | StrOutputParser()
)

class QueryRequest(BaseModel):
    query: str


@app.get("/")
async def root():
    return {
        "message": "RAGbook API is running.",
        "upload_endpoint": "POST /upload",
        "query_endpoint": "POST /query",
        "docs": "/docs",
    }


@app.post(
    "/upload",
    summary="Upload a PDF document",
    description="Upload a PDF file (max 10MB). Only PDF files are supported."
)
async def upload_document(
    file: UploadFile = File(
        ...,
        description="PDF file to upload. Only '.pdf' files are supported. Max size: 10MB."
    )
):
    try:
        # Save file to disk
        file_path = os.path.join(DATA_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")

        # Read PDF
        try:
            reader = PdfReader(file_path)
            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    os.remove(file_path)
                    raise HTTPException(status_code=400, detail="PDF is encrypted and cannot be processed.")
        except Exception as e:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(e)}")

        documents = [
            Document(
                page_content=page.extract_text() or "",
                metadata={"source": file_path, "page": page_number},
            )
            for page_number, page in enumerate(reader.pages)
            if (page.extract_text() or "").strip()
        ]
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)
        # Add to vector store
        vector_store.add_documents(texts)
        vector_store.persist(texts) # Last change: add "text" in ()
       

        return {"message": f"Successfully uploaded and indexed {file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_rag(request: QueryRequest):
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, qa_chain.invoke, request.query)
        return {"answer": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# For development only. For production, use a command like:
# gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
