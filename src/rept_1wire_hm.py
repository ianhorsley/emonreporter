#!/usr/bin/env python

# program to interogate 1-wire bus and report all known temperatures
# with some commentary

# by ian
# This code has no warranty, including any implied fitness for purpose
# or implied merchantability.  It's free, and worth every penny.
# 2018/11/02
# updated to add more error catching and remove trend code

# /lib/systemd/system/1wireemon.service
# /home/pi/data/emonhub.conf

# standard library modules used in code
import sys
import time
import argparse
import socket
import logging

import emonhub_coder

# use OWFS module
import ow

# hm imports
from heatmisercontroller import network, logging_setup
from heatmisercontroller.exceptions import HeatmiserResponseError, HeatmiserControllerTimeError

#setup logging
logfolder = '/home/pi/rept_logs'
logging_setup.initialize_logger(logfolder, logging.WARN, True)

# set up parser with command summary
parser = argparse.ArgumentParser(
        description='Rolling 1-wire temperatures report')
# set up arguments with associated help and defaults
parser.add_argument('-i',
        dest='sample_interval',
        help='interval in seconds between samples',
        default='30')

# process the arguments
args=parser.parse_args()
# turn the arguments into numbers
sample_interval=float(args.sample_interval)

# socket config for emon connection
host = 'localhost'
port = 50011
node = '18' # for 1 wire bus
hmnode = '27' # for hm stat reporting

# tell the user what is happening
logging.info("1 wire bus reporting and hmstat reporting")
logging.info("  sample interval: "+str(sample_interval) + " seconds")

### 1 wire setup
# connect to localhost port 4304 where owserver should be running
try:
	ow.init('4304');
except exNoController as err:
	logging.warn('Could not connect to ow due to %s'%str(err))

# now determine what sensors we will consider
logging.debug("locate sensors and take initial readings:")
# every sensor on the bus added to the list
rawlist = ow.Sensor('/').sensorList()

#exError
#exNotInitialized, exUnknownSensor

# create lists for teh data we will accumulate
sensorlist=[]

# get time in seconds now
tt=int(time.time())

n=0 # initialise number of temperature sensors found so far
logging.info("initialising one wire array")
for s in rawlist:
    logging.info("  consider " + str(s) + ": ")
    if 'temperature' in s.entryList():
        # get teh temperature from that sensor
        T = s.temperature
        # increment count of sensors
        n = n + 1
        # tell the user teh good news
        logging.info("T: " + T)
        # record that as a sensor to interrogate
        sensorlist.append(s)
        # set found sensors to use un-cached results
        # so will run new conversion every read cycle
        s.useCache( False )
        # record the time of reading and value read
    else:
        # give the user the bad news
        logging.warn("no temperature value")
    print

logging.info("bus search done - " + str(n) + " temperature sensors found")

###setup hm network and controllers
logging.info("initialising hm network")
localconfigfile = '/home/pi/emonreporter/src/hmcontroller.conf'
hmn1 = network.HeatmiserNetwork(localconfigfile)

# CYCLE THROUGH ALL CONTROLLERS
for current_controller in hmn1.controllers:
  logging.info("Getting all data control %2d in %s *****************************" % (current_controller.address, current_controller.long_name))

  try:
    current_controller.read_all()
  except (HeatmiserResponseError, HeatmiserControllerTimeError) as err:
    print "C%d in %s Failed to Read due to %s" % (current_controller.address,  current_controller.name.ljust(4), str(err))
  else:
    disptext = "C%d Air Temp is %.1f from type %.f and Target set to %d  Boiler Demand %d" % (current_controller.address, current_controller.read_air_temp(), current_controller.read_air_sensor_type(), current_controller.setroomtemp, current_controller.heatingdemand)
    if current_controller.is_hot_water():
      print "%s Hot Water Demand %d" % (disptext, current_controller.hotwaterdemand)
    else:
      print disptext
    current_controller.display_heating_schedule()
    current_controller.display_water_schedule()
print

# now loop forever reading the identified sensors
while 1:
    # determine how long to wait until next interval
    # note this will skip some if specified interval is too short
    #  - it finds the next after now, not next after last
    sleeptime = sample_interval - (time.time() % sample_interval)
    time.sleep(sleeptime)

    # get time now and record it
    tt = int(time.time()) # we only record to integer seconds
    
    logging.info("Logging cyle at " + str(tt))

    try:
        fo = open(logfolder + "/testlog"+str(int(tt/86400))+".txt","ab")
    except IOError as e:
        logging.warn('failed to create log file : I/O error({0}): {1}'.format(e.errno, e.strerror))
    #except: #handle other exceptions such as attribute errors
    #    logging.warn("Unexpected error:" + str(sys.exc_info()[0]))
    #reset output string
    outputstr = node

    # work through list of sensors
    for s in sensorlist:
        n = sensorlist.index(s)  # the array register of this sensor
        try:  # just in case it has been unplugged
            T=float(s.temperature)
        except ow.exUnknownSensor:  # it has been unplugged
            logging.info('  sensor ' + str(s) + ' gone away - just ignore')
            logging.info('sensor ' + str(s) + ' left')
            continue  # so we'll jump to the next in the list

        # print sensor name and current value
        logging.info( '  {!s}: {:-6.2f}'.format(s.id,T))
        stringout = '{}:{!s}:{:+06.2f}'.format(tt,s.id,T)

        fo.write(stringout)
        fo.write("\n")

        outputstr += ' {:-3.0f}'.format(T*10)

    fo.close()

    ### do same for hm controllers

    #force read all fields at the same time to all optimisation
    allread = hmn1.All.read_fields(['sensorsavaliable','airtemp','remoteairtemp','heatingdemand','hotwaterdemand'], 0)
    #get demands and temps replacing nones
    demands = [99 if row is None or row[3] is None else row[3] for row in allread]
    hotwater = 2 if allread is None or allread[0] is None else allread[0][4]
    temps = [-10 if temp is None else temp for temp in hmn1.All.read_air_temp()]
    
    logging.info('Temps ' + ' '.join(map(str,temps)))
    logging.info('Demands ' + ' '.join(map(str,demands + [hotwater])))
    #enocde using emonhubs own module
    encodedtemps = [' '.join(map(str,emonhub_coder.encode("h",temp * 10 ))) for temp in temps ]
    #zip temp and demands and join string
    outputstr2 = ' '.join([hmnode, str(hotwater)] + ['%s %d'%pair for pair in zip(encodedtemps, demands)])
    
    #print outputstr2
    try:
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        soc.connect((host,port))
        logging.info('socket send %s'%outputstr)
        soc.send(outputstr + '\r\n')
        logging.info('socket send %s'%outputstr2)
        soc.send(outputstr2 + '\r\n')
        soc.close()
    except IOerror as err:
        logging.warn('could not connect to emonhub due to ' + str(err))
