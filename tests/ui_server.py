"""Isolated E2E fixture. Never touches the user's configuration or remote models."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import queue
import tempfile

import uvicorn

from vn_pet.activity import Companion
from vn_pet.server import create_app
from vn_pet.settings import Store


def main():
    with tempfile.TemporaryDirectory(prefix="vn-e2e-") as directory:
        events = queue.Queue()
        companion = Companion(Store(Path(directory)), events)
        async def generate(*args):
            await asyncio.sleep(.1)
            return "忙了一会儿，也记得歇一歇。我在这里陪着你。"
        companion.models.generate = generate
        companion.collector.collect = lambda *a, **kw: ({"signals": {}}, [])
        app = create_app(companion, "ui-test-token", "http://127.0.0.1:18765", events)
        original = app.router.lifespan_context
        async def deliveries():
            while True:
                await asyncio.sleep(.02)
                while not events.empty():
                    kind, payload, ack = events.get_nowait()
                    if kind == "speech" and not ack.done():
                        result = companion.display(payload, lambda *args: True)
                        ack.set_result(result)
        @asynccontextmanager
        async def lifespan(app):
            async with original(app):
                task = asyncio.create_task(deliveries())
                try:
                    yield
                finally:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        app.router.lifespan_context = lifespan
        uvicorn.run(app, host="127.0.0.1", port=18765, access_log=False, log_level="error")


if __name__ == "__main__":
    main()
