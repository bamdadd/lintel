from pathlib import Path

import pytest


@pytest.fixture()
def sample_files(tmp_path: Path) -> dict[str, str]:
    """Create sample files with known integration patterns."""
    # File with HTTP calls
    http_file = tmp_path / "http_service.py"
    http_file.write_text("""
import requests
import httpx
from grpc import insecure_channel

def call_api():
    requests.get("http://other-service/api")

async def async_call():
    async with httpx.AsyncClient() as client:
        await client.post("http://other/api")

channel = insecure_channel("localhost:50051")
""")

    # File with async messaging
    async_file = tmp_path / "messaging.py"
    async_file.write_text("""
from kafka import KafkaProducer, KafkaConsumer
import nats

producer = KafkaProducer(bootstrap_servers=["kafka:9092"])
consumer = KafkaConsumer("topic")

async def connect_nats():
    nc = await nats.connect("nats://localhost:4222")
""")

    # File with DB connections
    db_file = tmp_path / "database.py"
    db_file.write_text("""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import asyncpg
from pymongo import MongoClient

engine = create_engine("postgresql://localhost/db")
Session = sessionmaker(bind=engine)

async def get_pool():
    return await asyncpg.create_pool("postgresql://localhost/db")

mongo = MongoClient("mongodb://localhost:27017")
""")

    # File with blob storage
    blob_file = tmp_path / "storage.py"
    blob_file.write_text("""
import boto3
from azure.storage.blob import BlobServiceClient

s3 = boto3.client("s3")
blob_service = BlobServiceClient.from_connection_string("conn_str")
""")

    # File with external APIs
    external_file = tmp_path / "external.py"
    external_file.write_text("""
import stripe
from twilio.rest import Client as TwilioClient
import openai
""")

    return {
        "http": str(http_file),
        "async": str(async_file),
        "db": str(db_file),
        "blob": str(blob_file),
        "external": str(external_file),
        "all": [str(http_file), str(async_file), str(db_file), str(blob_file), str(external_file)],
    }
