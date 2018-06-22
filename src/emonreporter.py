#!/usr/bin/env python

"""

  This code is released under the ....
  
  Ian Horsley

"""

import sys
# import time
import logging
import logging.handlers
import signal
import argparse
# import pprint
# import Queue

# import emonhub_setup as ehs
# import emonhub_reporter as ehr
# import emonhub_interfacer as ehi
# import emonhub_coder as ehc

"""class EmonReporter

Monitors data sensor network, and sends data to EmonHub 
through scoket interface.

Communicates with the user through an ??? EmonHubSetup

"""


class EmonReporter(object):
    
    __version__ = 'Development Version (rc0.1)'
    
    def __init__(self, setup):
        """Setup an emonReporter.
        
        Interface (EmonHubSetup): User interface to the hub.
        
        """

        # Initialize exit request flag
        self._exit = False

        # Initialize setup and get settings
        #self._setup = setup
        #settings = self._setup.settings
        
        # socket config for emon connection
        self._host = 'localhost'
        self._port = 50011
        self._node = '18' # for 1 wire bus
        self._hmnode = '27' # for hm stat reporting
        
        self._sample_interval = 30
        
        # Initialize logging
        self._log = logging.getLogger("EmonReporter")
        self._set_logging_level('INFO', False)
        self._log.info("EmonReporter %s" % self.__version__)
        self._log.info("Opening reporter...")
        
        # Initialize Interfacers
        self._interfacers = {}

        # Update settings
        self._update_settings(settings)
        
    def run(self):
        """Launch the reporter.
        
        Monitor the COM port and process data.
        Check settings on a regular basis.

        """

        # Set signal handler to catch SIGINT and shutdown gracefully
        signal.signal(signal.SIGINT, self._sigint_handler)
        
        # Until asked to stop
        while not self._exit:
            pass
            # # Run setup and update settings if modified
            # self._setup.run()
            # if self._setup.check_settings():
                # self._update_settings(self._setup.settings)
            
            # # For all Interfacers
            # for I in self._interfacers.itervalues():
                # # Execute run method
                # I.run()
                # # Read socket
                # values = I.read()
                # # If complete and valid data was received
                # if values is not None:
                    # # Place a copy of the values in a queue for each reporter
                    # for name in self._reporters:
                        # # discard if reporter 'pause' set to 'all' or 'in'
                        # if 'pause' in self._reporters[name]._settings \
                                # and str(self._reporters[name]._settings['pause']).lower() in \
                                # ['all', 'in']:
                            # continue
                        # self._queue[name].put(values)

            # # Sleep until next iteration
            # time.sleep(0.2)
         
    def close(self):
        """Close reporter. Do some cleanup before leaving."""
        
        self._log.info("Exiting hub...")

        # for I in self._interfacers.itervalues():
            # I.close()

        # for R in self._reporters.itervalues():
            # R.stop = True
            # R.join()

        self._log.info("Exit completed")
        logging.shutdown()

    def _sigint_handler(self, signal, frame):
        """Catch SIGINT (Ctrl+C)."""
        
        self._log.debug("SIGINT received.")
        # reporter should exit at the end of current iteration.
        self._exit = True

    def _update_settings(self, settings):
        """Check settings and update if needed."""

        # EmonHub Logging level
        if 'loglevel' in settings['hub']:
            self._set_logging_level(settings['hub']['loglevel'])
        else:
            self._set_logging_level()


        # Create a place to hold buffer contents whilst a deletion & rebuild occurs
        self.temp_buffer = {}

        # Interfacers
        for name in self._interfacers.keys():
            # Delete interfacers if not listed or have no 'Type' in the settings without further checks
            # (This also provides an ability to delete & rebuild by commenting 'Type' in conf)
            if not name in settings['interfacers'] or not 'Type' in settings['interfacers'][name]:
                pass
            else:
                try:
                    # test for 'init_settings' and 'runtime_setting' sections
                    settings['interfacers'][name]['init_settings']
                    settings['interfacers'][name]['runtimesettings']
                except Exception as e:
                    # If interfacer's settings are incomplete, continue without updating
                    self._log.error("Unable to update '" + name + "' configuration: " + str(e))
                    continue
                else:
                    # check init_settings against the file copy, if they are the same move on to the next
                    if self._interfacers[name].init_settings == settings['interfacers'][name]['init_settings']:
                        continue
            # Delete interfacers if setting changed or name is unlisted or Type is missing
            self._log.info("Deleting interfacer '%s' ", name)
            self._interfacers[name].stop = True
            del(self._interfacers[name])

        for name, I in settings['interfacers'].iteritems():
            # If interfacer does not exist, create it
            if name not in self._interfacers:
                try:
                    if not 'Type' in I:
                        continue
                    self._log.info("Creating " + I['Type'] + " '%s' ", name)
                    if I['Type'] in ('EmonModbusTcpInterfacer','EmonFroniusModbusTcpInterfacer') and not pymodbus_found :
                        self._log.error("Python module pymodbus not installed. unable to load modbus interfacer")
                    # This gets the class from the 'Type' string
                    interfacer = getattr(ehi, I['Type'])(name,**I['init_settings'])
                    interfacer.set(**I['runtimesettings'])
                    interfacer.init_settings = I['init_settings']
                    interfacer.start()
                except ehi.EmonHubInterfacerInitError as e:
                    # If interfacer can't be created, log error and skip to next
                    self._log.error("Failed to create '" + name + "' interfacer: " + str(e))
                    continue
                except Exception as e:
                    # If interfacer can't be created, log error and skip to next
                    self._log.error("Unable to create '" + name + "' interfacer: " + str(e))
                    continue
                else:
                    self._interfacers[name] = interfacer
            else:
                # Otherwise just update the runtime settings if possible
                if 'runtimesettings' in I:
                    self._interfacers[name].set(**I['runtimesettings'])

        if 'nodes' in settings:
            ehc.nodelist = settings['nodes']

    def _set_logging_level(self, level='WARNING', log=True):
        """Set logging level.
        
        level (string): log level name in 
        ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        
        """

        # Ensure "level" is all upper case
        level = level.upper()
        
        # Check level argument is valid
        try:
            loglevel = getattr(logging, level)
        except AttributeError:
            self._log.error('Logging level %s invalid' % level)
            return False
        except Exception as e:
            self._log.error('Logging level %s ' % str(e))
            return False
        
        # Change level if different from current level
        if loglevel != self._log.getEffectiveLevel():
            self._log.setLevel(level)
            if log:
                self._log.info('Logging level set to %s' % level)

        
if __name__ == "__main__":

    # Command line arguments parser
    parser = argparse.ArgumentParser(description='emonReporter')
    
    # Configuration file
    parser.add_argument("--config-file", action="store",
                        help='Configuration file', default=sys.path[0]+'/../conf/emonreporter.conf')
    # Log file
    parser.add_argument('--logfile', action='store', type=argparse.FileType('a'),
                        help='Log file (default: log to Standard error stream STDERR)')
    # Show settings
    parser.add_argument('--show-settings', action='store_true',
                        help='show settings and exit (for debugging purposes)')
    # Show version
    parser.add_argument('--version', action='store_true',
                        help='display version number and exit')
    # Parse arguments
    args = parser.parse_args()
    
    # Display version number and exit
    if args.version:
        print('emonReporter %s' % EmonReporter.__version__)
        sys.exit()

    # Logging configuration
    logger = logging.getLogger("EmonReporter")
    if args.logfile is None:
        # If no path was specified, everything goes to sys.stderr
        loghandler = logging.StreamHandler()
    else:
        # Otherwise, rotating logging over two 5 MB files
        # If logfile is supplied, argparse opens the file in append mode,
        # this ensures it is writable
        # Close the file for now and get its path
        args.logfile.close()
        loghandler = logging.handlers.RotatingFileHandler(args.logfile.name,
                                                       'a', 5000 * 1024, 1)
    # Format log strings
    loghandler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(loghandler)

    # # Initialize reporter setup
    # try:
        # setup = ehs.EmonHubFileSetup(args.config_file)
    setup = None
    # except ehs.EmonHubSetupInitError as e:
        # logger.critical(e)
        # sys.exit("Unable to load configuration file: " + args.config_file)
 
    # # If in "Show settings" mode, print settings and exit
    # if args.show_settings:
        # setup.check_settings()
        # pprint.pprint(setup.settings)
    
    # Otherwise, create, run, and close EmonHub instance
    # else:
    try:
        reporter = EmonReporter(setup)
    except Exception as e:
        sys.exit("Could not start EmonReporter: " + str(e))
    else:
        reporter.run()
        # When done, close reporter
        reporter.close()

