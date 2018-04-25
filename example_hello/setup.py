import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'pyxadapterlib>=1.7',
    'pyramid',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'waitress',
    ]

setup(name='PyXadapterHello',
      version='1.7',
      description='X-road demo adapter',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        ],
      author='Ahti Kelder',
      author_email='',
      url='',
      keywords='web wsgi xroad',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = hello:main
      """,
      )
