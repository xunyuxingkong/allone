"""Process isolation for bounded Query Case execution."""

from __future__ import annotations

import multiprocessing
import time
from multiprocessing.connection import Connection
from typing import Any, Callable


class QueryTimeoutError(TimeoutError):
    """A Query Case exceeded its declared execution timeout."""

    def __init__(self, timeout_seconds: float, current_step_id: str | None) -> None:
        self.timeout_seconds = timeout_seconds
        self.current_step_id = current_step_id
        self.completed_steps: tuple[dict[str, Any], ...] = ()
        super().__init__("QUERY_TIMEOUT")


class QueryWorkerError(RuntimeError):
    """A Query Worker exited without returning a result."""


def parse_timeout_seconds(value: str) -> float:
    unit = value[-2:] if value.endswith("ms") else value[-1:]
    amount = int(value[:-2] if unit == "ms" else value[:-1])
    multiplier = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}[unit]
    return amount * multiplier


def supervise_worker(
    target: Callable[..., None],
    args: tuple[Any, ...],
    *,
    timeout_seconds: float,
    terminate_grace_seconds: float = 0.5,
) -> dict[str, Any]:
    """Run a top-level worker target and terminate it when its deadline expires.

    Worker targets receive a one-way send connection as their final argument and
    may send ``("step_started", step_id)`` / ``("step_completed", report)``
    events followed by ``("result", report)`` or ``("fatal", type, message)``.
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=target, args=(*args, sender))
    started = time.monotonic()
    current_step_id: str | None = None
    completed_steps: list[dict[str, Any]] = []
    result: dict[str, Any] | None = None
    fatal: tuple[str, str] | None = None
    try:
        process.start()
        sender.close()
        deadline = started + timeout_seconds
        while process.is_alive() or receiver.poll():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.terminate()
                process.join(terminate_grace_seconds)
                if process.is_alive():
                    process.kill()
                    process.join()
                raise QueryTimeoutError(timeout_seconds, current_step_id)
            if receiver.poll(min(remaining, 0.1)):
                try:
                    message = receiver.recv()
                except EOFError:
                    break
                event = message[0]
                if event == "step_started":
                    current_step_id = message[1]
                elif event == "step_completed":
                    completed_steps.append(message[1])
                    current_step_id = None
                elif event == "result":
                    result = message[1]
                    break
                elif event == "fatal":
                    fatal = (message[1], message[2])
                    break
            elif not process.is_alive():
                break
        process.join()
        if result is not None:
            return result
        if fatal is not None:
            raise QueryWorkerError(f"{fatal[0]}: {fatal[1]}")
        raise QueryWorkerError(f"QUERY_WORKER_EXITED:{process.exitcode}")
    except QueryTimeoutError as error:
        error.completed_steps = tuple(completed_steps)
        raise
    finally:
        if process.is_alive():
            process.terminate()
            process.join(terminate_grace_seconds)
            if process.is_alive():
                process.kill()
                process.join()
        receiver.close()
        try:
            sender.close()
        except OSError:
            pass
