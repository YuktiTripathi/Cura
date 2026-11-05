"""Pull the "answer" text out of a JSON object while it is still being written.

The answer model returns one JSON object whose first field is "answer". A client can start reading that text
while the rest of the object (claims, follow up questions) is still arriving. This decodes the JSON string
incrementally and hands over only the new characters of the answer."""

from __future__ import annotations

import re
from collections.abc import Callable

_START = re.compile(r'"answer"\s*:\s*"')
_SIMPLE = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class AnswerFieldStreamer:
    def __init__(self, on_delta: Callable[[str], None]):
        self._on_delta = on_delta
        self._head = ""
        self._in_answer = False
        self._done = False
        self._pending = ""  # an escape sequence split across two chunks
        self.emitted = False

    def feed(self, chunk: str) -> None:
        if self._done or not chunk:
            return
        if not self._in_answer:
            self._head += chunk
            match = _START.search(self._head)
            if not match:
                self._head = self._head[-24:]
                return
            chunk = self._head[match.end():]
            self._head = ""
            self._in_answer = True
        text = self._pending + chunk
        self._pending = ""
        out: list[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == '"':
                self._done = True
                break
            if ch != "\\":
                out.append(ch)
                i += 1
                continue
            if i + 1 >= len(text):
                self._pending = text[i:]
                break
            nxt = text[i + 1]
            if nxt == "u":
                if i + 6 > len(text):
                    self._pending = text[i:]
                    break
                try:
                    out.append(chr(int(text[i + 2:i + 6], 16)))
                except ValueError:
                    pass
                i += 6
                continue
            out.append(_SIMPLE.get(nxt, nxt))
            i += 2
        if out:
            self.emitted = True
            self._on_delta("".join(out))
