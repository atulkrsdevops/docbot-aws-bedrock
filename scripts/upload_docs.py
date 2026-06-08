"""
upload_docs.py — Upload knowledge documents to S3 and trigger KB ingestion job

Usage:
    python upload_docs.py --bucket <bucket-name> --kb-id <kb-id> --source ./docs/
    python upload_docs.py --bucket <bucket-name> --kb-id <kb-id> --source resume.pdf
"""

import argparse
import os
import sys
import time
import boto3
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".html", ".csv"}


def upload_directory(s3_client, bucket: str, source_dir: Path) -> int:
    """Upload all supported files from a directory to S3."""
    uploaded = 0
    for file_path in source_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
            s3_key = str(file_path.relative_to(source_dir))
            print(f"  ↑ Uploading: {file_path.name} → s3://{bucket}/{s3_key}")
            s3_client.upload_file(str(file_path), bucket, s3_key)
            uploaded += 1
    return uploaded


def upload_single_file(s3_client, bucket: str, file_path: Path) -> int:
    """Upload a single file to S3."""
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        print(f"  ⚠  Skipping {file_path.name} — unsupported format")
        print(f"     Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
        return 0
    s3_key = file_path.name
    print(f"  ↑ Uploading: {file_path.name} → s3://{bucket}/{s3_key}")
    s3_client.upload_file(str(file_path), bucket, s3_key)
    return 1


def start_ingestion_job(bedrock_agent_client, kb_id: str, data_source_id: str) -> str:
    """Start a Bedrock KB ingestion job to sync S3 docs into vector store."""
    response = bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
    )
    job_id = response["ingestionJob"]["ingestionJobId"]
    print(f"\n  ✓ Ingestion job started: {job_id}")
    return job_id


def wait_for_ingestion(bedrock_agent_client, kb_id: str, data_source_id: str, job_id: str):
    """Poll until the ingestion job completes."""
    print("  ⏳ Waiting for ingestion to complete ", end="", flush=True)
    while True:
        response = bedrock_agent_client.get_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
            ingestionJobId=job_id,
        )
        status = response["ingestionJob"]["status"]
        print(".", end="", flush=True)

        if status == "COMPLETE":
            stats = response["ingestionJob"].get("statistics", {})
            print(f"\n  ✓ Ingestion complete!")
            print(f"    Documents indexed: {stats.get('numberOfDocumentsIndexed', '?')}")
            print(f"    Documents failed:  {stats.get('numberOfDocumentsFailed', '?')}")
            break
        elif status == "FAILED":
            print(f"\n  ✗ Ingestion failed. Check CloudWatch logs.")
            sys.exit(1)

        time.sleep(5)


def get_data_source_id(bedrock_agent_client, kb_id: str) -> str:
    """Fetch the first data source ID for the given Knowledge Base."""
    response = bedrock_agent_client.list_data_sources(knowledgeBaseId=kb_id)
    data_sources = response.get("dataSourceSummaries", [])
    if not data_sources:
        print("  ✗ No data sources found for this Knowledge Base.")
        sys.exit(1)
    return data_sources[0]["dataSourceId"]


def main():
    parser = argparse.ArgumentParser(description="Upload docs to S3 and sync Bedrock KB")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--kb-id", required=True, help="Bedrock Knowledge Base ID")
    parser.add_argument("--source", required=True, help="Path to file or directory")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--no-sync", action="store_true", help="Skip KB sync after upload")
    args = parser.parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"✗ Source not found: {args.source}")
        sys.exit(1)

    s3 = boto3.client("s3", region_name=args.region)
    bedrock_agent = boto3.client("bedrock-agent", region_name=args.region)

    print(f"\n DocBot — Document Upload\n{'─'*40}")
    print(f"  Bucket : {args.bucket}")
    print(f"  KB ID  : {args.kb_id}")
    print(f"  Source : {args.source}\n")

    # Upload
    if source_path.is_dir():
        count = upload_directory(s3, args.bucket, source_path)
    else:
        count = upload_single_file(s3, args.bucket, source_path)

    if count == 0:
        print("\n  Nothing to upload.")
        sys.exit(0)

    print(f"\n  ✓ Uploaded {count} file(s) to S3")

    # Sync KB
    if not args.no_sync:
        ds_id = get_data_source_id(bedrock_agent, args.kb_id)
        job_id = start_ingestion_job(bedrock_agent, args.kb_id, ds_id)
        wait_for_ingestion(bedrock_agent, args.kb_id, ds_id, job_id)
        print("\n  ✓ Knowledge base is ready. Start chatting!\n")
    else:
        print("\n  Skipped KB sync (--no-sync). Run manually to index documents.\n")


if __name__ == "__main__":
    main()
