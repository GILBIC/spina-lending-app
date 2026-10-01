"""Bounded, volatile images. The eviction thread never accesses SQL or the network."""

from __future__ import annotations

import struct
import threading
import time
import zlib
from dataclasses import dataclass
from uuid import UUID

MAX_FRAME_BYTES = 524288


class ScreenShareError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def validate_png(data: bytes) -> None:
    if len(data) > MAX_FRAME_BYTES:
        raise ScreenShareError(413, "Screen image is too large.")
    invalid = ScreenShareError(
        422, "A valid PNG no larger than 1024 by 1024 is required."
    )
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise invalid
    offset, width, height, color = 8, 0, 0, 0
    channels = {2: 3, 6: 4}
    image_data = bytearray()
    ended = False
    while offset + 12 <= len(data):
        size = struct.unpack_from("!I", data, offset)[0]
        kind = data[offset + 4 : offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise invalid
        payload = data[offset + 8 : end - 4]
        if zlib.crc32(kind + payload) != struct.unpack_from("!I", data, end - 4)[0]:
            raise invalid
        if kind in (b"acTL", b"fcTL", b"fdAT") or (
            not kind[0] & 32 and kind not in (b"IHDR", b"PLTE", b"IDAT", b"IEND")
        ):
            raise invalid
        if offset == 8:
            if kind != b"IHDR" or size != 13:
                raise invalid
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack("!IIBBBBB", payload)
            )
            if (
                not (1 <= width <= 1024 and 1 <= height <= 1024)
                or depth != 8
                or color not in channels
                or compression
                or filtering
                or interlace != 0
            ):
                raise invalid
        elif kind == b"IHDR":
            raise invalid
        if kind == b"IDAT":
            image_data.extend(payload)
        if kind == b"IEND":
            if size or end != len(data) or not image_data:
                raise invalid
            ended = True
            break
        offset = end
    if not ended:
        raise invalid
    try:
        decoder = zlib.decompressobj()
        # Browser canvas and Flutter emit noninterlaced 8-bit RGB/RGBA.
        stride = width * channels[color] + 1
        limit = stride * height
        raster = decoder.decompress(image_data, limit + 1)
        if len(raster) != limit or not decoder.eof or decoder.unused_data:
            raise invalid
        if any(raster[offset] > 4 for offset in range(0, limit, stride)):
            raise invalid
    except zlib.error:
        raise invalid from None


@dataclass(frozen=True)
class Frame:
    generation: int
    sequence: int
    data: bytes
    deadline: float


class FrameCache:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._condition = threading.Condition(self.lock)
        self._frames: dict[UUID, Frame] = {}
        self._closed = False
        self._thread: threading.Thread | None = None

    @property
    def retained_bytes(self) -> int:
        with self.lock:
            return sum(len(frame.data) for frame in self._frames.values())

    def put(self, key: UUID, generation: int, sequence: int, data: bytes) -> None:
        with self.lock:
            if self._closed:
                raise ScreenShareError(409, "Screen sharing has stopped.")
            if key not in self._frames and len(self._frames) >= 2:
                raise ScreenShareError(429, "Two screens are already being shared.")
            self._frames[key] = Frame(generation, sequence, data, time.monotonic() + 3)
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._evict, daemon=True, name="spina-screen-expiry"
                )
                self._thread.start()
            self._condition.notify_all()

    def get(self, key: UUID) -> Frame | None:
        with self.lock:
            frame = self._frames.get(key)
            if frame and frame.deadline <= time.monotonic():
                self._frames.pop(key, None)
                return None
            return frame

    def clear(self, key: UUID) -> None:
        with self.lock:
            self._frames.pop(key, None)
            self._condition.notify_all()

    def _evict(self) -> None:
        with self._condition:
            while not self._closed:
                now = time.monotonic()
                for key in [
                    key for key, value in self._frames.items() if value.deadline <= now
                ]:
                    del self._frames[key]
                wait = min(
                    (value.deadline - now for value in self._frames.values()),
                    default=None,
                )
                self._condition.wait(timeout=wait)

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._frames.clear()
            self._condition.notify_all()
        if self._thread:
            self._thread.join(timeout=1)
