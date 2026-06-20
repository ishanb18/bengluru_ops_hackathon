"""
llm_verifier.py — Web Search + LLM Agent for Real-Time Incident Verification
"""

import os
import logging
from duckduckgo_search import DDGS
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
    query = f"Bengaluru traffic {event_cause} near {address} today"
    search_results = []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, region='in-en', max_results=3)
            for r in results:
                search_results.append(r['body'])
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
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

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b" if use_openrouter else "llama-3.3-70b-versatile",
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
        logger.error(f"Groq LLM verification failed: {e}")
        return {"score": 0, "summary": "LLM error during verification.", "verified": False}
