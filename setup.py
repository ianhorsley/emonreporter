"""Build setup for package"""
from __future__ import absolute_import
from setuptools import setup

def readme():
    """Method to add readme file as long_description."""
    with open('README.md') as fhandle:
        return fhandle.read()

setup(name='emonreporter',
      version='0.41',
      description='Python scripts to process room temperatures and apply to Heatmiser network.',
      long_description=readme(),
      classifiers=[
        'Programming Language :: Python :: 2.7',
      ],
      url='https://github.com/ianhorsley/emonreporter',
      author='Ian Horsley',
      #author_email='flyingcircus@example.com',
      license='GNU v3.0',
      packages=['emonreporter'],
      install_requires=[
        'requests',
        'logging',
        'pyserial',
        'configobj',
        'heatmisercontroller'
      ],
      test_suite="tests",
      include_package_data=True,
      zip_safe=False)
