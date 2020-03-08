class Storage:
    """
    Interface for the storage backend of FrundenBot to make sure that all
    storage implementations provide the same functionality.
    """
    def set_mate(self, text):
        """
        Store a new message that represents the current availability of drinks.

        :param text: New message
        """
        raise NotImplementedError

    def get_mate(self):
        """
        Get the current availability of drinks.

        :return: Current availability of drinks
        """
        raise NotImplementedError


class S3Storage(Storage):
    """
    Storage implementation that uses AWS S3 as a storage backend.
    """
    def __init__(self, region_name: str, bucket: str, key: str, secret: str):
        """
        Create a new s3 storage backend.

        :param region_name: AWS region name, e.g. eu-central-1
        :param bucket: Unique bucket name that exists in the use region
        :param key: AWS access key ID which has access to the bucket
        :param secret: Secret access key of the key ID
        """
        import boto3
        self.s3_client = boto3.resource('s3', region_name=region_name, aws_access_key_id=key, aws_secret_access_key=secret)
        self.bucket = bucket

    def set_mate(self, text):
        obj = self.s3_client.Object(self.bucket, 'mate/status.txt')
        obj.put(Body=text)

    def get_mate(self):
        obj = self.s3_client.Object(self.bucket, 'mate/status.txt')
        return obj.get()['Body'].read().decode('utf-8')


class FileStorage(Storage):
    """
    Storage implementation that uses a local directory as a storage backend.
    """

    def __init__(self, path: str):
        """
        Create a new file based storage backend.

        :param path: Path to the directory that should be used.
        """
        self.path = path

    def set_mate(self, text):
        with open('{}/mate/status.txt'.format(self.path), 'w+') as file:
            file.write(text)

    def get_mate(self):
        with open('{}/mate/status.txt'.format(self.path), 'r') as file:
            return file.read()

