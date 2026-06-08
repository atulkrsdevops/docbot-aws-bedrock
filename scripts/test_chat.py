"""
test_chat.py — Interactive CLI to test your DocBot API

Usage:
    python test_chat.py --api-url https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/
    python test_chat.py --api-url <url> --query "What is the refund policy?"
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def ask(api_url: str, query: str) -> dict:
    """Send a query to the DocBot API and return the response."""
    endpoint = api_url.rstrip("/") + "/chat"
    payload = json.dumps({"query": query}).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"\n✗ HTTP {e.code}: {body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n✗ Connection error: {e.reason}")
        print("  Check your API URL and ensure the CDK stack is deployed.")
        sys.exit(1)


def print_response(result: dict):
    print(f"\n{'─'*50}")
    print(f"Answer:\n{result.get('answer', 'No answer returned')}")
    sources = result.get("sources", [])
    if sources:
        print(f"\nSources ({result.get('chunks_retrieved', '?')} chunks retrieved):")
        for s in sources:
            print(f"  • {s}")
    print(f"{'─'*50}\n")


def interactive_mode(api_url: str):
    print(f"\n DocBot Chat — Interactive Mode")
    print(f" API: {api_url}")
    print(f" Type 'exit' or Ctrl+C to quit.\n{'─'*50}\n")

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nBye!")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break

        print("DocBot: thinking...")
        result = ask(api_url, query)
        print_response(result)


def main():
    parser = argparse.ArgumentParser(description="Test DocBot RAG chatbot")
    parser.add_argument("--api-url", required=True, help="API Gateway base URL")
    parser.add_argument("--query", help="Single query (non-interactive mode)")
    args = parser.parse_args()

    if args.query:
        result = ask(args.api_url, args.query)
        print_response(result)
    else:
        interactive_mode(args.api_url)


if __name__ == "__main__":
    main()
