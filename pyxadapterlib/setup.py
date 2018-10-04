import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'httplib2',
    'lxml',
    'pyramid',
    ]

setup(name='PyXadapterlib',
      version='1.8',
      description='X-road client/server library',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        ],
      author='Ahti Kelder',
      author_email='',
      url='',
      keywords='web wsgi xroad x-tee',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      )
