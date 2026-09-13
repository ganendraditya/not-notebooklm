"""
S3-Compatible Storage Adapter (Cloudflare R2, MinIO, AWS S3) for NotbookLM.
Provides unified, decoupled object storage synchronization alongside local disk fallback.
"""

import os
import logging
import threading
from typing import Optional, List, Dict, Any

logger = logging.getLogger("uvicorn.error")

_S3_CLIENT = None
_S3_INITIALIZED = False
_S3_LOCK = threading.Lock()


def is_s3_enabled() -> bool:
    """Checks if S3 storage is enabled and required configuration credentials are set."""
    storage_type = os.getenv("STORAGE_TYPE", "local").strip().lower()
    if storage_type != "s3":
        return False
    endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
    access_key = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    bucket = os.getenv("S3_BUCKET_NAME", "").strip()
    return bool(endpoint and access_key and secret_key and bucket)


def get_bucket_name() -> str:
    """Returns the configured S3 bucket name."""
    return os.getenv("S3_BUCKET_NAME", "not-notebooklm").strip()


def get_s3_client():
    """
    Initializes and returns a cached boto3 S3 client for Cloudflare R2 / MinIO / AWS S3.
    Returns None if boto3 is not installed or S3 is not configured.
    """
    global _S3_CLIENT, _S3_INITIALIZED
    if not is_s3_enabled():
        return None

    if _S3_INITIALIZED and _S3_CLIENT is not None:
        return _S3_CLIENT

    with _S3_LOCK:
        if _S3_INITIALIZED and _S3_CLIENT is not None:
            return _S3_CLIENT
        _S3_INITIALIZED = True

        try:
            import boto3
            from botocore.config import Config

            endpoint_url = os.getenv("S3_ENDPOINT_URL", "").strip()
            access_key = os.getenv("S3_ACCESS_KEY_ID", "").strip()
            secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
            region = os.getenv("S3_REGION", "auto").strip() or "auto"

            # Cloudflare R2 and MinIO require signature version s3v4 and path/virtual-host style handling
            s3_config = Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=15,
                read_timeout=60,
            )

            _S3_CLIENT = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
                config=s3_config,
            )
            logger.info(f"[StorageAdapter] Successfully initialized S3 client for endpoint: {endpoint_url}")

            # Automatically verify and create bucket if missing (ideal for local MinIO & testing)
            try:
                b_name = get_bucket_name()
                _S3_CLIENT.head_bucket(Bucket=b_name)
            except Exception:
                try:
                    if region in ("us-east-1", "auto", ""):
                        _S3_CLIENT.create_bucket(Bucket=b_name)
                    else:
                        _S3_CLIENT.create_bucket(
                            Bucket=b_name,
                            CreateBucketConfiguration={"LocationConstraint": region},
                        )
                    logger.info(f"[StorageAdapter] Automatically created S3 bucket '{b_name}' on {endpoint_url}")
                except Exception as be:
                    logger.debug(f"[StorageAdapter] Bucket check/create note: {be}")

            return _S3_CLIENT
        except ImportError:
            logger.warning("[StorageAdapter] 'boto3' library is not installed. Run: pip install boto3")
            _S3_CLIENT = None
            return None
        except Exception as e:
            logger.error(f"[StorageAdapter] Failed to initialize S3 client: {e}")
            _S3_CLIENT = None
            return None


def upload_file(local_path: str, s3_key: str, content_type: Optional[str] = None) -> bool:
    """Uploads a local file to S3 storage bucket. Gracefully skips if S3 is disabled."""
    client = get_s3_client()
    if not client or not os.path.exists(local_path):
        return False

    bucket = get_bucket_name()
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    elif local_path.lower().endswith(".pdf"):
        extra_args["ContentType"] = "application/pdf"
    elif local_path.lower().endswith(".png"):
        extra_args["ContentType"] = "image/png"
    elif local_path.lower().endswith((".jpg", ".jpeg")):
        extra_args["ContentType"] = "image/jpeg"
    elif local_path.lower().endswith(".txt"):
        extra_args["ContentType"] = "text/plain"

    try:
        client.upload_file(local_path, bucket, s3_key, ExtraArgs=extra_args if extra_args else None)
        logger.info(f"[StorageAdapter] Uploaded {local_path} -> s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        logger.error(f"[StorageAdapter] Failed to upload {local_path} to s3://{bucket}/{s3_key}: {e}")
        return False


def upload_bytes(data: bytes, s3_key: str, content_type: Optional[str] = None) -> bool:
    """Uploads in-memory bytes directly to S3 storage bucket."""
    client = get_s3_client()
    if not client:
        return False

    bucket = get_bucket_name()
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    try:
        client.put_object(Bucket=bucket, Key=s3_key, Body=data, **extra_args)
        logger.info(f"[StorageAdapter] Uploaded {len(data)} bytes -> s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        logger.error(f"[StorageAdapter] Failed to upload bytes to s3://{bucket}/{s3_key}: {e}")
        return False


def download_file(s3_key: str, target_local_path: str) -> bool:
    """Downloads an object from S3 storage to target_local_path."""
    client = get_s3_client()
    if not client:
        return False

    bucket = get_bucket_name()
    os.makedirs(os.path.dirname(os.path.abspath(target_local_path)), exist_ok=True)

    try:
        client.download_file(bucket, s3_key, target_local_path)
        logger.info(f"[StorageAdapter] Downloaded s3://{bucket}/{s3_key} -> {target_local_path}")
        return True
    except Exception as e:
        logger.warning(f"[StorageAdapter] Failed to download s3://{bucket}/{s3_key}: {e}")
        return False


def ensure_local_copy(s3_key: str, target_local_path: str) -> bool:
    """
    Ensures a local copy of the file exists.
    If file already exists on disk, returns True immediately.
    If missing and S3 is enabled, downloads from S3.
    """
    if os.path.exists(target_local_path) and os.path.getsize(target_local_path) > 0:
        return True

    if is_s3_enabled():
        return download_file(s3_key, target_local_path)
    return False


def delete_file(s3_key: str) -> bool:
    """Deletes an object from S3 storage bucket."""
    if not is_s3_enabled():
        return False

    client = get_s3_client()
    if not client:
        return False

    bucket = get_bucket_name()
    try:
        client.delete_object(Bucket=bucket, Key=s3_key)
        logger.info(f"[StorageAdapter] Deleted s3://{bucket}/{s3_key}")
        return True
    except Exception as e:
        logger.warning(f"[StorageAdapter] Failed to delete s3://{bucket}/{s3_key}: {e}")
        return False


def delete_files_with_prefix(prefix: str) -> int:
    """Bulk deletes all objects matching the specified key prefix."""
    if not is_s3_enabled() or not prefix or not prefix.strip():
        return 0

    client = get_s3_client()
    if not client:
        return 0

    bucket = get_bucket_name()
    deleted_count = 0
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            delete_keys = [{"Key": obj["Key"]} for obj in objects]
            res = client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
            deleted_count += len(res.get("Deleted", []))
            logger.info(f"[StorageAdapter] Batch deleted {len(delete_keys)} objects with prefix '{prefix}'")
    except Exception as e:
        logger.error(f"[StorageAdapter] Error batch deleting prefix '{prefix}': {e}")

    return deleted_count


def generate_presigned_url(s3_key: str, expiration_sec: int = 3600) -> Optional[str]:
    """Generates a temporary pre-signed download URL directly from S3 / Cloudflare R2."""
    client = get_s3_client()
    if not client:
        return None

    bucket = get_bucket_name()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=expiration_sec,
        )
        return url
    except Exception as e:
        logger.warning(f"[StorageAdapter] Failed to generate presigned URL for {s3_key}: {e}")
        return None
