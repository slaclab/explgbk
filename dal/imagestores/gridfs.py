from dal.imagestores.imagestore import ImageStore
import logging
import requests

from bson import ObjectId
from gridfs import GridFS

from context import logbookclient

logger = logging.getLogger(__name__)

class GridFSIS(ImageStore):
    def store_file_and_return_url(self, experiment_name, filename, mimetype, filecontents):
        expdb = logbookclient[experiment_name]
        fs = GridFS(expdb)
        fid = fs.put(filecontents)
        return "mongo://"+str(fid)

    def return_url_contents(self, experiment_name, remote_url):
        expdb = logbookclient[experiment_name]
        fs = GridFS(expdb)
        fid = remote_url.replace("mongo://", "")
        out = fs.get(ObjectId(fid))
        return out
