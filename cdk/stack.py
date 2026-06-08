"""
DocBot CDK Stack — v3
OpenSearch collection + index created manually.
This stack deploys: S3, Bedrock KB, Lambda, API Gateway only.
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


COLLECTION_ARN = "arn:aws:aoss:us-east-1:332422487493:collection/n72okfp6e0izh5csdd3"
ACCOUNT_ID     = "332422487493"
REGION         = "us-east-1"


class DocBotStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ── 1. S3 BUCKET ───────────────────────────────────────────────────
        docs_bucket = s3.Bucket(
            self, "DocsBucket",
            bucket_name=f"docbot-knowledge-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # ── 2. IAM ROLE FOR KNOWLEDGE BASE ─────────────────────────────────
        kb_role = iam.Role(
            self, "KnowledgeBaseRole",
            role_name="DocBotKnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            inline_policies={
                "KBPolicy": iam.PolicyDocument(statements=[
                    iam.PolicyStatement(
                        actions=["s3:GetObject", "s3:ListBucket"],
                        resources=[docs_bucket.bucket_arn, f"{docs_bucket.bucket_arn}/*"]
                    ),
                    iam.PolicyStatement(
                        actions=["aoss:APIAccessAll"],
                        resources=[f"arn:aws:aoss:{REGION}:{ACCOUNT_ID}:collection/*"]
                    ),
                    iam.PolicyStatement(
                        actions=["bedrock:InvokeModel"],
                        resources=["arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1"]
                    ),
                ])
            }
        )

        # ── 3. ADD KB ROLE TO OPENSEARCH DATA ACCESS POLICY ────────────────
        # Allow the KB role to read/write the index we created manually
        iam.CfnPolicy(
            self, "AOSSDataAccessForKB",
            policy_name="DocBotAOSSDataAccess",
            roles=[kb_role.role_name],
            policy_document={
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Action": ["aoss:APIAccessAll"],
                    "Resource": f"arn:aws:aoss:{REGION}:{ACCOUNT_ID}:collection/*"
                }]
            }
        )

        # ── 4. BEDROCK KNOWLEDGE BASE ───────────────────────────────────────
        knowledge_base = cdk.CfnResource(
            self, "KnowledgeBase",
            type="AWS::Bedrock::KnowledgeBase",
            properties={
                "Name": "DocBotKnowledgeBase",
                "RoleArn": kb_role.role_arn,
                "KnowledgeBaseConfiguration": {
                    "Type": "VECTOR",
                    "VectorKnowledgeBaseConfiguration": {
                        "EmbeddingModelArn": f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v1"
                    }
                },
                "StorageConfiguration": {
                    "Type": "OPENSEARCH_SERVERLESS",
                    "OpensearchServerlessConfiguration": {
                        "CollectionArn": COLLECTION_ARN,
                        "VectorIndexName": "docbot-index",
                        "FieldMapping": {
                            "VectorField": "embedding",
                            "TextField": "text",
                            "MetadataField": "metadata"
                        }
                    }
                }
            }
        )
        knowledge_base.add_dependency(kb_role.node.default_child)

        # ── 5. S3 DATA SOURCE ───────────────────────────────────────────────
        cdk.CfnResource(
            self, "KBDataSource",
            type="AWS::Bedrock::DataSource",
            properties={
                "Name": "DocBotS3DataSource",
                "KnowledgeBaseId": knowledge_base.ref,
                "DataSourceConfiguration": {
                    "Type": "S3",
                    "S3Configuration": {"BucketArn": docs_bucket.bucket_arn}
                }
            }
        )

        # ── 6. CHATBOT LAMBDA ───────────────────────────────────────────────
        lambda_role = iam.Role(
            self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "BedrockAccess": iam.PolicyDocument(statements=[
                    iam.PolicyStatement(
                        actions=["bedrock:InvokeModel", "bedrock:Retrieve", "bedrock:RetrieveAndGenerate"],
                        resources=["*"]
                    )
                ])
            }
        )

        chatbot_fn = _lambda.Function(
            self, "ChatbotFunction",
            function_name="docbot-chatbot",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("../lambda"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "KNOWLEDGE_BASE_ID": knowledge_base.ref,
                "BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
                "AWS_REGION_NAME": self.region,
            },
        )

        # ── 7. API GATEWAY ──────────────────────────────────────────────────
        api = apigw.RestApi(
            self, "DocBotApi",
            rest_api_name="docbot-api",
            description="DocBot RAG Chatbot API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["POST", "OPTIONS"],
                allow_headers=["Content-Type", "Authorization"],
            )
        )
        api.root.add_resource("chat").add_method("POST", apigw.LambdaIntegration(chatbot_fn))

        # ── 8. OUTPUTS ──────────────────────────────────────────────────────
        cdk.CfnOutput(self, "ApiEndpoint", value=api.url, description="API Gateway URL")
        cdk.CfnOutput(self, "BucketName", value=docs_bucket.bucket_name, description="S3 docs bucket")
        cdk.CfnOutput(self, "KnowledgeBaseId", value=knowledge_base.ref, description="Bedrock KB ID")


app = cdk.App()
DocBotStack(app, "DocBotStack")
app.synth()
