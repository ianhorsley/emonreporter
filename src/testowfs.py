#!/usr/bin/env python
#!/usr/bin/python
import datetime
import numpy as N

#import pyownet

def main():
    # set the 1-Wire temperature sensor location and open the file
    device = "/mnt/1wire/uncached/28.2C1B4A050000/"
    
    #f = open(device + "demofile2.txt", "a")
    #f.write("Now the file has more content!")
    #f.close()
    
    # number of samples to read
    samples = 10

    # create a counter and arrays to store the sampled temperatures
    counter = 1
    readarray = N.zeros(samples)

    print("Starting Sample Capture")

    starttime = datetime.datetime.now()

    while counter < samples:
        # read the temperate to the array
        temperature = open(device + "temperature12", "r")
        t = temperature.read()
        temperature.close()
        readarray[counter] = float(t)
        print("%f C" % readarray[counter])
        counter = counter + 1
        print("%.2f time seconds" % (datetime.datetime.now() - starttime).total_seconds())

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
