#!/usr/bin/env python

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

from rept_1wire_hmv2 import *

# set up parser with command summary
parser = argparse.ArgumentParser(
        description='Rolling 1-wire and heatmiser temperatures report')
# set up arguments with associated help and defaults
parser.add_argument('-i',
        dest='sample_interval',
        help='interval in seconds between samples',
        default='30')
# Configuration file
parser.add_argument("--config-file", action="store",
                    help='Configuration file', default=sys.path[0] + '/../conf/emonreporter.conf')
# Log file
parser.add_argument('--logfile', action='store', type=argparse.FileType('a'),
                    help='Log file (default: log to Standard error stream STDERR)')

# process the arguments
args=parser.parse_args()

# turn the arguments into numbers
sample_interval=float(args.sample_interval)

setup, localconfigfile = initialise_setup(args.config_file)

#setup logging
logging_setup.initialize_logger_full(setup.settings['logging']['logfolder'], logging.DEBUG)

# tell the user what is happening
logging.info("1 wire bus reporting")
logging.info("  sample interval: %d seconds", sample_interval )

onewirenetwork, sensorlist1wire = initialise_1wire()

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

    output_message = ''

    logging.info("Logging cyle at %d", read_time)
    output_message += get_1wire_data(onewirenetwork, sensorlist1wire)

    if len(output_message) > 0:
        try:
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.connect((setup.settings['emonsocket']['host'],
                            int(setup.settings['emonsocket']['port'])))
            logging.info('socket send %s', output_message)
            logging.debug(soc.sendall(output_message.encode('utf-8')))
            soc.close()
        except IOError as err:
            logging.warning('could not connect to emonhub due to %s', err)
