"""EmonHub_Coder

Provides functions to code and decode data being sent to emonhub.

"""

from __future__ import absolute_import
import struct

# Ensure little-endian & standard sizes used
ENDIAN_TYPE = '<'

# set the base data type to bytes
BASE_TYPE = 'B'

# Data types & sizes (number of bytes)
DATA_CODES = {'b': '1', 'h': '2', 'i': '4', 'l': '4', 'q': '8', 'f': '4', 'd': '8',
             'B': '1', 'H': '2', 'I': '4', 'L': '4', 'Q': '8', 'c': '1', '?': '1'}

def check_datacode(datacode):
    """Check that data code is in the valid list"""

    # if datacode is valid return the data size in bytes
    if datacode in DATA_CODES:
        return int(DATA_CODES[datacode])

    # if not valid return False
    return False

def decode(datacode, frame):
    """decode a emonhub data frame"""

    # get data size from data code
    data_size = int(check_datacode(datacode))

    result = struct.unpack(ENDIAN_TYPE + datacode[0],
                            struct.pack(ENDIAN_TYPE + BASE_TYPE * data_size, *frame))
    return result[0]

def encode(datacode, value):
    """encode data in to an emonhub frame"""

    # get data size from data code
    data_size = int(check_datacode(datacode))

    #value = 60
    #datacode = "b"
    result = struct.unpack(ENDIAN_TYPE + BASE_TYPE * data_size,
                            struct.pack(ENDIAN_TYPE + datacode, value))
    return result
