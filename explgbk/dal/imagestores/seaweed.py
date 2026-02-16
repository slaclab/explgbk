from explgbk.dal.imagestores.imagestore import ImageStore

import logging
import io
import requests

logger = logging.getLogger(__name__)


class SeaWeed(ImageStore):
    def __init__(self, imagestoreurl):
        self.imagestoreurl = imagestoreurl

    def store_file_and_return_url(
        self, experiment_name, filename, mimetype, filecontents
    ):
        isloc = requests.post(self.imagestoreurl + "dir/assign").json()
        imgurl = isloc["publicUrl"] + isloc["fid"]
        logger.info("Posting attachment %s to URL %s", filename, imgurl)
        files = {
            "file": (
                filename,
                filecontents,
                mimetype,
                {"Content-Disposition": "inline; filename=%s" % filename},
            )
        }
        requests.post(imgurl, files=files)
        return imgurl

    def return_url_contents(self, experiment_name, remote_url):
        resp = requests.get(remote_url, stream=True)
        if not resp:
            return None
        return io.BytesIO(resp.content)
