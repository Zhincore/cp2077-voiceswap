import asyncio
import os
from http import HTTPStatus

import websockets

import config

WEBUI_PATH = os.path.join(os.getcwd(), config.WEBUI_PATH)
FILE_TYPES = {
    "html": "text/html",
    "js": "text/javascript",
    "css": "text/css",
}


def _send_file(path: str):
    filetype = FILE_TYPES.get(path.split(".")[-1], "application/octet-stream")

    with open(path, "rb") as f:
        return (
            HTTPStatus.OK,
            [
                ["Content-Type", filetype],
            ],
            f.read(),
        )


async def _websocket_handler(websocket):
    async for message in websocket:
        await websocket.send(message)


async def _request_handler(path, request):
    if path == "/socket":
        return

    file_path = os.path.join(WEBUI_PATH, "." + path)
    if path == "/" or os.path.isfile(file_path):
        return _send_file(
            os.path.join(file_path, "index.html") if path == "/" else file_path
        )

    return HTTPStatus.NOT_FOUND, [], b"Path not found"


async def _main():
    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    async with websockets.serve(
        _websocket_handler, "localhost", 3000, process_request=_request_handler
    ) as server:
        addr = server.sockets[0].getsockname()
        print(f"Serving on http://localhost:{addr[1]}")
        await stop


def main():
    """Main function of the program."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
