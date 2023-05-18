import base64
import boto3
import io
import warnings

from commonsLib import loggerElk

warnings.filterwarnings('ignore')  # "error", "ignore", "always", "default", "module" or "once"


class S3File:
    def __init__(self, s3_element):
        self.Key = s3_element['Key']
        self.Size = s3_element['Size']

    def get_category(self):
        spl = self.Key.split("/")
        if len(spl) >= 2:
            return spl[len(spl) - 2]
        elif len(spl) == 1:
            return spl[0]
        else:
            raise Exception(f"The element with key {self.Key} is not in a folder for category")


class S3Service(object):
    TIMEOUT = 99999

    def __init__(self, app, bucket, domain=""):
        self.bucket = bucket
        self.domain = domain
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.__s3Session = None
        self.logger = loggerElk(__name__)
        try:
            match = next(d for d in app.config['AWS']['BUCKETS'] if d['ID'] == bucket)
            self.aws_access_key_id = match['ACCESS_KEY_ID']
            self.aws_secret_access_key = match['SECRET_ACCESS_KEY']
            real_name = match.get('REAL_NAME', None)
            if real_name is not None:
                self.bucket = real_name
        except Exception:
            match = next(d for d in app.config['AWS']['BUCKETS'] if d['ID'] == 'DEFAULT')
            self.aws_access_key_id = match['ACCESS_KEY_ID']
            self.aws_secret_access_key = match['SECRET_ACCESS_KEY']

        if self.aws_access_key_id is None or self.aws_secret_access_key is None:
            raise Exception('No AWS credentials found')

        self.getS3Session()

    def getS3Session(self):

        if self.__s3Session is None:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
            self.__s3Session = session

        return self.__s3Session

    def getS3Client(self):
        if self.__s3Session is None:
            session = self.getS3Session()
        else:
            session = self.__s3Session
        return session.client(u's3')

    def get_files_from_s3(self, altDomain=None):
        try:
            documents = []
            doma = self.domain
            if altDomain:
                doma = altDomain
            for doc in self.__get_all_s3_objects(Bucket=self.bucket, Prefix=doma):
                documents.append(S3File(doc))

            return documents
        except Exception as e:
            raise e

    def __get_all_s3_objects(self, **base_kwargs):
        continuation_token = None
        while True:
            list_kwargs = dict(MaxKeys=1000, **base_kwargs)
            if continuation_token:
                list_kwargs['ContinuationToken'] = continuation_token

            client = self.getS3Client()
            response = client.list_objects_v2(**list_kwargs)
            yield from response.get('Contents', [])
            if not response.get('IsTruncated'):  # At the end of the list?
                break
            continuation_token = response.get('NextContinuationToken')

    def check_file(self, key):
        try:
            client = self.getS3Client()
            client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def get_txt_file(self, key, retry=True):
        try:
            bytes_buffer = io.BytesIO()
            client = self.getS3Client()
            client.download_fileobj(Bucket=self.bucket, Key=key, Fileobj=bytes_buffer)
            data_decoded = bytes_buffer.getvalue()
            return base64.b64decode(data_decoded).decode('utf-8')
        except Exception as e:
            if retry:
                return self.get_txt_file(key, False)
            raise e

    def get_byte_file(self, key, retry=True):
        try:
            bytes_buffer = io.BytesIO()
            client = self.getS3Client()
            client.download_fileobj(Bucket=self.bucket, Key=key, Fileobj=bytes_buffer)
            data_decoded = bytes_buffer.getvalue()
            return data_decoded
        except Exception as e:
            if retry:
                return self.get_byte_file(key, False)
            raise e

    def upload_file(self, key, content):
        client = self.getS3Client()
        response = client.put_object(
            Bucket=self.bucket,
            Key=str(key),
            Body=content
        )
        return response

    @staticmethod
    def s3_check_by_extension(s3_elements, extension):
        extension = extension.upper()
        for obj in s3_elements:
            if obj.Size > 0 and obj.Key.upper().endswith(f'.{extension}'):
                return True
        return False

    def checkCacheS3(self, key):
        self.logger.Information(f'Checking S3 cache: {key}')
        try:
            data_cached = self.get_byte_file(key)
            self.logger.Information(f'S3 cache found for: {key}')
            return data_cached.decode('utf-8')
        except:
            self.logger.Information(f'No S3 cache found for: {key}')
            return None

    def checkCacheS3Exists(self, key):
        self.logger.Information(
            f"OcrImageDoc2ReadOcrResource::POST- {key} Checking S3 cache: {key}")
        try:
            return self.check_file(key)
        except:
            self.logger.Information(
                f"OcrImageDoc2ReadOcrResource::POST- {key} No S3 cache found for: {key}")
            return None

    def delete_file(self, key):
        try:
            client = self.getS3Client()
            client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            self.logger.Information(
                f"OcrImageDoc2ReadOcrResource::POST- Error deleting {key}")
            return False
