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
import os
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
import heatmisercontroller.setup as hms

def initialise_setup(configfile=None):
    """Initialise setup loading configuration file."""

    # Select default configuration file if none provided
    if configfile is None:
        module_path = os.path.abspath(os.path.dirname(__file__))
        configfile = os.path.join(module_path, "reporter.conf")
      
    # Initialize controller setup
    try:
        setup = hms.HeatmiserControllerFileSetup(configfile)
    except hms.HeatmiserControllerSetupInitError as err:
        logging.error(err)
        sys.exit("Unable to load configuration file: " + configfile)
        
    return setup, configfile

def initialise_1wire():
    """Initialise 1 wire network and check for sensors"""
    ### 1 wire setup
    logging.debug("locate sensors and take initial readings:")
    try:
        # connect to localhost port where owserver should be running
        ow.init(setup.settings['1wire']['owport']);

        # list every sensor on the bus added that could be added to the list
        rawlist = ow.Sensor('/').sensorList()
    except (ow.exNoController,  ow.exNotInitialized) as err:
        logging.warn('Could not connect to ow due to %s'%str(err))

    expected_sensors = setup.settings['1wire']['sensors']
    #exError
    #exNotInitialized, exUnknownSensor

    # create lists for the data we will report
    sensorlist=[None] * len(expected_sensors)
    
    # get time in seconds now
    tt=int(time.time())

    n=0 # initialise number of expected temperature sensors found so far
    logging.info("initialising one wire array")
    for s in rawlist:
        try:
            #logging.info("  considering " + str(s) + ": ")
            if 'temperature' in s.entryList():
                # get teh temperature from that sensor
                T = s.temperature
                if s._usePath in expected_sensors:
                    # increment count of sensors detected
                    n += 1
                    # tell the user the good news
                    logging.info("T: " + T)
                    # record that as a sensor to interrogate
                    sensorlist[expected_sensors.index(s._usePath)] = s
                    logging.info("Sensor, %s, found that will be logged with initial reading %s."%(s, T))
                else:
                    # log the new sensor
                    logging.info("New sensor, %s, found that won't be logged."%s)
                # set found sensors to use un-cached results
                # so will run new conversion every read cycle
                s.useCache( False )
                # record the time of reading and value read
            else:
                # log the non temperature sensors
                logging.info("Non temperature sensor, %s, found that won't be logged."%s)
        except ow.exUnknownSensor:
            logging.warn("Sensor gone away during setup")
    logging.info("bus search done - %i sensors found - %i temperature sensors logging - %i sensors missing"%(len(rawlist), n, len(expected_sensors) - n))

def initialise_heatmiser(localconfigfile=None):
    """Initialise heatmiser network and check for sensors"""
    ###setup hm network and controllers
    logging.info("initialising hm network")
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

setup, localconfigfile = initialise_setup()

#setup logging
logging_setup.initialize_logger(setup.settings['logging']['logfolder'], logging.WARN)

# tell the user what is happening
logging.info("1 wire bus reporting and hmstat reporting")
logging.info("  sample interval: "+str(sample_interval) + " seconds")

initialise_1wire()

initialise_heatmiser(localconfigfile)

quit()

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
