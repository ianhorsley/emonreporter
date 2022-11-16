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

import time
import logging

# hm imports
from heatmisercontroller import logging_setup

from rept_1wire_hmv2 import initialise_setup, initialise_1wire, get_1wire_data
from rept_1wire_hmv2 import LocalDatalogger, get_args, send_message

args = get_args('Rolling 1-wire temperatures report')

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

    logging.info("Logging cyle at %d", read_time)
    output_message = get_1wire_data(onewirenetwork, sensorlist1wire)

    send_message(setup, output_message)
