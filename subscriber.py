import json
import time

import zmq


def main():
    context = zmq.Context()

    subscriber = context.socket(zmq.SUB)
    subscriber.connect('tcp://localhost:5561')
    subscriber.setsockopt(zmq.SUBSCRIBE, b'')
    print('# sub')

    time.sleep(1)

    syncclient = context.socket(zmq.REQ)
    syncclient.connect('tcp://localhost:5562')

    syncclient.send_string('req')
    print('# req')

    data = syncclient.recv_string()
    print('$', data)

    while True:
        msg = subscriber.recv_string()
        print(msg)
        if msg == 'DONE':
            break



if __name__ == '__main__':
    print('# send')
    print('$ recv')
    print()
    main()
