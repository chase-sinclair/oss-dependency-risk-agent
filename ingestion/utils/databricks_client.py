"""
Databricks SDK wrapper for the OSS Dependency Risk Agent.

Handles notebook uploads, job creation/update, run triggering,
and run status polling — all with dry_run support and proper logging.

Public API:
    DatabricksClient
        .upload_notebook(local_path, remote_path)
        .create_or_update_job(job_config)
        .trigger_run(job_id, notebook_params)
        .wait_for_run(run_id, poll_interval, timeout)
        .get_job_by_name(name)
        .get_run_url(run_id)
"""
# Defers evaluation of all type annotations so that Databricks SDK types
# referenced in signatures (RunResultState, etc.) are not resolved at class
# definition time — the SDK is imported lazily inside __init__.
from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

# Databricks SDK imports are deferred to class instantiation so that
# --help, --dry-run checks, and unit tests all work without the package
# installed.  The SDK is only required when DatabricksClient() is created.
def _import_sdk():
    """Lazy-import the Databricks SDK; raises ImportError with a helpful message."""
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.jobs import RunLifeCycleState, RunResultState
        from databricks.sdk.service.workspace import ImportFormat, Language
        return WorkspaceClient, RunLifeCycleState, RunResultState, ImportFormat, Language
    except ImportError as exc:
        raise ImportError(
            "databricks-sdk is not installed. "
            "Run: pip install databricks-sdk>=0.32.0"
        ) from exc

logger = logging.getLogger(__name__)


def _strip_meta_keys(obj: object) -> object:
    """
    Recursively remove any key starting with '_' from dicts.

    Used to clean job config dicts before sending to the Databricks API —
    strips comment/metadata keys (e.g. _comment, _metadata) added for
    human readability.  Empty dicts produced by stripping are also removed
    so that disabled config blocks (like a fully-commented schedule) do not
    send empty objects to the API.
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k.startswith("_"):
                continue
            cleaned = _strip_meta_keys(v)
            if cleaned == {}:   # drop config blocks that became empty
                continue
            result[k] = cleaned
        return result
    if isinstance(obj, list):
        return [_strip_meta_keys(item) for item in obj]
    return obj


class DatabricksRunError(RuntimeError):
    """Raised when a Databricks job run finishes in a non-success state."""


class DatabricksClient:
    """
    Thin wrapper around databricks-sdk with dry_run and retry support.

    Args:
        host:     Databricks workspace URL (e.g. https://dbc-xxx.cloud.databricks.com).
                  Defaults to DATABRICKS_HOST env var.
        token:    Personal access token.
                  Defaults to DATABRICKS_TOKEN env var.
        dry_run:  When True, log all operations but skip writes.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self.host = (host or os.environ["DATABRICKS_HOST"]).rstrip("/")
        self.dry_run = dry_run

        # Resolve SDK types now so missing-package errors surface at init time
        (
            WorkspaceClient,
            self._RunLifeCycleState,
            self._RunResultState,
            self._ImportFormat,
            self._Language,
        ) = _import_sdk()

        self._sdk = WorkspaceClient(
            host=self.host,
            token=token or os.environ["DATABRICKS_TOKEN"],
        )
        logger.debug(
            "DatabricksClient initialised (host=%s, dry_run=%s)", self.host, dry_run
        )

    # ── Notebook management ────────────────────────────────────────────────────

    def upload_notebook(
        self,
        local_path: str | Path,
        remote_path: str,
        overwrite: bool = True,
    ) -> None:
        """
        Upload a local .py notebook to the Databricks workspace.

        The file must begin with '# Databricks notebook source' to be
        recognised as a notebook by the workspace.

        Args:
            local_path:   Path to the local .py file.
            remote_path:  Destination workspace path, e.g.
                          '/Shared/oss-risk-agent/01_bronze_to_silver'.
            overwrite:    Replace an existing notebook at the same path.
        """
        local_path = Path(local_path)
        content = local_path.read_bytes()
        content_b64 = base64.b64encode(content).decode("utf-8")

        if self.dry_run:
            logger.info(
                "[DRY RUN] Would upload %s -> workspace:%s (%d bytes)",
                local_path.name,
                remote_path,
                len(content),
            )
            return

        self._upload_with_retry(remote_path, content_b64, overwrite)
        logger.info(
            "Uploaded notebook %s -> workspace:%s", local_path.name, remote_path
        )

    def upload_all_notebooks(
        self,
        notebooks_dir: str | Path,
        remote_base: Optional[str] = None,
    ) -> list[str]:
        """
        Upload all .py files in notebooks_dir to the workspace.

        Args:
            notebooks_dir: Local directory containing notebook .py files.
            remote_base:   Workspace destination folder.
                           Defaults to DATABRICKS_NOTEBOOK_PATH env var or
                           '/Shared/oss-risk-agent'.

        Returns:
            List of remote paths that were uploaded.
        """
        remote_base = (
            remote_base
            or os.environ.get("DATABRICKS_NOTEBOOK_PATH", "/Shared/oss-risk-agent")
        ).rstrip("/")

        notebooks_dir = Path(notebooks_dir)
        py_files = sorted(notebooks_dir.glob("*.py"))
        if not py_files:
            logger.warning("No .py files found in %s", notebooks_dir)
            return []

        uploaded: list[str] = []
        for local_path in py_files:
            stem = local_path.stem   # e.g. "01_bronze_to_silver"
            remote_path = f"{remote_base}/{stem}"
            self.upload_notebook(local_path, remote_path)
            uploaded.append(remote_path)

        logger.info(
            "Uploaded %d notebook(s) to workspace:%s", len(uploaded), remote_base
        )
        return uploaded

    # ── Job management ─────────────────────────────────────────────────────────

    def get_job_by_name(self, name: str) -> Optional[int]:
        """
        Return the job_id for a job matching the given name, or None.

        If multiple jobs share the same name, returns the first match.
        """
        for job in self._sdk.jobs.list(name=name):
            logger.debug("Found existing job '%s' (id=%d)", name, job.job_id)
            return job.job_id
        return None

    def create_or_update_job(
        self,
        job_config: dict | str | Path,
    ) -> int:
        """
        Create a new Databricks job or reset an existing one to match the config.

        Args:
            job_config: Job definition dict or path to a JSON file.

        Returns:
            job_id of the created/updated job.
        """
        if isinstance(job_config, (str, Path)):
            job_config = json.loads(Path(job_config).read_text(encoding="utf-8"))

        # Strip _metadata / _comment keys at all levels before sending to API.
        # The SDK's typed .create()/.reset() methods call .as_dict() on field
        # values and fail when they receive plain dicts.  Using the raw
        # api_client bypasses that coercion and accepts plain dicts directly.
        api_config = _strip_meta_keys(job_config)

        name = api_config.get("name", "unnamed-job")
        existing_id = self.get_job_by_name(name)

        if self.dry_run:
            verb = "update" if existing_id else "create"
            logger.info("[DRY RUN] Would %s job '%s'", verb, name)
            return existing_id or -1

        if existing_id:
            self._sdk.api_client.do(
                "POST",
                "/api/2.1/jobs/reset",
                body={"job_id": existing_id, "new_settings": api_config},
            )
            logger.info("Updated job '%s' (id=%d)", name, existing_id)
            return existing_id
        else:
            response = self._sdk.api_client.do(
                "POST",
                "/api/2.1/jobs/create",
                body=api_config,
            )
            job_id = response["job_id"]
            logger.info("Created job '%s' (id=%d)", name, job_id)
            return job_id

    # ── Run triggering ─────────────────────────────────────────────────────────

    def trigger_run(
        self,
        job_id: int,
        notebook_params: Optional[dict[str, str]] = None,
    ) -> Optional[int]:
        """
        Trigger a job run and return the run_id.

        Args:
            job_id:          Databricks job ID.
            notebook_params: Key-value pairs passed to notebook widgets.

        Returns:
            run_id, or None in dry_run mode.
        """
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would trigger job_id=%d with params=%s",
                job_id,
                notebook_params or {},
            )
            return None

        response = self._sdk.jobs.run_now(
            job_id=job_id,
            job_parameters=notebook_params or {},
        )
        run_id = response.run_id
        run_url = self.get_run_url(run_id)
        logger.info(
            "Triggered job_id=%d -> run_id=%d  %s", job_id, run_id, run_url
        )
        return run_id

    # ── Run monitoring ─────────────────────────────────────────────────────────

    def wait_for_run(
        self,
        run_id: int,
        poll_interval: int = 30,
        timeout: int = 7200,
    ) -> RunResultState:
        """
        Poll a run until it reaches a terminal state or the timeout expires.

        Args:
            run_id:         Run ID to monitor.
            poll_interval:  Seconds between status polls.
            timeout:        Maximum seconds to wait before raising TimeoutError.

        Returns:
            Final RunResultState (SUCCESS, FAILED, CANCELED, etc.)

        Raises:
            TimeoutError:          Run did not finish within timeout.
            DatabricksRunError:    Run finished but not in a success state.
        """
        deadline = time.monotonic() + timeout
        logger.info("Waiting for run_id=%d (timeout=%ds, poll=%ds)", run_id, timeout, poll_interval)

        while time.monotonic() < deadline:
            run = self._sdk.jobs.get_run(run_id=run_id)
            state = run.state.life_cycle_state

            logger.info(
                "run_id=%d  life_cycle=%s  result=%s",
                run_id,
                state.value if state else "UNKNOWN",
                run.state.result_state.value if run.state.result_state else "-",
            )

            terminal = {
                self._RunLifeCycleState.TERMINATED,
                self._RunLifeCycleState.SKIPPED,
                self._RunLifeCycleState.INTERNAL_ERROR,
            }
            if state in terminal:
                result = run.state.result_state
                if result != self._RunResultState.SUCCESS:
                    msg = (
                        f"Run {run_id} finished with result={result.value}. "
                        f"URL: {self.get_run_url(run_id)}"
                    )
                    logger.error(msg)
                    raise DatabricksRunError(msg)
                logger.info("run_id=%d completed successfully.", run_id)
                return result

            time.sleep(poll_interval)

        raise TimeoutError(
            f"run_id={run_id} did not complete within {timeout}s. "
            f"Check: {self.get_run_url(run_id)}"
        )

    def get_run_url(self, run_id: int) -> str:
        """Return the Databricks UI URL for a given run."""
        return f"{self.host}/#job/runs/{run_id}"

    # ── Internal helpers ───────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _upload_with_retry(
        self, remote_path: str, content_b64: str, overwrite: bool
    ) -> None:
        self._sdk.workspace.import_(
            path=remote_path,
            content=content_b64,
            format=self._ImportFormat.SOURCE,
            language=self._Language.PYTHON,
            overwrite=overwrite,
        )
