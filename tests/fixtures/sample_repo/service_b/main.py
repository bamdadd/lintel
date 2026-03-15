"""Service B - Async messaging + blob storage patterns."""
import boto3
from kafka import KafkaProducer, KafkaConsumer
import json

producer = KafkaProducer(
    bootstrap_servers=["kafka:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
)

consumer = KafkaConsumer(
    "user-events",
    bootstrap_servers=["kafka:9092"],
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
)

s3_client = boto3.client("s3")


def publish_user_event(user_data: dict) -> None:
    """Publish user event to Kafka."""
    producer.send("user-events", value=user_data)


def upload_report(report_data: bytes, filename: str) -> None:
    """Upload report to S3."""
    s3_client.put_object(Bucket="reports", Key=filename, Body=report_data)


def process_events() -> None:
    """Consume events from Kafka."""
    for message in consumer:
        print(f"Received: {message.value}")
