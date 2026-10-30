"""Non-blocking HTTPS POST, stepped across multiple frames.

Built on asyncio.open_connection(ssl=True), which works on this firmware
(verified live). The connection is kept alive across separate short
asyncio runs rather than one long blocking call, so the badge's frame
loop can keep redrawing (screen, LEDs, matrix animation) while a
request is in flight.

This exists because this firmware's display only presents what's drawn
once update() *returns* each frame (confirmed live: nothing drawn mid-call
during the old synchronous urequests.post() ever reached the screen for
the whole multi-second LLM round-trip — it just looked frozen/blank).

Both OpenRouter and Tavily send `Transfer-Encoding: chunked` and
`Connection: close` (verified live) — read-until-EOF always gives the
complete framed response, then the chunk envelopes are stripped once.

Usage: a generator — drive with next() once per frame (or `yield from`
it from another generator). Returns (status_code, body_bytes) via
StopIteration.value / the yield-from expression; raises on failure.
"""

import asyncio

READ_CHUNK = 1024
STEP_TIMEOUT_S = 0.05  # per-frame budget for a single non-blocking read attempt


def _dechunk(body):
    out = b""
    i = 0
    while i < len(body):
        nl = body.find(b"\r\n", i)
        if nl == -1:
            break
        size = int(body[i:nl], 16)
        if size == 0:
            break
        start = nl + 2
        out += body[start:start + size]
        i = start + size + 2  # skip the data and its trailing \r\n
    return out


def post(host, path, headers, body, port=443):
    """Generator: yields "pending" repeatedly; returns (status_code, body_bytes)."""
    loop = asyncio.get_event_loop()

    async def _connect_and_send():
        reader, writer = await asyncio.open_connection(host, port, ssl=True)
        header_lines = "".join("%s: %s\r\n" % (k, v) for k, v in headers.items())
        request_head = (
            "POST %s HTTP/1.1\r\n"
            "Host: %s\r\n"
            "%s"
            "Content-Length: %d\r\n"
            "Connection: close\r\n"
            "\r\n"
        ) % (path, host, header_lines, len(body))
        writer.write(request_head.encode() + body)
        await writer.drain()
        return reader, writer

    reader, writer = loop.run_until_complete(_connect_and_send())
    yield "pending"

    async def _read_chunk():
        try:
            return await asyncio.wait_for(reader.read(READ_CHUNK), STEP_TIMEOUT_S)
        except asyncio.TimeoutError:
            return None

    raw = b""
    while True:
        chunk = loop.run_until_complete(_read_chunk())
        if chunk == b"":
            break  # EOF — server closed the connection
        if chunk:
            raw += chunk
        yield "pending"

    try:
        writer.close()
    except Exception:
        pass

    header_end = raw.find(b"\r\n\r\n")
    if header_end == -1:
        raise ValueError("malformed HTTP response: no header terminator")
    header_block = raw[:header_end]
    body_bytes = raw[header_end + 4:]
    status_line = header_block.split(b"\r\n", 1)[0]
    status_code = int(status_line.split(b" ")[1])
    if b"chunked" in header_block.lower():
        body_bytes = _dechunk(body_bytes)
    return status_code, body_bytes
