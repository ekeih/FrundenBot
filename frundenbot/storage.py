class Storage:

    def set_mate(self, text):
        raise NotImplementedError

    def get_mate(self):
        raise NotImplementedError


class S3Storage(Storage):

    def __init__(self, region_name: str, bucket: str, key: str, secret: str):
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

    def __init__(self, path: str):
        self.path = path

    def set_mate(self, text):
        with open('{}/mate/status.txt'.format(self.path), 'w+') as file:
            file.write(text)

    def get_mate(self):
        with open('{}/mate/status.txt'.format(self.path), 'r') as file:
            return file.read()

