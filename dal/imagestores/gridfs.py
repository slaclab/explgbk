from dal.imagestores.imagestore import ImageStore
import logging
import re

from bson import ObjectId
from gridfs import GridFS

from context import logbookclient

logger = logging.getLogger(__name__)


class GridFSIS(ImageStore):
    def store_file_and_return_url(
        self, experiment_name, filename, mimetype, filecontents
    ):
        expdb = logbookclient[experiment_name]
        fs = GridFS(expdb)
        fid = fs.put(filecontents)
        return "mongo://" + str(fid)

    def return_url_contents(self, experiment_name, remote_url):
        mtch = re.match("mongo://([\w]*)/(.*)", remote_url)
        if mtch:
            expdb = logbookclient[mtch.group(1)]
            fid = mtch.group(2)
        else:
            expdb = logbookclient[experiment_name]
            fid = remote_url.replace("mongo://", "")
        fs = GridFS(expdb)
        out = fs.get(ObjectId(fid))
        return out
