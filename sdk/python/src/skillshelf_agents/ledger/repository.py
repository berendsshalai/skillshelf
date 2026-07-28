from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import LedgerDatabase
from .models import (
    ErrorRecord,
    RunRecord,
    RunStatus,
    TERMINAL_RUN_STATUSES,
    ToolCallRecord,
    ToolCallStatus,
    UsageRecord,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RunLedger:
    def __init__(self, database: Path) -> None:
        self.database = LedgerDatabase(database)

    def create_run(
        self,
        *,
        run_id: str,
        trace_id: str,
        session_id: str,
        canonical_input: dict[str, Any],
        configuration_version: str,
        original_run_id: str | None = None,
    ) -> None:
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO runs
                (run_id,trace_id,session_id,status,canonical_input,configuration_version,
                 original_run_id,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    trace_id,
                    session_id,
                    RunStatus.CREATED,
                    json.dumps(canonical_input, sort_keys=True),
                    configuration_version,
                    original_run_id,
                    now,
                    now,
                ),
            )

    def transition(self, run_id: str, status: RunStatus) -> None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            current = RunStatus(row["status"])
            if current in TERMINAL_RUN_STATUSES:
                raise ValueError(f"terminal run {run_id} cannot transition from {current}")
            connection.execute(
                "UPDATE runs SET status=?,updated_at=? WHERE run_id=?",
                (status, _now(), run_id),
            )

    def start_tool_call(
        self,
        *,
        run_id: str,
        tool_call_id: str,
        agent_id: str,
        tool_name: str,
        arguments_digest: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_calls
                (tool_call_id,run_id,agent_id,tool_name,status,arguments_digest,started_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    tool_call_id,
                    run_id,
                    agent_id,
                    tool_name,
                    ToolCallStatus.RUNNING,
                    arguments_digest,
                    _now(),
                ),
            )

    def finish_tool_call(
        self,
        tool_call_id: str,
        *,
        status: ToolCallStatus,
        output_digest: str | None = None,
        error_code: str | None = None,
    ) -> None:
        if status == ToolCallStatus.RUNNING:
            raise ValueError("a finished tool call cannot remain running")
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE tool_calls SET status=?,output_digest=?,error_code=?,completed_at=?
                WHERE tool_call_id=? AND status=?
                """,
                (status, output_digest, error_code, _now(), tool_call_id, ToolCallStatus.RUNNING),
            )
            if cursor.rowcount != 1:
                raise KeyError(tool_call_id)

    def record_usage(
        self,
        *,
        run_id: str,
        agent_id: str,
        request_id: str,
        input_tokens: int,
        cached_tokens: int,
        reasoning_tokens: int,
        output_tokens: int,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO usage_records
                (run_id,request_id,agent_id,input_tokens,cached_tokens,reasoning_tokens,
                 output_tokens,total_tokens)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    request_id,
                    agent_id,
                    input_tokens,
                    cached_tokens,
                    reasoning_tokens,
                    output_tokens,
                    input_tokens + output_tokens,
                ),
            )

    def record_error(self, run_id: str, *, code: str, message: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO errors(run_id,code,message,created_at) VALUES (?,?,?,?)",
                (run_id, code, message, _now()),
            )

    def inspect_run(self, run_id: str) -> RunRecord:
        with self.database.connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            tools = connection.execute(
                """
                SELECT tool_call_id,agent_id,tool_name,status,arguments_digest,output_digest,
                       started_at,completed_at,error_code
                FROM tool_calls WHERE run_id=? ORDER BY started_at
                """,
                (run_id,),
            ).fetchall()
            usage = connection.execute(
                """
                SELECT request_id,agent_id,input_tokens,cached_tokens,reasoning_tokens,
                       output_tokens,total_tokens
                FROM usage_records WHERE run_id=? ORDER BY id
                """,
                (run_id,),
            ).fetchall()
            errors = connection.execute(
                "SELECT code,message,created_at FROM errors WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        return RunRecord(
            run_id=run["run_id"],
            trace_id=run["trace_id"],
            session_id=run["session_id"],
            status=run["status"],
            canonical_input=json.loads(run["canonical_input"]),
            configuration_version=run["configuration_version"],
            created_at=run["created_at"],
            updated_at=run["updated_at"],
            tool_calls=[ToolCallRecord.model_validate(dict(item)) for item in tools],
            usage=[UsageRecord.model_validate(dict(item)) for item in usage],
            errors=[ErrorRecord.model_validate(dict(item)) for item in errors],
        )

    def list_runs(self, *, limit: int = 100) -> list[RunRecord]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self.database.connect() as connection:
            ids = [
                row["run_id"]
                for row in connection.execute(
                    "SELECT run_id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            ]
        return [self.inspect_run(run_id) for run_id in ids]
