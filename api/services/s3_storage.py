from __future__ import annotations
import io

import boto3
import botocore
from botocore.config import Config as BotoConfig

import config


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT_URL,
        aws_access_key_id=config.S3_ACCESS_KEY_ID,
        aws_secret_access_key=config.S3_SECRET_ACCESS_KEY,
        config=BotoConfig(
            signature_version="s3v4",
            region_name="ru-central1",
        ),
    )


def upload_bytes(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    client = _s3_client()
    client.put_object(
        Bucket=config.S3_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )
    return f"{config.S3_PUBLIC_URL}/{key}"


def delete_object(key: str) -> None:
    client = _s3_client()
    try:
        client.delete_object(Bucket=config.S3_BUCKET_NAME, Key=key)
    except Exception:
        pass


def s3_key_from_url(url: str | None) -> str | None:
    if not url or not url.startswith("http") or not config.S3_PUBLIC_URL:
        return None
    base = config.S3_PUBLIC_URL.rstrip("/") + "/"
    if not url.startswith(base):
        return None
    return url[len(base):]
