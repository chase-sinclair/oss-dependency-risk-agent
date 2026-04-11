"""
Reusable S3 client wrapper for the OSS Dependency Risk Agent bronze layer.

Wraps boto3 with:
- Retry logic on uploads (tenacity exponential back-off)
- dry_run mode that logs intended writes without touching S3
- Consistent S3 key construction matching the Bronze path convention:
      {S3_BRONZE_PREFIX}/raw/{org}/{repo}/{date}/{date}-{hour}.json.gz
"""
import logging
import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Exceptions that warrant a retry (transient AWS errors)
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return status in _RETRYABLE_STATUS_CODES
    return isinstance(exc, (ConnectionError, TimeoutError))


class S3Client:
    """
    Thin wrapper around boto3 S3 operations.

    Args:
        bucket:   S3 bucket name. Defaults to the S3_BRONZE_BUCKET env var.
        dry_run:  When True, log uploads without executing them.
    """

    def __init__(self, bucket: str | None = None, dry_run: bool = False) -> None:
        self.bucket = bucket or os.environ["S3_BRONZE_BUCKET"]
        self.dry_run = dry_run
        self._client = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        logger.debug(
            "S3Client initialised (bucket=%s, dry_run=%s)", self.bucket, self.dry_run
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/gzip",
    ) -> None:
        """
        Upload raw bytes to S3 at the given key.

        In dry_run mode, logs the intended write and returns immediately.
        """
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would upload %d bytes -> s3://%s/%s",
                len(data),
                self.bucket,
                key,
            )
            return

        self._upload_with_retry(key, data, content_type)
        logger.debug("Uploaded %d bytes -> s3://%s/%s", len(data), self.bucket, key)

    def key_exists(self, key: str) -> bool:
        """Return True if the S3 key already exists (HEAD request)."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey"):
                return False
            raise

    @staticmethod
    def build_key(org: str, repo: str, date_str: str, hour: int) -> str:
        """
        Build the canonical S3 key for a single hour of filtered events.

        Pattern:
            {S3_BRONZE_PREFIX}/raw/{org}/{repo}/{date_str}/{date_str}-{hour}.json.gz

        Note: always uses forward slashes regardless of OS.
        """
        prefix = os.environ.get("S3_BRONZE_PREFIX", "github-archive/").rstrip("/")
        return f"{prefix}/raw/{org}/{repo}/{date_str}/{date_str}-{hour}.json.gz"

    @staticmethod
    def build_sentinel_key(date_str: str, hour: int) -> str:
        """
        Build the key for the completion sentinel marker.

        Written after a successful hour-file upload so backfills can skip
        already-processed hours without listing per-project keys.
        """
        prefix = os.environ.get("S3_BRONZE_PREFIX", "github-archive/").rstrip("/")
        return f"{prefix}/_meta/done/{date_str}-{hour:02d}.done"

    # ── Internal helpers ───────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((ClientError, ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _upload_with_retry(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
