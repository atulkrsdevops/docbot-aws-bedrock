import boto3
import json
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION = "us-east-1"
INDEX_NAME = "docbot-index"

# Get collection endpoint from AWS
aoss = boto3.client("opensearchserverless", region_name=REGION)
collections = aoss.list_collections()["collectionSummaries"]
collection = next(c for c in collections if c["name"] == "docbot-vectors")
collection_id = collection["id"]
endpoint = f"{collection_id}.{REGION}.aoss.amazonaws.com"
print(f"Collection endpoint: {endpoint}")

# Auth
session = boto3.Session()
creds = session.get_credentials()
auth = AWS4Auth(
    creds.access_key, creds.secret_key,
    REGION, "aoss",
    session_token=creds.token
)

# Connect
client = OpenSearch(
    hosts=[{"host": endpoint, "port": 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)

# Create index
body = {
    "settings": {"index": {"knn": True}},
    "mappings": {
        "properties": {
            "embedding": {
                "type": "knn_vector",
                "dimension": 1536,
                "method": {"name": "hnsw", "space_type": "l2", "engine": "faiss"}
            },
            "text":     {"type": "text"},
            "metadata": {"type": "text"}
        }
    }
}

if client.indices.exists(INDEX_NAME):
    print(f"Index '{INDEX_NAME}' already exists.")
else:
    response = client.indices.create(INDEX_NAME, body=body)
    print(f"Index created: {response}")