import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.txt')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.txt')) as f:
    CHANGES = f.read()

requires = [
    'PyXadapterlib',
    'httplib2',
    'lxml',
    'pyramid',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'SQLAlchemy',
    'transaction',
    'zope.sqlalchemy',
    'waitress',
    ]

def globAll(prefix, path):
    li = []
    for root, dirs, files in os.walk(path):
        root2 = root[len(path):]
        if root.find('/.') > -1:
            continue
        if len(files) > 0:
            movefiles = [root + '/' + file for file in files if not file.startswith('.')]
            li.append((prefix + root2, movefiles))
    return li

wwwpath = '/var/www/html'
data_files = [('/usr/local/pyxadapter/apache', ['apache/populationdb.wsgi']),
             ]
data_files.extend(globAll(wwwpath + '/static', 'populationdb/static'))

setup(name='PyXadapterPopulationdb',
      version='1.7',
      description='X-road demo adapter (population registry)',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        ],
      author='Ahti Kelder',
      author_email='',
      url='',
      keywords='web wsgi bfg pyramid xroad',
      packages=find_packages(),
      include_package_data=True,
      data_files=data_files,
      zip_safe=False,
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = populationdb:main
      [console_scripts]
      initialize_Populationdb_db = populationdb.scripts.initializedb:main
      """,
      )
