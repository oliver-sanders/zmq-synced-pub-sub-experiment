import asyncio
import json
import random

import zmq
import zmq.asyncio


class DataDriver(object):

    def __init__(self):
        self.data = []
        self.subscribers = []

    def subscribe(self, fcn):
        self.subscribers.append(fcn)

    async def start(self):
        print('Driver started')
        while True:
            await asyncio.sleep(1)
            delta = random.random()
            self.data.append(delta)
            self.update(delta)

    def update(self, delta):
        for fcn in self.subscribers:
            fcn(str(delta))

    @asyncio.coroutine
    def json(self):
        return json.dumps(self.data)


@asyncio.coroutine
def sync_listener(socket, callback):
    print('sync_lister listening')
    msg = yield from socket.recv_string()
    print('revieved "%s"' % msg)
    response = yield from callback()
    print('sending "%s"' % response)
    socket.send_string(response)


def main():
    # context = zmq.Context()
    context = zmq.asyncio.Context()

    publisher = context.socket(zmq.PUB)
    publisher.sndhwm = 1100000  # ???
    publisher.bind('tcp://*:5561')

    syncer = context.socket(zmq.REP)
    syncer.bind('tcp://*:5562')

    driver = DataDriver()
    driver.subscribe(publisher.send_string)
    driver.subscribe(print)

    asyncio.ensure_future(driver.start())
    asyncio.ensure_future(sync_listener(syncer, driver.json))

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.get_event_loop().close()  # perhaps a bit harsh
        publisher.send_string('DONE')
        print('DONE')


main()
