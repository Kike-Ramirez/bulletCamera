# hola

import time
import logging
from SimpleCV import Camera, Image
import threading
from threading import Timer,Thread,Event
from flask import Flask, make_response, send_file
import shutil
from os import listdir
from os.path import isfile, join
import json
from pprint import pprint
from io import BytesIO
import os


# Function to capture FNUM frames in a row, and save it in captures global array
# --------------------------------------------------
def cameraCapture():

    global cam, captures, cameraOpen

    logging.debug('Capture thread started')

    cameraOpen = True

    captures = []

    for num in range(FNUM):
        img = cam.getImage()
        captures.append(img)
        time.sleep(1. / FPS)

    cameraOpen = False

    logging.debug('Capture thread finished')

# Thread to send ping Status to server every second
# --------------------------------------------------
class PingStatus():

   def __init__(self,t,hFunction):
      self.t=t
      self.hFunction = hFunction
      self.thread = Timer(self.t,self.handle_function)

   def handle_function(self):
      self.hFunction()
      self.thread = Timer(self.t,self.handle_function)
      self.thread.start()

   def start(self):
      self.thread.start()

   def cancel(self):
      self.thread.cancel()

def pingStatus():

    # Prepare status.json and send it to the server every 1 sec
    print 'Sending Ping...'


# Function to send nth frame to server (just once)
# --------------------------------------------------
def sendFrame(number):
    global captures, cameraOpen, data

    logging.debug('SendFrame thread started')

    if not cameraOpen:

        if number >= 0 and number < FNUM:

            # Create a memory file to save capture and send it via HTTP to server
            byte_io = BytesIO()
            captures[number].save(byte_io, 'PNG')
            byte_io.seek(0)

            return send_file(byte_io, mimetype='image/png')         

        else:

            return "BulletCam - Error: index out of range", 404

    else:

        return "BulletCam - Error: camera still working - try again in 5 seconds", 404

    logging.debug('SendFrame thread finished')



# ------------------------------------------------------

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s',
                    )

with open('/home/pi/src/python/bulletCamera/settings.json') as data_file:    
    data = json.load(data_file)

HOST = '10.42.0.' + str(100 + data['cam']['id'])
PORT = data['cam']['port']
FPS = data['cam']['fps']
FNUM = FPS * 5


data = []
captures = []
cameraOpen = False
threads = []


cam = Camera()
time.sleep(0.5)

app = Flask(__name__)



def map(value, minOutput, maxOutput, minInput=0, maxInput=100):
    inputRange = maxInput - minInput
    outputRange = maxOutput - minOutput
    valueScaled = float(value - minInput) / float(inputRange)

    return minOutput + (valueScaled * outputRange)


@app.route("/set/brightness/<int:number>")
def setBrightness(number):
    # INNO Dept: Change brightness to camera using v4l-ctl
    number = map(number, -64, 64)
    brightnessCommand = "v4l2-ctl --set-ctrl brightness=" + str(number)
    os.system(brightnessCommand)

    return "BulletCam - Brightness (-64 - 64) changed: " + str(number), 200

@app.route("/set/contrast/<int:number>")
def setContrast(number):
    number = map(number, 0, 95)
    contrastCommand = "v4l2-ctl --set-ctrl contrast=" + str(number)
    os.system(contrastCommand)
    # INNO Dept: Change contrast to camera using v4l-ctl

    return "BulletCam - Contrast (0 - 95) changed: " + str(number), 2000

@app.route("/set/saturation/<int:number>")
def setSaturation(number):
    number = map(number, 0, 100)
    saturationCommand = "v4l2-ctl --set-ctrl saturation=" + str(number)
    os.system(saturationCommand)
    # INNO Dept: Change saturation to camera using v4l-ctl

    return "BulletCam - Saturation (0-100) changed: " + str(number), 2000

@app.route("/set/hue/<int:number>")
def setHue(number):
    number = map(number, -2000, 2000)
    hueCommand = "v4l2-ctl --set-ctrl hue=" + str(number)
    os.system(hueCommand)
    # INNO Dept: Change hue to camera using v4l-ctl

    return "BulletCam  - Hue changed: " + str(number), 2000


@app.route("/set/exposure_auto/<int:number>")
def setExposure_auto(number):
    # INNO Dept: Change exposure to camera using v4l-ctl
    if number == 0:
        exposure_autoCommand = "v4l2-ctl --set-ctrl exposure_auto=3"
    elif number == 1:
        exposure_autoCommand = "v4l2-ctl --set-ctrl exposure_auto=1"
    os.system(exposure_autoCommand)

    return "BulletCam - Auto exposure changed to mode (0-3): " + str(number), 2000

@app.route("/set/exposure/<int:number>")
def setExposure(number):
    number = map(number, 50, 1000)
    exposure_autoCommand = "v4l2-ctl --set-ctrl exposure_absolute=" + str(number)
    os.system(exposure_autoCommand)
    # INNO Dept: Change exposure to camera using v4l-ctl

    return "BulletCam - Manual exposure (50-10000) changed: " + str(number), 2000

@app.route("/calibrate")
def calibrate():
    logging.debug('Calibration started...')

    if not cameraOpen:

        # Take a capture
        img = cam.getImage()
        logging.debug('Picture succesfully taken')

        # Create a memory file to save capture and send it via HTTP to server
        byte_io = BytesIO()
        img.save(byte_io, 'PNG')
        byte_io.seek(0)
        logging.debug('Picture saved into memory file')

        # Detect totems and send back position to server

        logging.debug('OpenCV: Detecting reference totems...')

        # Send info back to server
        logging.debug('Send back image to server...')
        return send_file(byte_io, mimetype='image/png')         

    else:
        return "BulletCam Id:" + str(data['cam']['id']) + " - Error: camera still working - try again in 5 seconds", 404

    logging.debug('camCalibrate succesfully finished')


@app.route("/capture")
def start():
    global captures, cameraOpen, data

    if not cameraOpen:

        logging.debug('Starting capture thread...')        
        t = threading.Thread(name='BulletCam - capture', target=cameraCapture)
        threads.append(t)
        t.start()

        textReturn = "BulletCam - Capturing ... "
        return textReturn, 200
    
    else:
        textReturn = "BulletCam - Error: Camera still working" 
        return textReturn, 404



@app.route('/get/<int:number>')
def getFrameNum(number):
    global captures, cameraOpen, data
	
    logging.debug('Sending frame to server')

    if not cameraOpen:

        if number >= 0 and number < len(captures):

            byte_io = BytesIO()
            captures[number].save(byte_io, 'PNG')
            byte_io.seek(0)

            return send_file(byte_io, mimetype='image/png')         

        else:

            return "BulletCam - Error: Index (0 - " + str(FNUM) + " ) out of range", 404

    else:

        return "BulletCam Id: - Error: Camera still working", 404



# Main entrance
if __name__ == '__main__':
    print map(0, 0, 128)
    print map(50, 0, 128)
    print map(100, 0, 128)

    print map(0, -128, 128)
    print map(50, -128, 128)
    print map(100, -128, 128)
    # Run main app
    app.run(HOST, PORT)
