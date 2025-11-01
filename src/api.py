#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from run_query import TextUtility

app = FastAPI(title="Multi-Task Text Utility API", version="1.0.0")

class QueryRequest(BaseModel):
    question: str = Field(..., description="User question to process")

class QueryResponse(BaseModel):
    answer: str
    confidence: float
    actions: list
    category: str
    follow_up: Optional[str]
    metrics: dict
    safety_warning: Optional[str] = None

@app.get("/")
def root():
    return {
        "service": "Multi-Task Text Utility API",
        "version": "1.0.0",
        "description": "A customer support assistant that processes user questions and returns structured JSON responses with comprehensive metrics tracking and safety measures",
        "endpoints": {
            "/": "GET - API documentation (this endpoint)",
            "/health": "GET - Health check and available AI providers",
            "/prompts": "GET - List available prompt templates",
            "/query": "POST - Process a user question and get structured response"
        },
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    """
    Health check endpoint that returns the status of the API and available AI providers.
    
    Returns:
    - status: API health status
    - available_providers: List of initialized AI providers
    - providers_count: Number of available providers
    """
    utility = TextUtility()
    available_providers = [p.get('provider') for p in utility.ai_providers.values() if p]
    return {
        "status": "healthy" if available_providers else "degraded",
        "available_providers": available_providers if available_providers else None,
        "providers_count": len(available_providers),
        "message": "API is operational" if available_providers else "No AI providers configured. Please set API keys in .env file."
    }

@app.post("/query", response_model=QueryResponse)
def process_query(request: QueryRequest):
    """
    Process a user question and return a structured JSON response.
    
    The question is validated through safety checks before processing. If the question
    contains invalid patterns (e.g., only numbers, only asterisks, repetitive characters),
    it will be blocked and a safety_warning will be included in the response.
    
    Configuration (provider, prompt file, models) is managed via environment variables
    in the .env file and cannot be overridden via API requests.
    
    Request Body:
    - question (str, required): The user's question to process
    
    Response:
    - answer (str): The AI-generated answer
    - confidence (float): Confidence score (0.0-1.0)
    - actions (list): List of actionable steps
    - category (str): One of: "technical", "billing", "general", "other"
    - follow_up (str | null): Optional follow-up question
    - metrics (dict): Performance and cost metrics
    - safety_warning (str | null): Warning message if safety check failed
    
    Status Codes:
    - 200: Success
    - 500: Internal server error or processing failure
    """
    try:
        utility = TextUtility()
        result = utility.process_query(request.question)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))
        
        return QueryResponse(
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0.0),
            actions=result.get("actions", []),
            category=result.get("category", "other"),
            follow_up=result.get("follow_up"),
            metrics=result.get("metrics", {}),
            safety_warning=result.get("safety_warning")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/prompts")
def list_prompts():
    """
    List all available prompt template files.
    
    Prompt templates define how the AI interprets and responds to questions.
    The active prompt is controlled by the PROMPT_FILE environment variable.
    
    Returns:
    - prompts: List of available prompt template file names
    - default: The default prompt template name
    - current: The currently active prompt template (from .env)
    """
    prompts_dir = Path("prompts")
    if not prompts_dir.exists():
        return {
            "prompts": [],
            "default": "main_prompt.txt",
            "current": os.getenv("PROMPT_FILE", "main_prompt.txt"),
            "message": "Prompts directory not found"
        }
    
    prompt_files = [f.name for f in prompts_dir.glob("*.txt")]
    current_prompt = os.getenv("PROMPT_FILE", "main_prompt.txt")
    
    return {
        "prompts": prompt_files,
        "default": "main_prompt.txt",
        "current": current_prompt,
        "available_count": len(prompt_files)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
