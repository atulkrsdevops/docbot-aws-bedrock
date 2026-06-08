"""
DocBot Lambda Handler
Receives user query → retrieves from Bedrock KB → generates answer via Claude
"""

import json
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")

bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=REGION)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)


def retrieve_from_kb(query: str, num_results: int = 5) -> list[dict]:
    """Retrieve relevant chunks from Bedrock Knowledge Base."""
    response = bedrock_agent.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": num_results}
        },
    )
    results = []
    for r in response.get("retrievalResults", []):
        results.append({
            "text": r["content"]["text"],
            "score": r.get("score", 0),
            "source": r.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
        })
    logger.info(f"Retrieved {len(results)} chunks for query: {query[:80]}")
    return results


def build_prompt(query: str, context_chunks: list[dict]) -> str:
    """Build a RAG prompt with retrieved context."""
    context = "\n\n---\n\n".join(
        f"[Source: {c['source']}]\n{c['text']}" for c in context_chunks
    )
    return f"""You are a helpful assistant. Answer the user's question using ONLY the context provided below.
If the answer is not in the context, say "I don't have information about that in my knowledge base."

<context>
{context}
</context>

<question>
{query}
</question>

Answer concisely and accurately based on the context above."""


def call_bedrock_llm(prompt: str) -> str:
    """Call Claude via Bedrock InvokeModel."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = bedrock_runtime.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


def lambda_handler(event, context):
    """Main Lambda entry point."""
    # CORS headers for browser clients
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
    }

    try:
        # Parse request body
        body = json.loads(event.get("body", "{}"))
        query = body.get("query", "").strip()

        if not query:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Missing 'query' in request body"}),
            }

        if len(query) > 2000:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Query too long (max 2000 chars)"}),
            }

        # RAG pipeline
        chunks = retrieve_from_kb(query)

        if not chunks:
            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps({
                    "answer": "I couldn't find relevant information in the knowledge base.",
                    "sources": [],
                }),
            }

        prompt = build_prompt(query, chunks)
        answer = call_bedrock_llm(prompt)

        # Return answer + sources for transparency
        sources = list({c["source"] for c in chunks})  # deduplicated

        logger.info(f"Query answered successfully. Sources: {sources}")

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "answer": answer,
                "sources": sources,
                "chunks_retrieved": len(chunks),
            }),
        }

    except bedrock_agent.exceptions.ResourceNotFoundException:
        logger.error(f"Knowledge Base {KNOWLEDGE_BASE_ID} not found")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Knowledge base not configured. Check KNOWLEDGE_BASE_ID."}),
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Internal server error"}),
        }
