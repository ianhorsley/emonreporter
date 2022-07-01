#!/usr/bin/env python
#!/usr/bin/python
import datetime
import numpy as N

import pyownet
from time import sleep

def main():
    ow = pyownet.protocol.proxy(host='localhost', port=4304)

    
    # set the 1-Wire temperature sensor location and open the file
    device = "/mnt/1wire/uncached/28.2C1B4A050000/"
    
    #f = open(device + "demofile2.txt", "a")
    #f.write("Now the file has more content!")
    #f.close()
    
    # number of samples to read
    samples = 10

    # create a counter and arrays to store the sampled temperatures
    counter = 0
    readarray = N.zeros(samples)

    print("Starting Sample Capture")

    starttime = datetime.datetime.now()

    while counter < samples:
        
        ow.write('simultaneous/temperature', data=b'1')    # begin conversions
        sleep(0.75)                                        # need to wait for conversion

        # read the temperate to the array
        for ts in ow.dir():#path='uncached'
            startreadtime = datetime.datetime.now()
            #print(ts)
            #print(ow.present(ts + 'latesttemp'))
            t = ow.read(ts + 'latesttemp')
            readarray[counter] = float(t)
            print("%f C" % readarray[counter])
            counter = counter + 1
            print("%.2f time seconds" % (datetime.datetime.now() - startreadtime).total_seconds())

    # stop the timer
    endtime = datetime.datetime.now()

    # calculate the samples per second
    totalseconds = (endtime - starttime).total_seconds()
    samplespersecond = samples / totalseconds

    averagetemperature = N.average(readarray)

    print("%.2f samples per seconds" % (samplespersecond))
    print("Average Temperature: %.2f" % (averagetemperature))


if __name__ == "__main__":
    main()
