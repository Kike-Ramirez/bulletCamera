# hola

import time
import logging
from SimpleCV import Camera, Image, Color
import SimpleCV
import cv2
import png
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
import numpy
import math
import socket

# Function to capture FNUM frames in a row, and save it in captures global array
# --------------------------------------------------
def cameraCapture():

    global cam, captures, cameraOpen, FNUM

    logging.debug('Capture thread started')

    cameraOpen = True

    captures = []

    for num in range(FNUM):
        logging.debug('Capturing: ' + str(num))
        img = cam.getImage()
	img = img.resize(1024, 768)
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
    global data

    # Prepare status.json and send it to the server every 1 sec
    print 'Sending Ping...'
    
    # Save status
    with open('/home/pi/src/python/bulletCamera/status.json', 'w') as outfile:
        json.dump(data, outfile)

    # Create a memory file to save status and send it via HTTP to server
    byte_io = BytesIO()
    data.save(byte_io, 'JSON')
    byte_io.seek(0)

    return send_file(byte_io, mimetype='application/json')         




    



# ------------------------------------------------------

logging.basicConfig(level=logging.DEBUG,
                    format='[%(levelname)s] (%(threadName)-10s) %(message)s',
                    )

with open('/home/pi/src/python/bulletCamera/settings.json') as data_file:    
    data = json.load(data_file)

HOST = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
PORT = data['cam']['port']
FPS = data['cam']['fps']
FNUM = FPS * 5

print 'HOST' + HOST

CAM_WIDTH = data['cam']['width']
CAM_HEIGHT = data['cam']['height']

captures = []
threads = []

cameraOpen = False

data['cam']['calibrated'] = False
data['cam']['tracked'] = False
data['cam']['onFocus'] = False




#prop_map = { "width": data['cam']['width'], "height": data['cam']['height']  }

#cam = Camera(camera_index = data['cam']['index'], threaded = True)

cam = Camera()

time.sleep(0.5)

img = cam.getImage()

targets = [ [ data['cal']['target1x'] * img.width, data['cal']['target1y'] * img.height, data['cal']['target1r'] * img.width ], 
    [ data['cal']['target2x'] * img.width, data['cal']['target2y']* img.height, data['cal']['target2r']* img.width ] ] 


app = Flask(__name__)



def map(value, minOutput, maxOutput, minInput=0, maxInput=100):
    inputRange = maxInput - minInput
    outputRange = maxOutput - minOutput
    valueScaled = float(value - minInput) / float(inputRange)

    return minOutput + (valueScaled * outputRange)

def drawCircles(img):
    global data, targets

    if len(targets) is 2:
        for t in targets:
            logging.debug('SimpleCV: Drawing FAKE circles...')         
            img.drawCircle((t[0], t[1]), 3, SimpleCV.Color.RED, -1)    
            img.drawCircle((t[0], t[1]), t[2], SimpleCV.Color.RED, 2)    

        img.drawLine( (targets[0][0] , targets[0][1]), (targets[1][0] , targets[1][1]) , SimpleCV.Color.RED, 2 )

def drawArea(img):
    global data

    x = data['cal']['area1x'] * img.width
    y = data['cal']['area1y'] * img.height
    w = data['cal']['area1w'] * img.width
    h = data['cal']['area1h'] * img.height

    logging.debug('SimpleCV: Drawing safe calibration area' )

    img.drawRectangle(x,y,w,h, Color.GREEN, 0, 60 )
    img.drawRectangle(x,y,w,h, Color.GREEN, 1, 255 )


def drawGrid(img):

    logging.debug('SimpleCV: Drawing grid' )

    img.drawLine((0, img.height * 0.5 ) , ( img.width, img.height * 0.5), Color.WHITE, 1 )
    img.drawLine(( img.width * 0.5, 0 ) , ( img.width * 0.5 , img.height ), Color.WHITE, 1 )



def rotate(img):
    global data

    p1x = data['cal']['target1x'] * img.width
    p1y = data['cal']['target1y'] * img.height

    p2x = data['cal']['target2x'] * img.width
    p2y = data['cal']['target2y'] * img.height

    rotateAngle = math.atan2( (p2x - p1x) , (p2y - p1y) )

    output = img.rotate( math.degrees(- rotateAngle ), point=(p2x, p2y), fixed=True)   

    logging.debug('Rotate Angle: ' + str(math.degrees( - rotateAngle ))) 
    
    logging.debug('SimpleCV: Imaged Rotated')

    return output


def crop(img):
    global data

    output = img.crop(x = img.width * 0.5 , y = img.height * 0.5 , w = 768, h = 768, centered=True )

    logging.debug('SimpleCV: Imaged Cropped')

    return output

def trackTargets(img):
    global data, cam

    logging.debug('SimpleCV: Calculating target positions')

    targets = [ [ data['cal']['target1x'] * img.width, data['cal']['target1y'] * img.height, data['cal']['target1r'] * img.width ], 
        [ data['cal']['target2x'] * img.width, data['cal']['target2y']* img.height, data['cal']['target2r']* img.width ] ] 

    # OPTION 1: Test in better lighting conditions (no colour matching)

    # circles = img.findCircle(canny=int(data['cal']['canny']),
    #     thresh=int(data['cal']['threshold']),
    #     distance=int(data['cal']['distance']))


    # OPTION 2: Test in better lighting conditions (color matching - best candidate)

    logging.debug('SimpleCV: Calculating masks...')
    # black_mask = img.colorDistance(color=(0, 0, 0)).binarize()
    # # Totem color=(165, 178, 94)
    distance = img.hueDistance(color=(165, 178, 94)).invert().binarize(threshold=100)

    logging.debug('SimpleCV: Finding blobs...')
    blobs = (distance).findBlobs()

    logging.debug('SimpleCV: Detecting circles...')
    if blobs is not None:
        circles = [b for b in blobs if b.isCircle(0.5)]
        if len(circles) == 0:
            logging.debug('SimpleCV: No circles detected')
            return None

    # loop over the (x, y) coordinates and radius of the circles
    for c in circles:
        # draw the circle in the output image
        rad = c.radius()
        if (data['cal']['minRadioTarget'] < rad) and (data['cal']['maxRadioTarget'] > rad):
            logging.debug('SimpleCV: Drawing circles...')         
            img.drawCircle((c.x, c.y), c.radius(),SimpleCV.Color.BLUE,3)

    return targets



@app.route("/set/brightness/<int:number>")
def setBrightness(number):
    global data

    # INNO Dept: Change brightness to camera using v4l-ctl

    number = map(number, -64, 64)
    brightnessCommand = "v4l2-ctl --set-ctrl brightness=" + str(number)
    os.system(brightnessCommand)

    # Change status value
    data['cam']['brightness'] = number

    return "BulletCam - Brightness (-64 - 64) changed: " + str(number), 200

@app.route("/set/contrast/<int:number>")
def setContrast(number):
    number = map(number, 0, 95)
    contrastCommand = "v4l2-ctl --set-ctrl contrast=" + str(number)
    os.system(contrastCommand)

    # Change status value
    data['cam']['contrast'] = number

    return "BulletCam - Contrast (0 - 95) changed: " + str(number), 2000

@app.route("/set/saturation/<int:number>")
def setSaturation(number):
    number = map(number, 0, 100)
    saturationCommand = "v4l2-ctl --set-ctrl saturation=" + str(number)
    os.system(saturationCommand)

    # Change status value
    data['cam']['saturation'] = number

    return "BulletCam - Saturation (0-100) changed: " + str(number), 2000

@app.route("/set/hue/<int:number>")
def setHue(number):
    number = map(number, -2000, 2000)
    hueCommand = "v4l2-ctl --set-ctrl hue=" + str(number)
    os.system(hueCommand)

    # Change status value
    data['cam']['hue'] = number

    return "BulletCam  - Hue changed: " + str(number), 2000


@app.route("/set/exposure_auto/<int:number>")
def setExposure_auto(number):
    # INNO Dept: Change exposure to camera using v4l-ctl
    if number == 0:
        exposure_autoCommand = "v4l2-ctl --set-ctrl exposure_auto=3"
    elif number == 1:
        exposure_autoCommand = "v4l2-ctl --set-ctrl exposure_auto=1"
    os.system(exposure_autoCommand)

    # Change status value
    data['cam']['exposure_auto'] = number

    return "BulletCam - Auto exposure changed to mode (0-3): " + str(number), 2000

@app.route("/set/exposure/<int:number>")
def setExposure(number):

    # INNO Dept: Change exposure to camera using v4l-ctl
    number = map(number, 50, 1000)
    exposure_autoCommand = "v4l2-ctl --set-ctrl exposure_absolute=" + str(number)
    os.system(exposure_autoCommand)

    # Change status value
    data['cam']['exposure'] = number

    return "BulletCam - Manual exposure (50-10000) changed: " + str(number), 2000

@app.route("/calibrate")
def calibrate():
    global data, cameraOpen, cam
    logging.debug('Calibration started...')

    if not cameraOpen:

        # Clear captures list
        captures = []

        # Reserve resource
        cameraOpen = True

        # Take a new capture
        img = cam.getImage()

        # Free resource
        cameraOpen = False

        # Downscale image to speed up processing
        img = img.resize(1024, 768)

        # # Detect totems and send back position to server
        # logging.debug('SimpleCV: Detecting reference totems...')

        # targets = trackTargets(img2)

        # # Check if we are on focus
        # if (targets[0].x >= data['cal']['area1x']) and (targets[0].x <= (data['cal']['area1x'] + data['cal']['area1w'])): 
        #     if (targets[0].y >= data['cal']['area1y']) and (targets[0].y <= (data['cal']['area1y'] + data['cal']['area1h'])):

        #         data['cal']['onFocus'] = True

        # distance = img2.hueDistance(color=(165, 178, 94)).invert().binarize(threshold=100)

        # Draw screen indicators
        # drawArea(img2)
        drawGrid(img)
        # drawCircles(img2)


        logging.debug('Saving image into memory file')
        # Create a memory file to save capture and send it via HTTP to server
        byte_io = BytesIO()
        img.save(byte_io, 'PNG')
        byte_io.seek(0)
        logging.debug('Picture saved into memory file')

        data['cal']['calibrated'] = True

        # Send info back to server
        logging.debug('Send back image to server...')
        return send_file(byte_io, mimetype='image/png')         

    else:
        return "BulletCam - Error: camera still working - try again in 5 seconds", 404

@app.route("/track")
def track():
    global data, cameraOpen, cam

    if not cameraOpen & data['cal']['calibrated']:
        logging.debug('Setting tracked ON')

        data['cal']['tracked'] = True

        # Clear captures list
        captures = []

        # Reserve resource
        cameraOpen = True

        # Take a new capture
        img = cam.getImage()

        # Free resource
        cameraOpen = False

        # Detect totems and send back position to server

        logging.debug('SimpleCV: Detecting reference totems...')

        targets = trackTargets(img)

        # Rotate & Crop Image
        drawCircles(img)
        img_temp = rotate(img)
        img_temp = crop(img_temp)

        # Draw screen indicators
        drawArea(img_temp)
        drawGrid(img_temp)

        logging.debug('Saving image into memory file')
        # Create a memory file to save capture and send it via HTTP to server
        byte_io = BytesIO()
        img_temp.save(byte_io, 'PNG')
        byte_io.seek(0)
        logging.debug('Picture saved into memory file')


        # Send info back to server
        logging.debug('Send back image to server...')
        return send_file(byte_io, mimetype='image/png')         

    elif data['cal']['calibrated']:
        return "BulletCam - Error: camera still working - try again in some seconds", 404

    else:
        return "BulletCam - Error: camera not calibrated - proceed to calibrate first", 404



@app.route("/capture")
def capture():
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

    # Run main app
    app.run(HOST, PORT)
