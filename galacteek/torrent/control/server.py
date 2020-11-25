import asyncio
import logging
import pickle
import struct
from typing import Any, cast, Callable, Optional

from galacteek.torrent.control.manager import ControlManager
from galacteek import log as logger


__all__ = ['ControlServer', 'DaemonExit']


# logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class DaemonExit(Exception):
    pass


class ControlServer:
    def __init__(self, control: ControlManager, daemon_stop_handler: Optional[Callable[['ControlServer'], None]]):
        self._control = control
        self._daemon_stop_handler = daemon_stop_handler

        self._server = None

    @property
    def control(self) -> ControlManager:
        return self._control

    HANDSHAKE_MESSAGE = b'bit-torrent:ControlServer\n'

    LENGTH_FMT = '!I'

    @staticmethod
    async def receive_object(reader: asyncio.StreamReader) -> Any:
        length_data = await reader.readexactly(struct.calcsize(ControlServer.LENGTH_FMT))
        (length,) = struct.unpack(ControlServer.LENGTH_FMT, length_data)
        data = await reader.readexactly(length)
        return pickle.loads(data)

    @staticmethod
    def send_object(obj: Any, writer: asyncio.StreamWriter):
        data = pickle.dumps(obj)
        length_data = struct.pack(ControlServer.LENGTH_FMT, len(data))
        writer.write(length_data)
        writer.write(data)

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr_repr = ':'.join(map(str, writer.get_extra_info('peername')))
        logger.info('accepted connection from %s', addr_repr)

        try:
            writer.write(ControlServer.HANDSHAKE_MESSAGE)

            while True:
                # FIXME: maybe do not allow to execute arbitrary object
                action = cast(Callable[[ControlManager], Any], await ControlServer.receive_object(reader))

                try:
                    result = action(self._control)
                    if asyncio.iscoroutine(result):
                        result = await result
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    result = e

                ControlServer.send_object(result, writer)

                if isinstance(result, DaemonExit):
                    logger.info('stop command received')
                    if self._daemon_stop_handler is not None:
                        self._daemon_stop_handler(self)
                    return
        except asyncio.IncompleteReadError:
            pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning('%s disconnected because of %r', addr_repr, e)
        finally:
            writer.close()

    HOST = '127.0.0.1'
    # PORT_RANGE = range(6995, 6999 + 1)
    PORT_RANGE = range(7005, 7010)

    async def start(self):
        for port in ControlServer.PORT_RANGE:
            try:
                self._server = await asyncio.start_server(
                    self._accept, host=ControlServer.HOST, port=port)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f'exception on starting server on port {port}: {e}')
            else:
                logger.info(f'server started on port {port}')
                return
        else:
            raise RuntimeError('Failed to start a control server')

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            logger.info('server stopped')
