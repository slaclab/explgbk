from dal.imagestores.imagestore import ImageStore
import os
import logging
import tarfile
import io

from bson import ObjectId

from context import logbookclient, LOGBOOK_SITE

logger = logging.getLogger(__name__)


class TarIS(ImageStore):
    def __get_experiment_results_folder__(self, experiment_name):
        if LOGBOOK_SITE == "LCLS":
            expdb = logbookclient[experiment_name]
            instrument = expdb["info"].find_one()["instrument"].lower()
            results = os.path.join(
                "/reg/d/psdm/", instrument, experiment_name, "results"
            )
            return results
        return None

    def store_file_and_return_url(
        self, experiment_name, filename, mimetype, filecontents
    ):
        results_folder = self.__get_experiment_results_folder__(experiment_name)
        if not (
            results_folder
            and os.path.exists(results_folder)
            and os.path.isdir(results_folder)
        ):
            raise Exception(
                "Missing results folder for experiment %s %s"
                % (experiment_name, results_folder)
            )
        archive_folder = os.path.join(results_folder, "archive")
        if not os.path.exists(archive_folder):
            os.mkdir(archive_folder)
        with tarfile.open(os.path.join(archive_folder, "attachments.tar"), "a") as t:
            tinfo = tarfile.TarInfo(str(ObjectId()))
            filecontents.seek(0, 2)
            tinfo.size = filecontents.tell()
            filecontents.seek(0, 0)
            t.addfile(tinfo, filecontents)
            return "tar://" + tinfo.name

    def return_url_contents(self, experiment_name, remote_url):
        attachments_file = os.path.join(
            self.__get_experiment_results_folder__(experiment_name),
            "archive",
            "attachments.tar",
        )
        if not (attachments_file and os.path.exists(attachments_file)):
            raise Exception(
                "Missing attachments tar file for experiment %s %s"
                % (experiment_name, attachments_file)
            )

        fid = remote_url.replace("tar://", "")
        with tarfile.open(attachments_file, "r") as t:
            return io.BytesIO(t.extractfile(fid).read())
