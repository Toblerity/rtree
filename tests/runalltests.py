import doctest
import glob

try:
    import pkg_resources
    pkg_resources.require('Rtree')
except:
    pass

for file in glob.glob('*.txt'):
    doctest.testfile(file, verbose=1)

