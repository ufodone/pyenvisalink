import asyncio
import base64
import logging
import re
import socket
import time

from mock_server_dsc import DscServer
from mock_server_honeywell import HoneywellServer

EVL_VERSION = 4
MOCK_TYPE = "HONEYWELL"
# MOCK_TYPE = "DSC"
PASSWORD = "12345"

log = logging.getLogger(__name__)

clients = {}  # task -> (reader, writer)
conns_open = 0
evl_server = None


def accept_client(client_reader, client_writer):
    log.info(f"Accepted connection: client_reader={client_reader}, client_writer={client_writer}")
    task = asyncio.Task(handle_client(client_reader, client_writer))
    clients[task] = (client_reader, client_writer)

    def client_done(task):
        del clients[task]
        client_writer.close()
        log.info("End Connection")

    log.info("New Connection")
    task.add_done_callback(client_done)


async def handle_client(client_reader, client_writer):
    global conns_open

    if conns_open > 0:
        log.info(f"Already have {conns_open} conns open.  Closing new conn.")
        return
    conns_open += 1

    evl_server.connected(client_writer)

    # send a hello to let the client know they are connected
    await evl_server.hello()

    timeout_count = 0
    try:
        while True:
            data = None

            # wait for input from client
            try:
                data = await client_reader.readline()
            except asyncio.TimeoutError:
                log.info("Woke from read due to timeout")
                timeout_count += 1

            if data is None:
                # timeout waiting for data
                continue

            sdata = data.decode().rstrip()
            log.info(f"recv: {sdata}")
            if len(sdata) == 0:
                # connection was closed
                break

            if not await evl_server.process_command(sdata):
                break
    except Exception as ex:
        log.error("Caught exception: %r", ex)

    conns_open -= 1
    await evl_server.disconnected()
    log.info(f"Exiting reader loop; conns_open={conns_open}")


async def handle_http_client(client_reader, client_writer):
    key = base64.b64encode(bytes(f"user:{PASSWORD}", "utf-8")).decode("ascii")

    data = await client_reader.read(n=1024)
    data = data.decode()
    log.info("%s", data)

    m = re.search(r"Authorization: Basic ([a-zA-Z0-9\+/=]+)", data)
    if not m or m.group(1) != key:
        response = "HTTP/1.1 401 Authorization Required\r\n"
        response += "Connection: close\r\n"
        response += 'WWW-Authenticate: Basic realm="4449E6229DCA89A55B9B051B390183CC"\r\n'
        response += "Content-Type: text/html\r\n"
        response += "\r\n"
        response += "<HTML><BODY><H1>Server Requires Authentication</H1></BODY></HTML>\r\n"
        client_writer.write(response.encode())
    else:
        m = re.search("GET /([0-9]*)", data)
        if m.group(1) == "2":
            payload = f"<TITLE>Envisalink {EVL_VERSION}</TITLE>Security Subsystem - {MOCK_TYPE}<"
        elif m.group(1) == "3":
            payload = "Firmware Version: 1.2.3.4 MAC: 010203040506"
        else:
            payload = ""

        header = "HTTP/1.1 200 Success\r\nConnection: close\r\nConecnt-Type: text/html\r\n\r\n"
        client_writer.write(f"{header}{payload}\r\n".encode())


async def handle_cli_client(client_reader, client_writer):

    while True:
        data = None

        # wait for input from client
        try:
            data = await client_reader.readline()
        except asyncio.TimeoutError:
            log.info("Woke from read due to timeout")

        if data is None:
            # timeout waiting for data
            continue

        sdata = data.decode().rstrip()
        if len(sdata) == 0:
            # connection was closed
            break

        cmd = sdata.split(":")
        log.info(f"{cmd}")

        if cmd[0] == "write":
            evl_server.write_raw(cmd[1])

    log.info(f"Exiting reader loop; conns_open={conns_open}")


def accept_http_client(client_reader, client_writer):
    log.info(f"Accepted connection on http endpoint: client_reader={client_reader}, client_writer={client_writer}")
    task = asyncio.Task(handle_http_client(client_reader, client_writer))
    clients[task] = (client_reader, client_writer)

    def client_done(task):
        del clients[task]
        client_writer.close()
        log.info("End Connection")

    log.info("New Connection")
    task.add_done_callback(client_done)


def accept_cli_client(client_reader, client_writer):
    log.info(f"Accepted connection on cli endpoint: client_reader={client_reader}, client_writer={client_writer}")
    task = asyncio.Task(handle_cli_client(client_reader, client_writer))
    clients[task] = (client_reader, client_writer)

    def client_done(task):
        del clients[task]
        client_writer.close()
        log.info("End Connection")

    log.info("New Connection")
    task.add_done_callback(client_done)


async def main():
    global evl_server
    if MOCK_TYPE == "DSC":
        evl_server = DscServer(64, 1, PASSWORD)
    else:
        num_zones = 64
        if EVL_VERSION == 4:
            num_zones = 128
        evl_server = HoneywellServer(num_zones, 1, PASSWORD)

    server = await asyncio.start_server(accept_client, host=None, port=4025)
    await server.start_serving()

    http_server = await asyncio.start_server(accept_http_client, host=None, port=8080)
    await http_server.start_serving()

    cli_server = await asyncio.start_server(accept_cli_client, host=None, port=8000)
    await cli_server.start_serving()

    while True:
        await asyncio.sleep(5)


if __name__ == "__main__":
    log = logging.getLogger("")
    formatter = logging.Formatter("%(asctime)s %(levelname)s " + "[%(module)s:%(lineno)d] %(message)s")
    # setup console logging
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    ch.setFormatter(formatter)
    log.addHandler(ch)
    asyncio.run(main())