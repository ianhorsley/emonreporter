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

# use OWFS pyownet module
import pyownet

# hm imports
from heatmisercontroller import network, logging_setup
from heatmisercontroller.exceptions import HeatmiserResponseError, HeatmiserControllerTimeError
import heatmisercontroller.setup as hms

def initialise_setup(configfile=None):
    """Initialise setup loading configuration file."""

    # Select default configuration file if none provided
    if configfile is None:
        module_path = os.path.abspath(os.path.dirname(__file__))
        configfile = os.path.join(module_path, "../conf/reporter.conf")

    # Initialize controller setup
    try:
        setup = hms.HeatmiserControllerFileSetup(configfile)
    except hms.HeatmiserControllerSetupInitError as err:
        logging.error(err)
        sys.exit("Unable to load configuration file: " + configfile)

    return setup, configfile

def initialise_1wire():
    """Initialise 1 wire network and check for sensors"""
    logging.debug("locate sensors and take initial readings:")
    try:
        # connect to localhost port where owserver should be running
        ow = pyownet.protocol.proxy(host='localhost', port=setup.settings['1wire']['owport'])

        # list every sensor on the bus added that could be added to the list
        rawlist = ow.dir()
    except (pyownet.protocol.Error) as err:
        logging.warning('Could not connect to ow due to %s'%str(err))
        return []

    expected_sensors = setup.settings['1wire']['sensors']
    #exError
    #exNotInitialized, exUnknownSensor

    n=0 # initialise number of expected temperature sensors found so far
    logging.info("initialising one wire array")

    try:
        rawlist = ow.dir()
        ow.write('simultaneous/temperature', data=b'1')    # begin conversions
        time.sleep(0.75)                                   # need to wait for conversion
    except (pyownet.protocol.Error) as err:
        logging.warning('Could not read list and run concersion on ow due to %s', str(err))
        return []
        
    for s in expected_sensors:
        try:
            logging.info("  considering " + str(s) + ": ")
            if ow.present(s):
                if ow.present(s + '/latesttemp'):
                    # get the temperature from that sensor
                    t = float(ow.read(s + '/latesttemp'))
                    n += 1
                    logging.info("Sensor, %s, found that will be logged with initial reading %s.", s, t)
                else:
                    # log the non temperature sensors
                    logging.warning("Expected sensor is a non temperature sensor, %s, found that won't be logged.", s)
            else:
                logging.warning("Expected sensor, %s, not found.", s)
        except pyownet.protocol.Error:
            logging.warning("Sensor gone away during setup")
            
    for s in rawlist:
        if s[:-1] not in expected_sensors:
            if ow.present(s[:-1] + '/latesttemp'):
                # get the temperature from that sensor
                t = float(ow.read(s + '/latesttemp'))
                logging.info("New sensor, %s, found that won't be logged with initial reading %s.", s, t)
            else:
                # log the non temperature sensors
                logging.warning("Non temperature sensor, %s, found that won't be logged.", s)
    
    
    logging.info("bus search done - %i sensors found - %i temperature sensors - %i sensors missing",
                    len(rawlist),
                    n,
                    len(expected_sensors) - n)
    
    if n > 0:
        return expected_sensors
    else:
        return []

def get_1wire_data():
    """Get data from 1 wire network and and return formatted string"""
    #reset output string
    outputstr = setup.settings['emonsocket']['node']

    try:
        ow.write('simultaneous/temperature', data=b'1')    # begin conversions
        time.sleep(0.75)                                   # need to wait for conversion
    except (pyownet.protocol.Error) as err:
        logging.warning('Could not read list and run concersion on ow due to %s', str(err))
        return None

    n = 0 #count results

    # work through list of sensors
    for s in sensorlist1wire:
        try:  # just in case it has been unplugged
            # get the temperature from that sensor
            t = float(ow.read(s + '/latesttemp'))
            n += 1
        except pyownet.protocol.Error:  # it has been unplugged
            logging.warning('Sensor ' + str(s) + ' gone away - ignoring')
            t = float(setup.settings['emonsocket']['temperaturenull'])
            #continue  # so we'll jump to the next in the list
        else:
            # print sensor name and current value
            logging.info( 'Logging Sensor {!s}: {:-6.2f}'.format(s, t))
            stringout = '{}:{!s}:{:+06.2f}\n'.format(tt, s, t)
            datalogger.log(stringout)

        #outputstr += ' {:-3.0f}'.format(T*10)
        outputstr += ' ' + ' '.join(map(str,emonhub_coder.encode("h", t * 10 )))
    
    logging.debug(outputstr)
    
    if n == 0:
        return None
    return outputstr 
    
def initialise_heatmiser(localconfigfile=None):
    """Initialise heatmiser network and check for sensors"""
    logging.info("initialising hm network")
    try:
        hmn = network.HeatmiserNetwork(localconfigfile)
    except HeatmiserResponseError:
        return None

    # CYCLE THROUGH ALL CONTROLLERS
    for current_controller in hmn.controllers:
      logging.info("Getting all data control %2d in %s" % (current_controller.set_address, current_controller.set_long_name))

      try:
        current_controller.read_all()
        disptext = "C%d Air Temp is %.1f from type %.f and Target set to %d  Boiler Demand %d" % (current_controller.set_address, current_controller.read_air_temp(), current_controller.read_air_sensor_type(), current_controller.setroomtemp, current_controller.heatingdemand)
      except (HeatmiserResponseError, HeatmiserControllerTimeError) as err:
        logging.warning("C%d in %s Failed to Read due to %s" % (current_controller.set_address,  current_controller.name.ljust(4), str(err)))
      else:
        if current_controller.is_hot_water:
          logging.info("%s Hot Water Demand %d" % (disptext, current_controller.hotwaterdemand))
        else:
          logging.info(disptext)
          
    return hmn

def get_heatmiser_data():
    """Get data from heatmiser network and and return formatted string"""
    try:
        #read all fields needed now
        allread = hmn.All.read_fields(['sensorsavaliable','airtemp','remoteairtemp','heatingdemand','hotwaterdemand'], 0)
        #read currenttime, which will get time from sensor every 24 hours and hence check .
        hmn.All.read_field('currenttime')
    except (HeatmiserResponseError, HeatmiserControllerTimeError) as err:
        logging.warning("All failed to read due to %s" % (str(err)))
        return ''
    else:
        #get demands and temps replacing nones
        demands = [99 if row is None or row[3] is None else row[3] for row in allread]
        hotwater = 2 if allread is None or allread[0] is None else allread[0][4]
        temps = [float(setup.settings['emonsocket']['temperaturenull']) if temp is None else temp for temp in hmn.All.read_air_temp()]
    
        logging.debug('Temps ' + ' '.join(map(str,temps)))
        logging.debug('Demands ' + ' '.join(map(str,demands + [hotwater])))
    
        #enocde using emonhubs own module
        encodedtemps = [' '.join(map(str,emonhub_coder.encode("h",temp * 10 ))) for temp in temps ]
    
        logging.info('Logging heatmiser data')
        stringout = str(tt)
        tempstring = ':TEMP' + ','.join(str(tep) for tep in temps)
        demandsstring = 'DEMAND' + ','.join(str(tep) for tep in demands)
        hotwaterstring = 'HOTW' + str(hotwater)
        datalogger.log(stringout + tempstring + demandsstring + hotwaterstring + '\n')
        
        #zip temp and demands and join string
        outputstr = ' '.join([setup.settings['emonsocket']['hmnode'], str(hotwater)] + ['%s %d'%pair for pair in zip(encodedtemps, demands)])
    
        logging.debug(outputstr)
        return outputstr
    
class LocalDatalogger(object):
    """Manages a local daily data logging file."""
    def __init__(self, logfolder):
        self._logfolder = logfolder
        
        self._outputfile = None
        self._openfilename = False
        self._file_day_stamp = False
        
        self._open_file(time.time())
    
    def _check_day(self, timestamp):
        """Open new file if the day has changed."""
        daystamp = int(timestamp/86400)
        if self._file_day_stamp != daystamp:
            self._close_file()
            self._open_file(timestamp)
    
    def _open_file(self, timestamp):
        """Open data file and store handle"""
        self._file_day_stamp = int(timestamp/86400)
        try:
            self._openfilename = self._logfolder + "/testlog"+str(self._file_day_stamp)+".txt"
            self._outputfile = open(self._openfilename,"a") #removed b
        except IOError as err:
            self._openfilename = False
            self._file_day_stamp = False
            logging.warning('failed to create log file : I/O error({0}): {1}'.format(err.errno, err.strerror))
        else:
            logging.info('opened file ' + self._openfilename)
    
    def _close_file(self):
        """Close data file."""
        if not self._file_day_stamp is False:
            self._outputfile.close()
            logging.info('closed file ' + self._openfilename)
            self._openfilename = False
            self._file_day_stamp = False
    
    def log(self, stringout):
        """Log data to todays log file."""
        self._check_day(time.time())
        if not self._file_day_stamp is False:
            try:
                self._outputfile.write(stringout)
            except IOError as err:
                self._close_file()
                logging.warning('failed to write to log file : I/O error({0}): {1}'.format(err.errno, err.strerror))
            else:
                logging.debug('logged to file:' + stringout)
             
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
logging_setup.initialize_logger_full(setup.settings['logging']['logfolder'], logging.WARN)

# tell the user what is happening
logging.info("1 wire bus reporting and hmstat reporting")
logging.info("  sample interval: "+str(sample_interval) + " seconds")

sensorlist1wire = initialise_1wire()

hmn = initialise_heatmiser(localconfigfile)

datalogger = LocalDatalogger(setup.settings['logging']['logfolder'])

logging.info("Entering reading loop")

# now loop forever reading the identified sensors
while 1:
    # determine how long to wait until next interval
    # note this will skip some if specified interval is too short
    #  - it finds the next after now, not next after last
    sleeptime = sample_interval - (time.time() % sample_interval)
    time.sleep(sleeptime)

    # get time now and record it
    tt = int(time.time()) # we only record to integer seconds
    
    output_message = ""
    
    logging.info("Logging cyle at " + str(tt))
    outputstr_1wire = get_1wire_data()
    if outputstr_1wire is not None:
        output_message += outputstr_1wire + '\r\n'
    outputstr_hmn = get_heatmiser_data()
    output_message += outputstr_hmn + '\r\n'

    if len(output_message > 0):
        try:
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.connect((setup.settings['emonsocket']['host'],int(setup.settings['emonsocket']['port'])))
            logging.info('socket send %s and %s'%(outputstr_1wire, outputstr_hmn))
            logging.debug(soc.sendall(output_message))
            soc.close()
        except IOError as err:
            logging.warning('could not connect to emonhub due to ' + str(err))
