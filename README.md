# DocBot — RAG Chatbot on AWS Bedrock

A production-ready Retrieval-Augmented Generation (RAG) chatbot built with **Amazon Bedrock Knowledge Bases**, **AWS Lambda**, and **API Gateway** — fully provisioned via **AWS CDK**.

Upload your documents → deploy → chat with them instantly.

\---



\## Demo



!\[DocBot Chat UI](screenshots/botUI1.jpg)

!\[Who Built DocBot](screenshots/botUI2.jpg)



## Architecture

```
User / Browser
    │
    ▼
API Gateway (REST)
    │
    ▼
Lambda (orchestrator)
    ├──► Bedrock Knowledge Base ──► OpenSearch Serverless (vector store)
    │         │
    │         └──► S3 (raw documents: PDF, TXT, MD, DOCX)
    │
    └──► Bedrock LLM (Claude 3 Haiku)
              │
              ▼
         Answer + sources → User
```

\---

## Prerequisites

### 1\. AWS Account Setup

1. **Create an AWS account** at [aws.amazon.com](https://aws.amazon.com) if you don't have one.
2. **Create an IAM user** with programmatic access:

   * Go to IAM → Users → Create user
   * Attach policy: `AdministratorAccess` (for dev; restrict in production)
   * Create access key → download credentials
3. **Configure AWS CLI**:

```bash
   pip install awscli
   aws configure
   # Enter: Access Key ID, Secret Key, Region (e.g. us-east-1), output format (json)
   ```

### 2\. Enable Bedrock Model Access

> This is the step most beginners miss.

1. Go to **AWS Console → Amazon Bedrock → Model access** (left sidebar)
2. Click **Manage model access**
3. Enable these models:

   * ✅ `Amazon Titan Embeddings V1` (for Knowledge Base embeddings)
   * ✅ `Anthropic Claude 3 Haiku` (for answer generation)
4. Click **Save changes** — access is usually granted within a few minutes

### 3\. Install Dependencies

```bash
# Node.js (required for AWS CDK)
# Install from https://nodejs.org (LTS version)
node --version   # should be 18+

# AWS CDK CLI
npm install -g aws-cdk
cdk --version    # should be 2.x

# Python dependencies
pip install aws-cdk-lib constructs boto3
```

### 4\. Bootstrap CDK (one-time per account/region)

```bash
cdk bootstrap aws://YOUR\_ACCOUNT\_ID/us-east-1
# Find your account ID: aws sts get-caller-identity
```

\---

## Project Structure

```
docbot/
├── cdk/
│   └── stack.py          # CDK stack — all AWS resources
├── lambda/
│   └── handler.py        # Lambda function (RAG pipeline)
├── scripts/
│   ├── upload\_docs.py    # Upload docs to S3 + sync KB
│   └── test\_chat.py      # CLI test client
├── ui/
│   └── index.html        # Browser chat interface
└── README.md
```

\---

## Deployment

### Step 1 — Deploy the CDK Stack

```bash
cd cdk
cdk deploy
```

This provisions:

* S3 bucket (document storage)
* OpenSearch Serverless collection (vector store)
* Bedrock Knowledge Base (wired to S3 + OpenSearch)
* Lambda function (RAG orchestrator)
* API Gateway REST API

At the end of deployment, CDK prints:

```
Outputs:
DocBotStack.ApiEndpoint     = https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/
DocBotStack.BucketName      = docbot-knowledge-123456789-us-east-1
DocBotStack.KnowledgeBaseId = XXXXXXXXXX
```

Save these values.

### Step 2 — Upload Your Documents

Put your documents (PDFs, TXTs, Markdown files, etc.) in a local folder, then:

```bash
python scripts/upload\_docs.py \\
  --bucket docbot-knowledge-123456789-us-east-1 \\
  --kb-id XXXXXXXXXX \\
  --source ./your-docs/
```

This uploads files to S3 and triggers an ingestion job that:

1. Chunks your documents
2. Creates vector embeddings using Titan Embed
3. Stores them in OpenSearch Serverless

Wait for the script to print `✓ Ingestion complete!` before chatting.

### Step 3 — Test via CLI

```bash
# Interactive mode
python scripts/test\_chat.py --api-url https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/

# Single query
python scripts/test\_chat.py \\
  --api-url https://xxxxx.execute-api.us-east-1.amazonaws.com/prod/ \\
  --query "What is the refund policy?"
```

### Step 4 — Open the Chat UI

Open `ui/index.html` in your browser (double-click or `open ui/index.html`).

Paste your API Gateway URL into the input at the top and start chatting.

\---

## API Reference

### POST /chat

**Request:**

```json
{
  "query": "What is the onboarding process for new employees?"
}
```

**Response:**

```json
{
  "answer": "According to the onboarding guide, new employees should...",
  "sources": \["s3://docbot-bucket/hr-handbook.pdf"],
  "chunks\_retrieved": 5
}
```

**Error Response:**

```json
{
  "error": "Missing 'query' in request body"
}
```

\---

## Supported Document Types

|Format|Extension|
|-|-|
|PDF|`.pdf`|
|Plain text|`.txt`|
|Markdown|`.md`|
|Word|`.docx`|
|HTML|`.html`|
|CSV|`.csv`|

\---

## Cost Estimate (approximate)

|Service|Cost|
|-|-|
|OpenSearch Serverless|\~$0.24/OCU-hour (min 2 OCUs = \~$0.48/hr)|
|Bedrock Titan Embed|$0.0001 per 1K tokens|
|Bedrock Claude 3 Haiku|\~$0.00025 per query|
|Lambda|Free tier covers millions of invocations|
|API Gateway|$3.50 per million calls|

> ⚠️ OpenSearch Serverless is the main cost driver. Tear down when not in use.

\---

## Cleanup

```bash
cd cdk
cdk destroy
```

This removes all provisioned resources and stops billing.

\---

## What This Demonstrates (for Recruiters)

* **IaC with AWS CDK** — full stack provisioned as code (your DevOps background)
* **Amazon Bedrock Knowledge Bases** — managed RAG without custom vector DB code
* **Lambda orchestration** — serverless, production-ready handler with error handling
* **API Gateway** — REST API with CORS, ready for frontend integration
* **Observability** — CloudWatch log retention configured at deploy time

\---

## Extending This Project

* Add **Cognito authentication** to the API Gateway
* Add **streaming responses** using Lambda response streaming
* Add **Bedrock Guardrails** for content filtering
* Replace OpenSearch Serverless with **Aurora pgvector** to reduce cost
* Add a **CI/CD pipeline** with AWS CodePipeline (natural DevOps extension)

\---

## Author

Built as a portfolio project demonstrating DevOps → GenAI transition skills using AWS Bedrock and CDK.

