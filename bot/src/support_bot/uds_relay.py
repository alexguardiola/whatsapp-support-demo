"""Forward a Unix socket to a TCP endpoint on the host.

Used when a host firewall blocks Docker bridge traffic to the local model server: this relay runs
with host networking, publishes no TCP port, and only listens on a socket in a shared volume.
"""
import argparse
import asyncio
import contextlib
import os


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def serve(path: str, host: str, port: int) -> asyncio.AbstractServer:
    async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        try:
            up_r, up_w = await asyncio.open_connection(host, port)
        except OSError:
            client_w.close()
            return
        await asyncio.gather(_pipe(client_r, up_w), _pipe(up_r, client_w))

    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)
    server = await asyncio.start_unix_server(handle, path)
    os.chmod(path, 0o660)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(prog="uds-relay")
    parser.add_argument("--listen", required=True, help="unix socket path")
    parser.add_argument("--target", default="127.0.0.1:11434", help="host:port")
    args = parser.parse_args()
    host, port = args.target.rsplit(":", 1)

    async def run() -> None:
        server = await serve(args.listen, host, int(port))
        print(f"relaying {args.listen} -> {args.target}", flush=True)
        async with server:
            await server.serve_forever()

    asyncio.run(run())


if __name__ == "__main__":
    main()
