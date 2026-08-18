import os
import re
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import pymupdf4llm
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters, FilterOperator
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.groq import Groq
from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from dotenv import load_dotenv

load_dotenv()

# Setup Qdrant Client (Local Disk)
qdrant_client = QdrantClient(path="./qdrant_data")
collection_name = "not_notebooklm"

if not qdrant_client.collection_exists(collection_name):
    # Dummy check, LlamaIndex handles dynamic creation during first insert
    pass

vector_store = QdrantVectorStore(client=qdrant_client, collection_name=collection_name)

# Configure LLM and Embeddings based on .env
llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()

if llm_provider == "groq":
    Settings.llm = Groq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))
    Settings.embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=os.getenv("GEMINI_API_KEY"))
else:
    Settings.llm = Gemini(model="models/gemini-flash-latest", api_key=os.getenv("GEMINI_API_KEY"))
    Settings.embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=os.getenv("GEMINI_API_KEY"))


def ingest_document_text(text: str, filename: str, chat_id: str):
    """Ingests raw text into the vector database under a specific chat_id."""
    doc = Document(
        text=text,
        metadata={"chat_id": chat_id, "source_type": "file", "filename": filename}
    )
    VectorStoreIndex.from_documents([doc], vector_store=vector_store, show_progress=True)
    return True

def ingest_document(file_path: str, chat_id: str):
    """Parses a PDF/File and ingests it."""
    md_text = pymupdf4llm.to_markdown(file_path)
    filename = os.path.basename(file_path)
    return ingest_document_text(md_text, filename, chat_id)

def web_search_and_ingest(query: str, chat_id: str) -> str:
    """
    Searches the web for a query, scrapes the top 2 articles, 
    ingests them into the RAG database for this chat_id, and returns a summary.
    """
    print(f"[Agent] Searching the web for: {query}")
    results = DDGS().text(query, max_results=2)
    if not results:
        return f"No results found on the web for '{query}'."
    
    ingested_urls = []
    for res in results:
        url = res['href']
        try:
            # Scrape content
            page = requests.get(url, timeout=5)
            soup = BeautifulSoup(page.content, 'html.parser')
            # Extract readable text (very basic scraping)
            paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3'])
            text = "\n".join([p.get_text() for p in paragraphs])
            
            if len(text.strip()) > 100:
                # Ingest to Qdrant
                doc = Document(
                    text=f"Source URL: {url}\n\n{text}",
                    metadata={"chat_id": chat_id, "source_type": "web", "url": url}
                )
                VectorStoreIndex.from_documents([doc], vector_store=vector_store)
                ingested_urls.append(url)
        except Exception as e:
            print(f"[Agent] Failed to scrape {url}: {e}")
            continue
            
    if ingested_urls:
        return f"Successfully searched the web and saved information from: {', '.join(ingested_urls)}. The user can now ask questions about this new information."
    else:
        return "Searched the web but couldn't extract useful text from the results."


def fetch_and_ingest_doi(doi: str, chat_id: str) -> str:
    """
    Uses OpenAlex API to find an Open Access PDF for a given DOI,
    downloads it, and ingests it into Qdrant.
    """
    print(f"[Agent] Fetching DOI: {doi}")
    
    # Clean DOI string just in case
    match = re.search(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+', doi, re.I)
    if not match:
        return f"Invalid DOI format: {doi}"
    clean_doi = match.group(0)
    
    api_url = f"https://api.openalex.org/works/doi:{clean_doi}"
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            return f"Failed to fetch metadata for DOI {clean_doi}. (Status: {resp.status_code})"
        
        data = resp.json()
        oa_info = data.get("open_access", {})
        if not oa_info.get("is_oa"):
            return f"The paper for DOI {clean_doi} is not Open Access (paywalled). Please upload the PDF manually."
        
        pdf_url = oa_info.get("oa_url")
        if not pdf_url:
            return f"Open Access URL not found for DOI {clean_doi}."
            
        print(f"[Agent] Downloading PDF from {pdf_url}")
        pdf_resp = requests.get(pdf_url, timeout=20)
        if pdf_resp.status_code != 200:
            return f"Failed to download PDF from {pdf_url}."
            
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_resp.content)
            tmp_path = tmp.name
            
        # Ingest
        filename = f"{clean_doi.replace('/', '_')}.pdf"
        md_text = pymupdf4llm.to_markdown(tmp_path)
        ingest_document_text(md_text, filename, chat_id)
        
        # Cleanup
        os.remove(tmp_path)
        return f"Successfully downloaded and saved Open Access paper for DOI: {clean_doi}. The user can now ask questions about it."
        
    except Exception as e:
        return f"An error occurred while fetching DOI {clean_doi}: {str(e)}"


def query_chat(chat_id: str, query: str):
    """
    Queries the vector store via a ReAct Agent. 
    The Agent has access to the RAG Query Engine (for uploaded/saved docs)
    and the Web Search tool (to fetch new info autonomously).
    """
    index = VectorStoreIndex.from_vector_store(vector_store)
    
    # 1. Setup RAG Query Engine Tool for this specific chat
    filters = MetadataFilters(
        filters=[MetadataFilter(key="chat_id", operator=FilterOperator.EQ, value=chat_id)]
    )
    query_engine = index.as_query_engine(filters=filters)
    
    def search_local_documents(q: str) -> str:
        """Use this tool to answer questions based on the user's uploaded documents and previously searched web sources."""
        return str(query_engine.query(q))
        
    local_search_tool = FunctionTool.from_defaults(fn=search_local_documents)
    
    # 2. Setup Web Search & Ingest Tool
    def search_web_tool(q: str) -> str:
        """
        Use this tool ONLY if the answer is not found in the local documents. 
        It will search the internet, read articles, and save them to your memory.
        """
        return web_search_and_ingest(q, chat_id)
        
    web_tool = FunctionTool.from_defaults(fn=search_web_tool)
    
    # 3. Setup DOI Fetcher Tool
    def search_doi_tool(doi: str) -> str:
        """
        Use this tool when the user provides a DOI (e.g., 10.1038/s41586-020-2649-2) 
        and asks to download, read, or import the paper.
        """
        return fetch_and_ingest_doi(doi, chat_id)
        
    doi_tool = FunctionTool.from_defaults(fn=search_doi_tool)
    
    # 4. Create the ReAct Agent
    agent = ReActAgent.from_tools(
        [local_search_tool, web_tool, doi_tool], 
        llm=Settings.llm, 
        verbose=True,
        context="You are a personal research assistant. Always try to answer using the 'search_local_documents' tool first. If the information is missing, use 'search_web_tool' to search the web, or 'search_doi_tool' to download a paper given its DOI."
    )
    
    response = agent.chat(query)
    return str(response)
