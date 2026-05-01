import logging
import asyncio
from typing import List

class SSELogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.queues: List[asyncio.Queue] = []

    def emit(self, record):
        log_entry = self.format(record)
        for queue in self.queues:
            # Não podemos usar await aqui, então usamos call_soon_threadsafe se estiver em outra thread
            # Mas o FastAPI roda em loop de eventos.
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(queue.put_nowait, log_entry)
            except Exception:
                pass

    def add_queue(self, queue: asyncio.Queue):
        self.queues.append(queue)

    def remove_queue(self, queue: asyncio.Queue):
        if queue in self.queues:
            self.queues.remove(queue)

sse_handler = SSELogHandler()
sse_handler.setFormatter(logging.Formatter('%(message)s'))

def setup_sse_logging():
    logger = logging.getLogger("VisionAlign")
    logger.addHandler(sse_handler)
    return sse_handler
