#!/usr/bin/env python3

""" program to interogate 1-wire bus and report all known temperatures
# with some commentary

# by ian
# This code has no warranty, including any implied fitness for purpose
# or implied merchantability.  It's free, and worth every penny.
# 2018/11/02
# updated to add more error catching and remove trend code

# /lib/systemd/system/1wireemon.service
# /home/pi/data/emonhub.conf"""

# standard library modules used in code
from __future__ import absolute_import
from __future__ import division

import sys
import time
import argparse
import socket
import logging
from serial import SerialException
import pyownet # use OWFS pyownet module

# hm imports
from heatmisercontroller import network, logging_setup
from heatmisercontroller.exceptions import HeatmiserResponseError, HeatmiserControllerTimeError
import heatmisercontroller.setup as hms

import emonhub_coder

def initialise_setup(configfile):
    """Initialise setup loading configuration file."""

    # Initialize controller setup
    try:
        int_setup = hms.HeatmiserControllerFileSetup(configfile)
    except hms.HeatmiserControllerSetupInitError as errcatch:
        logging.error(errcatch)
        sys.exit("Unable to load configuration file: " + configfile)

    return int_setup, configfile

def initialise_1wire(setup):
    """Initialise 1 wire network and check for sensors"""
    logging.debug("locate sensors and take initial readings:")
    expected_sensors = setup.settings['1wire']['sensors']

    try:
        # connect to localhost port where owserver should be running
        ownet = pyownet.protocol.proxy(host='localhost', port=setup.settings['1wire']['owport'])
        found_sensors = _log_expected_sensors(ownet, expected_sensors)
    except (pyownet.protocol.Error) as errcatch:
        logging.warning('Could not connect to ow due to %s', str(errcatch))
        return []

    rawlist = _log_other_sensors(ownet, expected_sensors)

    logging.info("bus search done for sensors - %i found - %i temperature - %i missing",
                    len(rawlist),
                    found_sensors,
                    len(expected_sensors) - found_sensors)

    if found_sensors == 0:
        return ownet, []

    return ownet, expected_sensors

def _check_sensor(ownetobj, name, type_label):
    """Check whether sensor is temperature or not"""
    try:
        if ownetobj.present(name + '/latesttemp'):
            # get the temperature from that sensor
            temp = float(ownetobj.read(name + '/latesttemp'))
            logging.info("%s sensor, %s, found with initial reading %s.",
                            type_label, name, temp)
        else:
            # log the non temperature sensors
            logging.warning("%s sensor, %s, is a non temperature sensor that won't be logged.",
                                type_label, name)
            return 0
    except pyownet.protocol.Error:
        logging.warning("%s sensor, %s, went away during setup.", type_label, name)
        return 0

    return 1

def _log_expected_sensors(ownetobj, expected_sensors):
    """Count expected sensors that are avaliable"""
    _start_conversion(ownetobj)

    found_sensors = 0 # initialise number of expected temperature sensors found so far
    for sensor in expected_sensors:
        #logging.info("  considering " + str(s) + ": ")
        if ownetobj.present(sensor):
            found_sensors += _check_sensor(ownetobj, sensor, "Expected")
        else:
            logging.warning("Expected sensor, %s, not found.", sensor)
    return found_sensors

def _log_other_sensors(ownetobj, expected_sensors):
    """Get all sensor list and log any that are unexpected."""
    try:
        # list every sensor on the bus added that could be added to the list
        rawlist = ownetobj.dir()
    except (pyownet.protocol.Error) as errcatch:
        logging.warning('Could not read list and run concersion on ow due to %s', str(errcatch))

    for sensor in rawlist:
        if sensor[:-1] not in expected_sensors:
            _check_sensor(ownetobj, sensor[:-1], "New")

    return rawlist

def _start_conversion(ownetobj):
    """Start simultaneous temperature conversion and wait"""
    try:
        ownetobj.write('simultaneous/temperature', data=b'1')    # begin conversions
        time.sleep(0.75)                                   # need to wait for conversion
    except (pyownet.protocol.Error) as errcatch:
        logging.warning('Could not run conversion on ow due to %s', str(errcatch))
        raise

def get_1wire_data(setup, ownetobj, expected_sensors, read_time_out, datalogger):
    """Get data from 1 wire network and and return formatted string"""
    temps = list() # list of temps
    result_count = 0  # count results
    # reset output string
    outputstr = setup.settings['emonsocket']['node']

    try:
        _start_conversion(ownetobj)
    except pyownet.protocol.Error:
        return temps, result_count, ''


    # work through list of sensors
    for sensor in expected_sensors:
        temp = _read_temp_sensor(ownetobj, sensor, read_time_out, datalogger, setup)
        temps.append(temp)
        if temp is not float(setup.settings['emonsocket']['temperaturenull']):
            result_count += 1
        outputstr += ' ' + ' '.join(map(str,emonhub_coder.encode("h", round(temp * 10 ))))

    logging.debug(outputstr)

    if result_count == 0:
        return temps, result_count, ''
    return temps, result_count, outputstr + '\r\n'

def _read_temp_sensor(ownetobj, sensor, read_time_out, datalogger, setup):
    """Read temperature sensor and return result"""
    try:  # just in case it has been unplugged
        # get the temperature from that sensor
        temp = float(ownetobj.read(sensor + '/latesttemp'))
    except pyownet.protocol.Error:  # it has been unplugged
        logging.warning('Sensor %s gone away - ignoring', sensor)
        temp = float(setup.settings['emonsocket']['temperaturenull'])
        #continue  # so we'll jump to the next in the list
    else:
        # print sensor name and current value
        logging.info( 'Logging Sensor {!s}: {:-6.2f}'.format(sensor, temp))
        stringout = '{}:{!s}:{:+06.2f}\n'.format(read_time_out, sensor, temp)
        datalogger.log(stringout)
    return temp

def initialise_heatmiser(configfile=None):
    """Initialise heatmiser network and check for sensors"""
    logging.info("initialising hm network")
    try:
        hm_network = network.HeatmiserNetwork(configfile)
    except (SerialException, HeatmiserResponseError):
        return None

    # CYCLE THROUGH ALL CONTROLLERS
    for current_controller in hm_network.controllers:
        logging.info("Getting all data control %2d in %s",
                        current_controller.set_address, current_controller.set_long_name)
        _heatmiser_initial_read(current_controller)

    return hm_network

def _heatmiser_initial_read(controller):
    """Get all data from a heatmiser sensor"""
    try:
        controller.read_all()
        disptext = "C%d Air Temp is %.1f from type %.f and Target set %d Demand %d" % (
                    controller.set_address, controller.read_air_temp(),
                    controller.read_air_sensor_type(), controller.setroomtemp,
                    controller.heatingdemand)
    except (HeatmiserResponseError, HeatmiserControllerTimeError) as errcatch:
        logging.warning("C%d in %s Failed to Read due to %s",
                            controller.set_address,
                            controller.name.ljust(4),
                            str(errcatch))
    else:
        if controller.is_hot_water:
            logging.info("%s Hot Water Demand %d", disptext, controller.hotwaterdemand)
        else:
            logging.info(disptext)

def get_heatmiser_data(read_time_out):
    """Get data from heatmiser network and and return formatted string"""
    try:
        #read all fields needed now
        allread = hmn.All.read_fields(['sensorsavaliable',
                                        'airtemp',
                                        'remoteairtemp',
                                        'heatingdemand',
                                        'hotwaterdemand'], 0)
        #read currenttime, which will get time from sensor every 24 hours and hence check .
        hmn.All.read_field('currenttime')
    except (SerialException, HeatmiserResponseError, HeatmiserControllerTimeError) as errcatch:
        logging.warning("All failed to read due to %s", str(errcatch))
        return ''
    else:
        #get demands and temps replacing nones
        demands = [99 if row is None or row[3] is None else row[3] for row in allread]
        hotwater = 2 if allread is None or allread[0] is None else allread[0][4]
        temps = [float(setup.settings['emonsocket']['temperaturenull'])
                    if temp is None else temp for temp in hmn.All.read_air_temp()]

        logging.debug('Temps %s', temps)
        logging.debug('Demands %s', demands + [hotwater])

        #enocde using emonhubs own module
        encodedtemps = [' '.join(map(str,emonhub_coder.encode("h",temp * 10 ))) for temp in temps ]

        logging.info('Logging heatmiser data')
        stringout = str(read_time_out)
        tempstring = ':TEMP' + ','.join(str(tep) for tep in temps)
        demandsstring = 'DEMAND' + ','.join(str(tep) for tep in demands)
        hotwaterstring = 'HOTW' + str(hotwater)
        datalogger.log(stringout + tempstring + demandsstring + hotwaterstring + '\n')

        #zip temp and demands and join string
        outputstr = ' '.join([setup.settings['emonsocket']['hmnode'], str(hotwater)]
                                + ['%s %d'%pair for pair in zip(encodedtemps, demands)])

        logging.debug(outputstr)
        return outputstr + '\r\n'

class LocalDatalogger():
    """Manages a local daily data logging file."""
    def __init__(self, logfolder):
        self._logfolder = logfolder

        self._outputfile = None
        self._openfilename = False
        self._file_day_stamp = False

        self._open_file(time.time())

    def _check_day(self, timestamp):
        """Open new file if the day has changed."""
        daystamp = timestamp//86400
        if self._file_day_stamp != daystamp:
            self._close_file()
            self._open_file(timestamp)

    def _open_file(self, timestamp):
        """Open data file and store handle"""
        self._file_day_stamp = timestamp//86400
        try:
            self._openfilename = self._logfolder + "/testlog"+str(self._file_day_stamp)+".txt"
            self._outputfile = open(self._openfilename,"a") #removed b
        except IOError as errcatch:
            self._openfilename = False
            self._file_day_stamp = False
            logging.warning('failed to create log file : I/O error(%d): %s',
                                errcatch.errno, errcatch.strerror)
        else:
            logging.info('opened file %s', self._openfilename)

    def _close_file(self):
        """Close data file."""
        if self._file_day_stamp is not False:
            self._outputfile.close()
            logging.info('closed file %s', self._openfilename)
            self._openfilename = False
            self._file_day_stamp = False
    
    def log(self, stringout):
        """Log data to todays log file."""
        self._check_day(time.time())
        if self._file_day_stamp is not False:
            try:
                self._outputfile.write(stringout)
            except IOError as errcatch:
                self._close_file()
                logging.warning('failed to write to log file : I/O error(%d): %s',
                                    errcatch.errno, errcatch.strerror)
            else:
                logging.debug('logged to file: %s', stringout)

def get_args(desc_text):
    """Setups and parser and processes the arguements"""
    # set up parser with command summary
    parser = argparse.ArgumentParser(
            description=desc_text)
    # set up arguments with associated help and defaults
    parser.add_argument('-i',
            dest='sample_interval',
            help='interval in seconds between samples',
            default='30')
    # Configuration file
    parser.add_argument("--config-file", action="store",
                        help='Config file', default=sys.path[0] + '/../conf/emonreporter.conf')
    # Log file
    parser.add_argument('--logfile', action='store', type=argparse.FileType('a'),
                        help='Log file (default: log to Standard error stream STDERR)')
            
    # process the arguments
    return parser.parse_args()

def send_message(setuparray, message_text):
    """Send a message over socket interface."""
    if len(message_text) > 0:
        try:
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.connect((setuparray.settings['emonsocket']['host'],
                            int(setuparray.settings['emonsocket']['port'])))
            logging.info('socket send %s', message_text)
            logging.debug(soc.sendall(message_text.encode('utf-8')))
            soc.close()
        except IOError as mainerrcatch:
            logging.warning('could not connect to emonhub due to %s', mainerrcatch)


if __name__ == "__main__":

    args = get_args('Rolling 1-wire and heatmiser temperatures report')
    
    # turn the arguments into numbers
    sample_interval=float(args.sample_interval)

    setup, localconfigfile = initialise_setup(args.config_file)

    #setup logging
    logging_setup.initialize_logger_full(setup.settings['logging']['logfolder'], logging.DEBUG)

    # tell the user what is happening
    logging.info("1 wire bus reporting and hmstat reporting")
    logging.info("  sample interval: %d seconds", sample_interval )

    onewirenetwork, sensorlist1wire = initialise_1wire(setup)

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
        read_time = int(time.time()) # we only record to integer seconds
            
        logging.info("Logging cyle at %d", read_time)
        _, _, output_message = get_1wire_data(setup, onewirenetwork, sensorlist1wire, read_time, datalogger)
        
        if hmn is not None:
            output_message += get_heatmiser_data(read_time)

        send_message(setup, output_message)
