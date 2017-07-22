import time
from SimpleCV import Camera, Image
import threading
from threading import Thread, Event
from flask import Flask, make_response, send_file
import shutil
from os import listdir
from os.path import isfile, join
import json
from pprint import pprint
from io import BytesIO


class LoopThread(Thread):
    def __init__(self, stop_event):
        self.stop_event = stop_event
        Thread.__init__(self)

    def run(self):
        while True:
            START_EVENT.wait()
            self.loop_process()

    def loop_process(self):
        global num, cam, captures
        img = cam.getImage()
        captures.append(img)
        num += 1
        print 'Picture Taken: ' + str(num)
        time.sleep(1. / FPS)

with open('settings.json') as data_file:    
    data = json.load(data_file)

HOST = '10.42.0.' + str(100 + data['cam']['id'])
PORT = data['cam']['port']
FPS = data['cam']['fps']

START_EVENT = Event()
thread = LoopThread(START_EVENT)

num = 0

data = []
captures = []
cameraOpen = False



cam = Camera()
time.sleep(0.5)

app = Flask(__name__)

@app.route("/stop")
def stop():
    global captures, cameraOpen
    cameraOpen = False
    START_EVENT.clear()
    print '----- Stopped -----'

    return "BulletCam Stopped!!", 200

@app.route("/start")
def start():
    global captures, cameraOpen
    if not cameraOpen:
        captures = []
        cameraOpen = True
        START_EVENT.set()
        print '----- Started -----'
        return "BulletCam Started!!", 200
    else:
        return "BulletCam already working!!", 200


@app.route('/get/<int:number>')
def getFrameNum(number):
    global captures, cameraOpen
    print len(captures)
    print 'Getting frame : ' + str(number)
	
    if not cameraOpen:

        if number >= 0 and number < len(captures):

            """Saves into memory to send the nth capture """
            byte_io = BytesIO()
            captures[number].save(byte_io, 'PNG')
            byte_io.seek(0)

            return send_file(byte_io, mimetype='image/png')         

        else:

            return "OUT OF RANGE", 200

    else:

        return "CAMERA STILL WORKING", 200



if __name__ == '__main__':
    thread.daemon = True
    thread.start()
    app.run(HOST, PORT)
