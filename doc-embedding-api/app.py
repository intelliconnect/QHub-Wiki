import json
import logging
import os
import hashlib
import time
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType
from fastembed.embedding import FlagEmbedding as TextEmbedding
from groq import Groq
import anthropic

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("knowledge_base_app")

app = FastAPI(
    title="Knowledge Base - Ingestion, Search & RAG",
    description="Complete knowledge base system with chunking and AI-powered search"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INGEST_API_SECRET = os.getenv("INGEST_API_SECRET")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

WIKIJS_DOMAIN = os.getenv("WIKIJS_DOMAIN")
if WIKIJS_DOMAIN and not WIKIJS_DOMAIN.startswith(("http://", "https://")):
    WIKIJS_DOMAIN = f"http://{WIKIJS_DOMAIN}"
WIKIJS_ADMIN_EMAIL = os.getenv("WIKIJS_ADMIN_EMAIL")
WIKIJS_ADMIN_PASSWORD = os.getenv("WIKIJS_ADMIN_PASSWORD")
KB_REPO_SSH_URL = os.getenv("KB_REPO_SSH_URL")
KB_GIT_BRANCH = os.getenv("KB_GIT_BRANCH")
KB_GIT_COMMIT_EMAIL = os.getenv("KB_GIT_COMMIT_EMAIL")
KB_GIT_COMMIT_NAME = os.getenv("KB_GIT_COMMIT_NAME")
KB_GIT_SSH_PRIVATE_KEY = os.getenv("KB_GIT_SSH_PRIVATE_KEY", "")
use_https = QDRANT_URL.startswith("https://") if QDRANT_URL else False

qdrant_port = 443 if use_https else 6333

qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    timeout=60,  
    prefer_grpc=False,
    https=use_https, 
    port=qdrant_port 
)
 

embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", max_length=512)
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

class IngestPayload(BaseModel):
    path: str
    repo: str
    commit: str
    deleted: bool
    content: str

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class RAGRequest(BaseModel):
    query: str
    limit: int = 3
    llm_provider: str = "groq"

class SearchResult(BaseModel):
    path: str
    title: str
    content: str
    score: float
    chunk_index: int
    total_chunks: int

def extract_frontmatter(content: str) -> tuple:
    frontmatter = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            frontmatter_text = parts[1].strip()
            for line in frontmatter_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()
            content = parts[2].strip()
    return frontmatter, content

def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(' '.join(chunk_words))
        start = end - overlap
        if end >= len(words):
            break
    return chunks

def generate_point_id(path: str, repo: str, chunk_index: int = 0) -> str:
    unique_string = f"{repo}:{path}:chunk_{chunk_index}"
    return hashlib.md5(unique_string.encode()).hexdigest()

def ensure_indexes_exist():
    try:
        qdrant_client.get_collection(COLLECTION_NAME)
        indexes_to_create = [
            ("path", PayloadSchemaType.KEYWORD),
            ("repo", PayloadSchemaType.KEYWORD)
        ]
        for field_name, field_type in indexes_to_create:
            try:
                qdrant_client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name=field_name,
                    field_schema=field_type
                )
                logger.info("Created index %s", field_name)
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info("Index already exists %s", field_name)
                else:
                    logger.error("Index creation failed for %s: %s", field_name, str(e)[:100])
        return True
    except Exception as e:
        logger.exception("Index check failed: %s", e)
        return False

def create_collection_if_not_exists():
    try:
        collections = qdrant_client.get_collections()
        collection_names = [col.name for col in collections.collections]
        if COLLECTION_NAME not in collection_names:
            logger.info("Creating collection %s", COLLECTION_NAME)
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            logger.info("Creating payload indexes")
            ensure_indexes_exist()
            logger.info("Collection created with indexes")
        else:
            logger.info("Collection %s already exists", COLLECTION_NAME)
            ensure_indexes_exist()
    except Exception as e:
        logger.exception("Collection setup error: %s", e)
        raise

def format_ssh_key(ssh_key: str) -> str:
    """
    Format SSH key to handle multiple input formats:
    1. Single-line without any newlines
    2. Escaped newlines (\\n)
    3. Actual newlines
    """
    if "\\n" not in ssh_key and "\n" not in ssh_key:
        logger.info("Formatting single-line SSH key")
        ssh_key = ssh_key.replace(
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        ).replace(
            "-----END OPENSSH PRIVATE KEY-----",
            "\n-----END OPENSSH PRIVATE KEY-----"
        )

        lines = ssh_key.split('\n')
        if len(lines) >= 2:
            header = lines[0]
            footer = lines[-1]
            middle = ''.join(lines[1:-1])
            middle_lines = [middle[i:i+64] for i in range(0, len(middle), 64)]
            ssh_key = header + '\n' + '\n'.join(middle_lines) + '\n' + footer

        logger.info("SSH key formatted with proper newlines")
    else:
        ssh_key = ssh_key.replace("\\n", "\n")
        logger.info("SSH key already had newline markers")

    return ssh_key

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Knowledge Base Server")
    create_collection_if_not_exists()

@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Knowledge Base - Complete System",
        "endpoints": {
            "ingestion": "/ingest - Add/update documents",
            "search": "/search - Vector similarity search",
            "rag": "/rag - AI-powered answers",
            "wiki_setup": "/start-process - Initialize Wiki.js",
            "stats": "/stats - Collection statistics",
            "health": "/health - Health check",
        },
        "features": {
            "chunking": f"{CHUNK_SIZE} words per chunk",
            "overlap": f"{CHUNK_OVERLAP} words",
            "ai_models": {
                "groq": "llama-3.3-70b-versatile" if groq_client else "not configured",
                "claude": "claude-sonnet-4-5-20250929" if anthropic_client else "not configured"
            }
        }
    }

@app.get("/health")
async def health():
    try:
        qdrant_client.get_collections()
        return {
            "status": "healthy",
            "qdrant": "connected",
            "groq": "ready" if groq_client else "not configured",
            "claude": "ready" if anthropic_client else "not configured",
            "collection": COLLECTION_NAME,
            "wikijs_configured": bool(WIKIJS_DOMAIN and WIKIJS_ADMIN_EMAIL)
        }
    except Exception as e:
        logger.exception("Health check failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Unhealthy: {str(e)}")

@app.post("/ingest")
async def ingest_document(
    payload: IngestPayload,
    x_ingest_token: Optional[str] = Header(None)
):
    if not x_ingest_token or x_ingest_token != INGEST_API_SECRET:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.deleted:
        try:
            scroll_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="path",
                        match=models.MatchValue(value=payload.path),
                    ),
                    models.FieldCondition(
                        key="repo",
                        match=models.MatchValue(value=payload.repo),
                    ),
                ]
            )
            scroll_result, next_page = qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=100,
                with_payload=False,
                with_vectors=False,
            )
            point_ids = [point.id for point in scroll_result]
            if point_ids:
                qdrant_client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=models.PointIdsList(points=point_ids),
                )
                logger.info("Deleted %s chunks for %s", len(point_ids), payload.path)
            else:
                logger.warning("No chunks found to delete for %s", payload.path)
            return {
                "status": "success",
                "action": "deleted",
                "chunks_deleted": len(point_ids)
            }
        except Exception as e:
            logger.exception("Delete failed: %s", e)
            raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    try:
        frontmatter, clean_content = extract_frontmatter(payload.content)
        word_count = len(clean_content.split())
        logger.info("Ingesting %s words for %s", word_count, payload.path)
        chunks = split_into_chunks(clean_content)
        logger.info("Generated %s chunks for %s", len(chunks), payload.path)
        points = []
        for idx, chunk in enumerate(chunks):
            embeddings = list(embedding_model.embed([chunk]))
            embedding_vector = embeddings[0].tolist()
            point_id = generate_point_id(payload.path, payload.repo, idx)
            metadata = {
                "path": payload.path,
                "repo": payload.repo,
                "commit": payload.commit,
                "title": frontmatter.get('title', ''),
                "description": frontmatter.get('description', ''),
                "tags": frontmatter.get('tags', ''),
                "chunk_index": idx,
                "total_chunks": len(chunks),
                "content": chunk[:500],
                "full_chunk": chunk
            }
            points.append(PointStruct(
                id=point_id,
                vector=embedding_vector,
                payload=metadata
            ))
        qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.info("Successfully ingested %s chunks for %s", len(chunks), payload.path)
        return {
            "status": "success",
            "action": "ingested",
            "path": payload.path,
            "title": frontmatter.get('title', 'N/A'),
            "word_count": word_count,
            "chunks_created": len(chunks)
        }
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/search", response_model=List[SearchResult])
async def search_documents(request: SearchRequest):
    try:
        logger.info("Search query received: %s", request.query)
        query_embedding = list(embedding_model.embed([request.query]))[0].tolist()
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=request.limit,
            with_payload=True,
            with_vectors=False
        ).points
        logger.info("Search returned %s results", len(results))
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                path=result.payload.get("path", ""),
                title=result.payload.get("title", ""),
                content=result.payload.get("full_chunk", "")[:500],
                score=result.score,
                chunk_index=result.payload.get("chunk_index", 0),
                total_chunks=result.payload.get("total_chunks", 1)
            ))
        return search_results
    except Exception as e:
        logger.exception("Search failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/rag")
async def rag_query(request: RAGRequest):
    try:
        logger.info("RAG query received: %s (provider: %s)", request.query, request.llm_provider)

        if request.llm_provider not in ["groq", "claude"]:
            raise HTTPException(status_code=400, detail="llm_provider must be 'groq' or 'claude'")

        if request.llm_provider == "groq" and not groq_client:
            raise HTTPException(status_code=503, detail="Groq is not configured")
        if request.llm_provider == "claude" and not anthropic_client:
            raise HTTPException(status_code=503, detail="Claude is not configured")

        query_embedding = list(embedding_model.embed([request.query]))[0].tolist()
        results = qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding,
            limit=request.limit,
            with_payload=True,
            with_vectors=False
        ).points
        logger.info("RAG retrieved %s relevant chunks", len(results))

        if not results:
            return {
                "answer": "I couldn't find any relevant information to answer your question.",
                "sources": [],
                "query": request.query,
                "llm_provider": request.llm_provider
            }

        context_parts = []
        sources = []
        for idx, result in enumerate(results):
            title = result.payload.get("title", "Untitled")
            content = result.payload.get("full_chunk", "")
            context_parts.append(f"[Document {idx + 1}: {title}]\n{content}\n")
            sources.append({
                "title": title,
                "path": result.payload.get("path", ""),
                "score": result.score,
                "chunk": f"{result.payload.get('chunk_index', 0) + 1}/{result.payload.get('total_chunks', 1)}"
            })
            logger.info("Using chunk %s with score %.3f", title, result.score)

        context = "\n".join(context_parts)

        system_prompt = """You are a helpful AI assistant that answers questions based on provided documents.

Rules:
- Only use information from the documents provided
- If documents don't contain the answer, say so clearly
- Be concise and direct
- Provide specific details when available"""

        user_prompt = f"""Based on these documents:

{context}

Question: {request.query}

Provide a clear answer based only on the documents above."""

        if request.llm_provider == "groq":
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=1000
            )
            answer = chat_completion.choices[0].message.content
            model_used = "llama-3.3-70b-versatile"

        elif request.llm_provider == "claude":
            message = anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1000,
                temperature=0.3,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            answer = message.content[0].text
            model_used = "claude-sonnet-4-5-20250929"

        logger.info("RAG answer generated using %s", request.llm_provider)

        return {
            "answer": answer,
            "sources": sources,
            "query": request.query,
            "chunks_used": len(results),
            "llm_provider": request.llm_provider,
            "model_used": model_used
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("RAG failed: %s", e)
        raise HTTPException(status_code=500, detail=f"RAG failed: {str(e)}")

@app.post("/start-process")
async def start_wiki_setup_process():
    """
    Orchestrates Wiki.js setup: admin creation, login, git configuration, and guest permissions
    """
    try:
        required_vars = {
            "WIKIJS_DOMAIN": WIKIJS_DOMAIN,
            "WIKIJS_ADMIN_EMAIL": WIKIJS_ADMIN_EMAIL,
            "WIKIJS_ADMIN_PASSWORD": WIKIJS_ADMIN_PASSWORD,
            "KB_REPO_SSH_URL": KB_REPO_SSH_URL,
            "KB_GIT_BRANCH": KB_GIT_BRANCH,
            "KB_GIT_SSH_PRIVATE_KEY": KB_GIT_SSH_PRIVATE_KEY
        }

        missing_vars = [key for key, value in required_vars.items() if not value]
        if missing_vars:
            raise HTTPException(
                status_code=500,
                detail=f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        results = {
            "step1_admin_creation": {},
            "step2_login": {},
            "step3_git_config": {},
            "step4_guest_permissions": {}
        }

        # create admin user
        logger.info("Step 1: Creating admin user")
        admin_payload = {
            "adminEmail": WIKIJS_ADMIN_EMAIL,
            "adminPassword": WIKIJS_ADMIN_PASSWORD,
            "adminPasswordConfirm": WIKIJS_ADMIN_PASSWORD,
            "siteUrl": WIKIJS_DOMAIN,
            "telemetry": True
        }

        admin_response = requests.post(
            f"{WIKIJS_DOMAIN}/finalize",
            json=admin_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if admin_response.status_code != 200:
            raise HTTPException(
                status_code=admin_response.status_code,
                detail=f"Admin creation failed: {admin_response.text}"
            )

        admin_data = admin_response.json()
        results["step1_admin_creation"] = admin_data
        logger.info("✓ Admin user created successfully: %s", admin_data)

        # wait for Wiki.js to complete setup and restart services
        logger.info("Waiting 10 seconds for Wiki.js to complete initialization...")
        time.sleep(10)

        # login to get JWT (with retry logic)
        logger.info("Step 2: Logging in to get JWT token")
        login_payload = [{
            "operationName": None,
            "variables": {
                "username": WIKIJS_ADMIN_EMAIL,
                "password": WIKIJS_ADMIN_PASSWORD,
                "strategy": "local"
            },
            "extensions": {},
            "query": """mutation ($username: String!, $password: String!, $strategy: String!) {
                authentication {
                    login(username: $username, password: $password, strategy: $strategy) {
                        responseResult {
                            succeeded
                            errorCode
                            slug
                            message
                            __typename
                        }
                        jwt
                        mustChangePwd
                        mustProvideTFA
                        mustSetupTFA
                        continuationToken
                        redirect
                        tfaQRImage
                        __typename
                    }
                    __typename
                }
            }"""
        }]

        # Retry login up to 3 times with 5 second delays
        max_retries = 3
        login_success = False
        jwt_token = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info("Login attempt %d/%d", attempt, max_retries)
                login_response = requests.post(
                    f"{WIKIJS_DOMAIN}/graphql",
                    json=login_payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if login_response.status_code == 200:
                    login_data = login_response.json()[0]

                    if login_data["data"]["authentication"]["login"]["responseResult"]["succeeded"]:
                        jwt_token = login_data["data"]["authentication"]["login"]["jwt"]
                        results["step2_login"] = {
                            "status": "success",
                            "message": "Login success",
                            "jwt_obtained": True,
                            "attempts": attempt
                        }
                        logger.info("✓ Login successful on attempt %d", attempt)
                        login_success = True
                        break
                    else:
                        error_msg = login_data["data"]["authentication"]["login"]["responseResult"]["message"]
                        logger.warning("Login failed on attempt %d: %s", attempt, error_msg)
                elif login_response.status_code == 502:
                    logger.warning("502 Bad Gateway on attempt %d - Wiki.js still initializing", attempt)
                else:
                    logger.warning("Login attempt %d returned status %d", attempt, login_response.status_code)

                if attempt < max_retries:
                    logger.info("Waiting 5 seconds before retry...")
                    time.sleep(5)

            except requests.RequestException as e:
                logger.warning("Network error on attempt %d: %s", attempt, str(e))
                if attempt < max_retries:
                    time.sleep(5)

        if not login_success:
            raise HTTPException(
                status_code=503,
                detail=f"Login failed after {max_retries} attempts. Wiki.js may still be initializing."
            )

        # configure git storage
        logger.info("Step 3: Configuring Git storage")

        # format ssh key properly, handles all formats
        ssh_key = format_ssh_key(KB_GIT_SSH_PRIVATE_KEY)

        git_config_payload = [{
            "operationName": None,
            "variables": {
                "targets": [
                    {
                        "isEnabled": False,
                        "key": "s3",
                        "config": [
                            {"key": "region", "value": "{\"v\":\"\"}"},
                            {"key": "bucket", "value": "{\"v\":\"\"}"},
                            {"key": "accessKeyId", "value": "{\"v\":\"\"}"},
                            {"key": "secretAccessKey", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "azure",
                        "config": [
                            {"key": "accountName", "value": "{\"v\":\"\"}"},
                            {"key": "accountKey", "value": "{\"v\":\"\"}"},
                            {"key": "containerName", "value": "{\"v\":\"wiki\"}"},
                            {"key": "storageTier", "value": "{\"v\":\"Cool\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "box",
                        "config": [
                            {"key": "clientId", "value": "{\"v\":\"\"}"},
                            {"key": "clientSecret", "value": "{\"v\":\"\"}"},
                            {"key": "rootFolder", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "digitalocean",
                        "config": [
                            {"key": "endpoint", "value": "{\"v\":\"nyc3.digitaloceanspaces.com\"}"},
                            {"key": "bucket", "value": "{\"v\":\"\"}"},
                            {"key": "accessKeyId", "value": "{\"v\":\"\"}"},
                            {"key": "secretAccessKey", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "dropbox",
                        "config": [
                            {"key": "appKey", "value": "{\"v\":\"\"}"},
                            {"key": "appSecret", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": True,
                        "key": "git",
                        "config": [
                            {"key": "authType", "value": "{\"v\":\"ssh\"}"},
                            {"key": "repoUrl", "value": f"{{\"v\":\"{KB_REPO_SSH_URL}\"}}"},
                            {"key": "branch", "value": f"{{\"v\":\"{KB_GIT_BRANCH}\"}}"},
                            {"key": "sshPrivateKeyMode", "value": "{\"v\":\"contents\"}"},
                            {"key": "sshPrivateKeyPath", "value": "{\"v\":\"\"}"},
                            {"key": "sshPrivateKeyContent", "value": json.dumps({"v": ssh_key})},
                            {"key": "verifySSL", "value": "{\"v\":true}"},
                            {"key": "basicUsername", "value": "{\"v\":\"\"}"},
                            {"key": "basicPassword", "value": "{\"v\":\"\"}"},
                            {"key": "defaultEmail", "value": f"{{\"v\":\"{KB_GIT_COMMIT_EMAIL}\"}}"},
                            {"key": "defaultName", "value": f"{{\"v\":\"{KB_GIT_COMMIT_NAME}\"}}"},
                            {"key": "localRepoPath", "value": "{\"v\":\"./data/repo\"}"},
                            {"key": "alwaysNamespace", "value": "{\"v\":false}"},
                            {"key": "gitBinaryPath", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "sync",
                        "syncInterval": "PT5M"
                    },
                    {
                        "isEnabled": False,
                        "key": "gdrive",
                        "config": [
                            {"key": "clientId", "value": "{\"v\":\"\"}"},
                            {"key": "clientSecret", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "disk",
                        "config": [
                            {"key": "path", "value": "{\"v\":\"\"}"},
                            {"key": "createDailyBackups", "value": "{\"v\":false}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "onedrive",
                        "config": [
                            {"key": "clientId", "value": "{\"v\":\"\"}"},
                            {"key": "clientSecret", "value": "{\"v\":\"\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "s3generic",
                        "config": [
                            {"key": "endpoint", "value": "{\"v\":\"https://service.region.example.com\"}"},
                            {"key": "bucket", "value": "{\"v\":\"\"}"},
                            {"key": "accessKeyId", "value": "{\"v\":\"\"}"},
                            {"key": "secretAccessKey", "value": "{\"v\":\"\"}"},
                            {"key": "sslEnabled", "value": "{\"v\":true}"},
                            {"key": "s3ForcePathStyle", "value": "{\"v\":false}"},
                            {"key": "s3BucketEndpoint", "value": "{\"v\":false}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    },
                    {
                        "isEnabled": False,
                        "key": "sftp",
                        "config": [
                            {"key": "host", "value": "{\"v\":\"\"}"},
                            {"key": "port", "value": "{\"v\":22}"},
                            {"key": "authMode", "value": "{\"v\":\"privateKey\"}"},
                            {"key": "username", "value": "{\"v\":\"\"}"},
                            {"key": "privateKey", "value": "{\"v\":\"\"}"},
                            {"key": "passphrase", "value": "{\"v\":\"\"}"},
                            {"key": "password", "value": "{\"v\":\"\"}"},
                            {"key": "basePath", "value": "{\"v\":\"/root/wiki\"}"}
                        ],
                        "mode": "push",
                        "syncInterval": "P0D"
                    }
                ]
            },
            "extensions": {},
            "query": """mutation ($targets: [StorageTargetInput]!) {
                storage {
                    updateTargets(targets: $targets) {
                        responseResult {
                            succeeded
                            errorCode
                            slug
                            message
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }"""
        }]

        git_config_response = requests.post(
            f"{WIKIJS_DOMAIN}/graphql",
            json=git_config_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jwt_token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=30
        )

        if git_config_response.status_code != 200:
            raise HTTPException(
                status_code=git_config_response.status_code,
                detail=f"Git configuration failed: {git_config_response.text}"
            )

        git_data = git_config_response.json()[0]

        if not git_data["data"]["storage"]["updateTargets"]["responseResult"]["succeeded"]:
            error_msg = git_data["data"]["storage"]["updateTargets"]["responseResult"]["message"]
            raise HTTPException(status_code=500, detail=f"Git config failed: {error_msg}")

        results["step3_git_config"] = git_data["data"]["storage"]["updateTargets"]["responseResult"]
        logger.info("✓ Git storage configured successfully")

        # update guests group permissions
        logger.info("Step 4: Updating Guests group permissions")

        guest_permissions_payload = [{
            "operationName": None,
            "variables": {
                "id": 2,
                "name": "Guests",
                "redirectOnLogin": "/",
                "permissions": [],
                "pageRules": [
                    {
                        "id": "guest",
                        "path": "",
                        "roles": ["read:pages", "read:assets", "read:comments"],
                        "match": "START",
                        "deny": False,
                        "locales": []
                    }
                ]
            },
            "extensions": {},
            "query": """mutation ($id: Int!, $name: String!, $redirectOnLogin: String!, $permissions: [String]!, $pageRules: [PageRuleInput]!) {
                groups {
                    update(id: $id, name: $name, redirectOnLogin: $redirectOnLogin, permissions: $permissions, pageRules: $pageRules) {
                        responseResult {
                            succeeded
                            errorCode
                            slug
                            message
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }"""
        }]

        guest_permissions_response = requests.post(
            f"{WIKIJS_DOMAIN}/graphql",
            json=guest_permissions_payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jwt_token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=30
        )

        if guest_permissions_response.status_code != 200:
            raise HTTPException(
                status_code=guest_permissions_response.status_code,
                detail=f"Guest permissions update failed: {guest_permissions_response.text}"
            )

        guest_data = guest_permissions_response.json()[0]

        if not guest_data["data"]["groups"]["update"]["responseResult"]["succeeded"]:
            error_msg = guest_data["data"]["groups"]["update"]["responseResult"]["message"]
            raise HTTPException(status_code=500, detail=f"Guest permissions failed: {error_msg}")

        results["step4_guest_permissions"] = guest_data["data"]["groups"]["update"]["responseResult"]
        logger.info("✓ Guests group permissions updated successfully")

        return {
            "status": "success",
            "message": "Wiki.js setup completed successfully - Admin created, logged in, Git configured, and guest permissions set",
            "details": results
        }

    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.exception("Network error during Wiki setup: %s", e)
        raise HTTPException(status_code=503, detail=f"Network error: {str(e)}")
    except Exception as e:
        logger.exception("Wiki setup process failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")
 

@app.get("/stats")
async def collection_stats():
    try:
        collection_info = qdrant_client.get_collection(COLLECTION_NAME)
        return {
            "collection_name": COLLECTION_NAME,
            "total_points": collection_info.points_count,
            "vector_size": collection_info.config.params.vectors.size,
            "distance": collection_info.config.params.vectors.distance.name,
            "status": "active"
        }
    except Exception as e:
        logger.exception("Stats retrieval failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info("Starting Uvicorn on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)