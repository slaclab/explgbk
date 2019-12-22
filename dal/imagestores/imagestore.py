import abc

class ImageStore(abc.ABC):
    @abc.abstractmethod
    def store_file_and_return_url(self, experiment_name, filename, mimetype, filecontents):
        """
        Store the file identified as filename as the specified filename; the contents of the file are in the file like filecontents object
        Return a URL that the store can later retrieve as a steamed response.
        """
        pass

    def return_url_contents(self, experiment_name, remote_url):
        """
        Return the contents of the specified URL in a form suitable for return with Flask's stream_with_context
        """
        pass
