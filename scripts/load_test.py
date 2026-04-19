"""Load test script — creates many workflows quickly.

Usage:
    python scripts/load_test.py --count 3000000
    python scripts/load_test.py --count 10000 --batch 500
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
import uuid

from temporalio.client import Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


async def main(count: int, batch_size: int, address: str, task_queue: str) -> None:
    client = await Client.connect(address)

    logger.info("Starting %d workflows in batches of %d...", count, batch_size)
    started = 0
    t0 = time.time()

    while started < count:
        batch = min(batch_size, count - started)
        tasks = []
        for _ in range(batch):
            wf_id = f"load-test-{uuid.uuid4().hex[:12]}"
            tasks.append(
                client.start_workflow(
                    "PingWorkflow",
                    f"load test {started}",
                    id=wf_id,
                    task_queue=task_queue,
                )
            )
        await asyncio.gather(*tasks)
        started += batch

        elapsed = time.time() - t0
        rate = started / elapsed if elapsed > 0 else 0
        logger.info(
            "  %d / %d started (%.0f/s, elapsed %.1fs)",
            started, count, rate, elapsed,
        )

    elapsed = time.time() - t0
    logger.info(
        "Done: %d workflows in %.1fs (%.0f/s)",
        count, elapsed, count / elapsed if elapsed > 0 else 0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load test — create many workflows")
    parser.add_argument("--count", type=int, default=10000, help="Number of workflows to create")
    parser.add_argument("--batch", type=int, default=200, help="Batch size for concurrent starts")
    parser.add_argument("--address", default=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"), help="Temporal address")
    parser.add_argument("--queue", default="hello-world-task-queue", help="Task queue name")
    args = parser.parse_args()

    asyncio.run(main(args.count, args.batch, args.address, args.queue))
