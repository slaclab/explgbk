__all__ = ["imagestore", "seaweed", "gridfs", "tar"]

from .seaweed import SeaWeed
from .tar import TarIS
from .gridfs import GridFSIS

def parseImageStoreURL(imagestoreurl):
    if imagestoreurl.startswith("http://"):
        return SeaWeed(imagestoreurl)
    elif imagestoreurl.startswith("mongo://"):
        return GridFSIS()
    elif imagestoreurl.startswith("tar://"):
        return TarIS()
    else:
        raise Exception("Cannot initialize image store with unknown scheme " + imagestoreurl)
