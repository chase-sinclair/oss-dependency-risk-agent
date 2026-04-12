"""
Databricks SQL execution tool for the OSS Risk Agent.

Executes a SQL statement against the configured SQL Warehouse and returns
the result as a list of dicts (column_name -> value).

All values from the Databricks API arrive as strings or None; callers are
responsible for casting to float/int as needed.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _extract_warehouse_id(http_path: str) -> str:
    """
    Extract the warehouse ID from a Databricks HTTP path.

    e.g. '/sql/1.0/warehouses/11bd1ba7445b1a22' -> '11bd1ba7445b1a22'
    """
    return http_path.rstrip("/").split("/")[-1]


def query_databricks(
    sql: str,
    warehouse_id: Optional[str] = None,
) -> list[dict]:
    """
    Execute a SQL statement against the Databricks SQL Warehouse.

    Args:
        sql:           SQL statement to execute.
        warehouse_id:  Databricks SQL Warehouse ID.  Defaults to the last
                       path segment of DATABRICKS_HTTP_PATH.

    Returns:
        List of row dicts: [{column_name: value, ...}, ...].
        Values are strings or None as returned by the Databricks API.

    Raises:
        RuntimeError: if the statement fails or the warehouse is unreachable.
    """
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    token = os.environ["DATABRICKS_TOKEN"]

    if warehouse_id is None:
        http_path = os.environ.get("DATABRICKS_HTTP_PATH", "")
        warehouse_id = _extract_warehouse_id(http_path)

    client = WorkspaceClient(host=host, token=token)

    logger.debug("Executing SQL on warehouse=%s:\n%s", warehouse_id, sql[:300])

    response = client.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="50s",
    )

    state = response.status.state
    if state != StatementState.SUCCEEDED:
        err = getattr(response.status, "error", None)
        raise RuntimeError(
            f"Databricks statement failed (state={state}): {err}"
        )

    # No rows returned
    if (
        response.result is None
        or response.result.data_array is None
        or response.manifest is None
    ):
        return []

    columns = [col.name for col in response.manifest.schema.columns]
    return [
        dict(zip(columns, row))
        for row in response.result.data_array
    ]
