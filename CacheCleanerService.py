import os
import sys

# Our deps
from common.s3.S3Service import S3Service
from commonsLib import loggerElk


class CacheCleanerService:
    ELK_ENABLED = os.environ["ELK_ENABLED"]
    if isinstance(ELK_ENABLED, str):
        ELK_ENABLED = True if ELK_ENABLED == "True" else False

    print(f"ELK_ENABLED: {ELK_ENABLED}")
    logger = loggerElk(__name__)
    DEFAULT_TXT_LEN_FOR_SKIP = 100

    def __init__(self, app, *args, **kwargs):
        self.app = app

    def post(self, input):
        try:
            self.logger.Information('CacheCleanerService::POST - init.')
            self.logger.Information(f'CacheCleanerService::POST - input: {input}')
            key = input['key']
            bucket = input['bucket']
            self.logger.Debug(f'OcrImageDoc2ReadOcrResource::POST- Key: {key} Bucket: {bucket}')

            s3_service = S3Service(
                app=self.app, bucket=bucket, domain=None)

            terminations = [".readOcr.pdf", ".txt", ".nonnative.txt"]

            actions_executed = []
            for termination in terminations:
                file_name = key + termination
                action = self.delete_cache_file(file_name, s3_service)
                if action:
                    actions_executed.append(f"{file_name} has been deleted.")

            return {
                'status': 'True',
                'statusCode': 200,
                'actions': actions_executed
            }
        except Exception as e:
            self.logger.Error(
                f'ERROR - OcrImageDoc2ReadOcrResource::POST- {key} ' + str(e.args), sys.exc_info())
            # return {'message': 'Something went wrong: ' + str(e)}, 500
            return {
                'status': 'False',
                'statusCode': 500,
                'message': str(e)
            }

    def delete_cache_file(self, file_key, s3_service):
        if s3_service.checkCacheS3Exists(file_key):
            return s3_service.delete_file(file_key)
        return None
