import logging
from pathlib import Path
from typing import List

from botocore.exceptions import ClientError

from frundenbot import STATE_UNKNOWN

LOGGER = logging.getLogger(__name__)


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
        raise NotImplementedError()

    def get_mate(self) -> str or None:
        """
        Get the current availability of drinks.

        :return: Current availability of drinks
        """
        raise NotImplementedError()

    def set_open(self, state: int):
        """
        Set the current "Open" state
        :param state: new state
        """
        raise NotImplementedError()

    def get_open(self) -> int:
        """
        Get the last saved "Open" state
        """
        raise NotImplementedError()

    def set_notification_listeners(self, listeners: List[str]):
        """
        Set the list of chat_ids that registered for a notification
        :param listeners: new value
        """
        raise NotImplementedError()

    def get_notification_listeners(self) -> List[str]:
        """
        Get the list of chat_ids that registered for a notification
        :return: listeners
        """
        raise NotImplementedError()


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
        self.s3_client = boto3.resource('s3', region_name=region_name, aws_access_key_id=key,
                                        aws_secret_access_key=secret)
        self.bucket = bucket

    def set_mate(self, text):
        self._write('mate/status.txt', text)

    def get_mate(self) -> str or None:
        value = self._read('mate/status.txt')
        return value

    def set_open(self, state: int):
        self._write('open.txt', f"{state}")

    def get_open(self) -> int:
        value = self._read('open.txt')
        return int(value) if value else STATE_UNKNOWN

    def set_notification_listeners(self, listeners: List[str]):
        self._write('listeners.txt', "\n".join(listeners))

    def get_notification_listeners(self) -> List[str]:
        value = self._read('listeners.txt')
        if value:
            return value.splitlines()
        else:
            return []

    def _read(self, path: str) -> str or None:
        obj = self.s3_client.Object(self.bucket, path)
        try:
            return obj.get()['Body'].read().decode('utf-8')
        except ClientError as ex:
            if ex.response['Error']['Code'] == 'NoSuchKey':
                return None
            else:
                raise ex

    def _write(self, path: str, value: str):
        obj = self.s3_client.Object(self.bucket, path)
        obj.put(Body=value)


class FileStorage(Storage):
    """
    Storage implementation that uses a local directory as a storage backend.
    """

    def __init__(self, path: str):
        """
        Create a new file based storage backend.

        :param path: Path to the directory that should be used.
        """
        self.root_path = path

    def set_mate(self, text):
        self._write("mate/status.txt", text)

    def get_mate(self) -> str or None:
        return self._read('mate/status.txt')

    def set_open(self, state: int):
        self._write("open.txt", f"{state}")

    def get_open(self) -> int:
        value = self._read("open.txt")
        return int(value) if value else STATE_UNKNOWN

    def set_notification_listeners(self, listeners: List[str]):
        self._write("listeners.txt", "\n".join(listeners))

    def get_notification_listeners(self) -> List[str]:
        value = self._read("listeners.txt")
        if value:
            return value.splitlines()
        else:
            return []

    def _read(self, path: str) -> str or None:
        path = Path(f'{self.root_path}/{path}').expanduser().absolute()
        if path.exists() and path.is_file():
            with open(path, 'r') as file:
                return file.read()
        else:
            return None

    def _write(self, path: str, value: str):
        path = Path(f'{self.root_path}/{path}').expanduser().absolute()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w+') as file:
            file.write(value)
