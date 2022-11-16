"""Unittests for src.get_schedule module"""
import unittest
import logging
import os

from emonreporter.get_schedule import XmlGetter
from emonreporter.get_config import username, password, url, destfile

class TestXmlGetter(unittest.TestCase):
    """Low level serial send and recieve message tests"""
    def setUp(self):
        try:
            os.remove(destfile)
        except OSError:
            pass
    
    def test_password_error(self):
        getter = XmlGetter(username, 'bob')
        with self.assertRaises(IOError):
            getter.check_file(url, destfile)
        
    def test_file_error(self):
        getter = XmlGetter(username, password)
        with self.assertRaises(IOError):
            getter.check_file(url + "d", destfile)

    def test_download(self):
        getter = XmlGetter(username, password)
        self.assertEqual(getter.check_file(url, destfile), True)
        #should only be downloaded once
        self.assertEqual(getter.check_file(url, destfile), False)
       
if __name__ == '__main__':
    unittest.main()
