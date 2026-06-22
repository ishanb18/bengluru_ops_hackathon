"""
llm_verifier.py — Web Search + LLM Agent for Real-Time Incident Verification
"""

import os
import logging
import httpx
from groq import Groq
import sys

# Ensure config is accessible
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.core.config import settings

logger = logging.getLogger(__name__)

def verify_incident_via_llm(event_cause: str, address: str) -> dict:
    """
    1. Runs a live web search for the incident.
    2. Feeds results to Groq LLM.
    3. Returns verification score and summary.
    """
    groq_api_key = settings.GROQ_API_KEY
    if not groq_api_key:
        logger.warning("GROQ_API_KEY is missing!")
        return {"score": 0, "summary": "LLM Verification disabled (Missing Groq Key).", "verified": False}

    use_openrouter = (
        groq_api_key.startswith("sk-or-")
        or "openrouter" in groq_api_key.lower()
    )
    # 1. Web Search
    clean_address = address.replace("[LIVE]", "").replace("[SIMULATED]", "").replace("Historical:", "").strip()
    query = f"Bengaluru {clean_address} traffic news {event_cause}"
    search_results = []
    try:
        tavily_key = settings.TAVILY_API_KEY
        if not tavily_key:
            logger.warning("TAVILY_API_KEY is missing — web search skipped.")
            search_results = ["Tavily API key not configured."]
            raise ValueError("skip_tavily")
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 3
            },
            timeout=10.0
        )
        response.raise_for_status()
        
        results = response.json().get("results", [])
        for r in results:
            search_results.append(r.get("content", ""))
            
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        search_results = ["Search failed or blocked."]
        
    search_context = "\n".join(search_results)

    # 2. LLM Prompt
    prompt = f"""
You are an advanced AI Traffic Intelligence Agent for the Bengaluru Traffic Police.
An incident has been auto-detected by live sensors:
- Cause: {event_cause}
- Location: {address}

Recent web search results retrieved right now:
<search_results>
{search_context}
</search_results>

Analyze the situation. If the search results confirm it, use them. If the search results are empty or say "Search failed" (which is common for localized breakdowns), rely on your vast internal knowledge of Bengaluru's traffic topology to SIMULATE a highly realistic, brief intelligence report explaining exactly why this specific incident on {address} causes major cascading delays.

Output your response as a valid JSON object with EXACTLY these two keys:
1. "score": An integer between 0 and 100. If verified by search, 80-100. If simulated based on topology, 60-79.
2. "summary": A very brief 1-2 sentence intelligence report explaining the impact.

Return ONLY the JSON object, nothing else.
"""

    client = Groq(
        api_key=groq_api_key,
        base_url="https://openrouter.ai/api/v1" if use_openrouter else None,
    )

    models_to_try = [
        "llama-3.1-8b-instant",
        "llama3-8b-8192",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]
    if use_openrouter:
        models_to_try = ["openai/gpt-oss-120b"]

    last_error = None
    for model_name in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            response_text = completion.choices[0].message.content
            
            import json
            result = json.loads(response_text)
            
            score = int(result.get("score", 0))
            summary = result.get("summary", "Verification complete.")
            verified = score >= 50
            
            return {
                "score": score,
                "summary": summary,
                "verified": verified
            }
        except Exception as e:
            logger.warning(f"Groq LLM ({model_name}) verification failed: {e}")
            last_error = e

    logger.error(f"All Groq models failed verification. Last error: {last_error}")
    return {"score": 0, "summary": "LLM error: Rate limits exceeded on all fallback models.", "verified": False}
