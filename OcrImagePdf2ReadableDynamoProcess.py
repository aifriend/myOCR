import datetime as dt
import json
import os
import requests
import sys
import traceback

# from Doc2ReadOcrService import Doc2ReadOcrService
from common.s3.DynamoDbService import DynamoDbService, DynamoDbConnectionException
from common.s3.S3Service import S3Service
from commonsLib import loggerElk


class UnprocessableRequest(Exception):
    """Request is unprocessable, but no errors ocurred"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class ErrorProcessingRequest(Exception):
    """Errors while trying to process request"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class OcrImageDoc2ReadOcrDynamoProcess:
    def __init__(self):
        pass

    @staticmethod
    def clean_json(response_value):
        if isinstance(response_value, dict):
            for key, value in response_value.items():
                if response_value[key] is None:
                    response_value[key] = ''
                elif isinstance(response_value[key], str):
                    response_value[key] = response_value[key].replace("\"", "")
                    response_value[key] = response_value[key].replace(
                        "'", "\'")

                elif isinstance(response_value[key], dict):
                    OcrImageDoc2ReadOcrDynamoProcess.clean_json(
                        response_value[key])

    @staticmethod
    def process_element(message, app):
        logger = loggerElk(__name__)
        logger.Information(f'Message received')
        bucket = os.environ["BUCKET_REQUEST_STORAGE"]
        s3_service = S3Service(app=app, bucket=bucket, domain=None)
        request_uuid = ""

        try:
            request_uuid = message['body'].decode('utf8')
        except Exception as e:
            logger.Information(
                f'ERROR processing request_uuid: {request_uuid} ERROR -> {str(e)}',
                {
                    "request_uuid": request_uuid,
                    "event": "ERROR_DOC2READOCR", "status": "KO",
                    "endpoint_push": "", "code": 500
                })
            raise UnprocessableRequest(
                'Provided message is not a valid uuid')

        if request_uuid:
            try:
                dynamo_db_service = DynamoDbService(app)
                logger.Information(f'OcrImageDoc2ReadOcrQueueProcess::QUEUE- {request_uuid} Start enqueued process',
                                   {
                                       "request_uuid": request_uuid,
                                       "event": "ENQUEUED_DOC2READOCR", "status": "OK",
                                       "endpoint_push": "", "code": 200
                                   })

                db_item = dynamo_db_service.get_item("guid", request_uuid)
                if not db_item:
                    logger.Error(
                        f"Enqueued request doesnt have a dynamodb item guid: {request_uuid}")
                    return

                accepted_d = db_item["accepted_date"]
                accepted_date = dt.datetime.fromisoformat(accepted_d)
                obsoleting_date = accepted_date + dt.timedelta(hours=1)
                if db_item["status"] == "PROCESSING" and dt.datetime.now(dt.timezone.utc) > obsoleting_date:
                    logger.Information(f'Doc2ReadOcr enqueued and processing by 1 hour, SET RESPONSE AS TIMEOUT',
                                       {
                                           "request_uuid": request_uuid,
                                           "event": "ENQUEUED_DOC2READOCR", "status": "KO",
                                           "endpoint_push": "", "code": 408
                                       })

                    response_value = {
                        'status': 'False',
                        'statusCode': '408'
                    }
                else:
                    input_key = db_item["request"]
                    data_decoded = s3_service.get_byte_file(
                        input_key).decode('utf8')
                    input = json.loads(data_decoded.replace('\'', '\"'))
                    logger.Information(f'Message received -> Request parsed',
                                       {
                                           "request_uuid": request_uuid,
                                           "event": "ENQUEUED_DOC2READOCR", "status": "OK",
                                           "endpoint_push": "", "code": 200
                                       })

                    logger.Information(f'Db item -> {str(db_item)}',
                                       {
                                           "request_uuid": request_uuid,
                                           "event": "ENQUEUED_DOC2READOCR", "status": "OK",
                                           "endpoint_push": "", "code": 200
                                       })
                    dynamo_db_service.update_item(
                        "guid", request_uuid, "status", "PROCESSING")
                    logger.Information(
                        f'Db item status marked as "PROCESSING"')
                    logger.Information(f'Start doc2readOcr process')

                    from Doc2ReadOcrService import Doc2ReadOcrService, Doc2ReadOcrInput
                    service = Doc2ReadOcrService(app=app)
                    response_value = service.post(input)

                    if isinstance(response_value, tuple):  # error
                        response_value = {
                            'status': 'False',
                            'statusCode': response_value[1]
                        }
                    else:
                        OcrImageDoc2ReadOcrDynamoProcess.clean_json(
                            response_value)
                        for key, value in response_value.items():
                            if response_value[key] is None:
                                response_value[key] = ''

                logger.Information(f'doc2readOcr process ENDS',
                                   {
                                       "request_uuid": request_uuid,
                                       "event": "ENQUEUED_DOC2READOCR", "status": "OK",
                                       "endpoint_push": "", "code": 200
                                   })

                # storage result
                logger.Information(f'Uploading result to s3',
                                   {
                                       "request_uuid": request_uuid,
                                       "event": "ENQUEUED_DOC2READOCR", "status": "OK",
                                       "endpoint_push": "", "code": 200
                                   })
                response_s3_key = f"response_{request_uuid}.json"
                s3_service.upload_file(response_s3_key, json.dumps(
                    response_value, ensure_ascii=True).encode("utf-8"))
                logger.Information(f'Uploaded to s3')

                logger.Information(f'Updating response -> {response_s3_key}')
                dynamo_db_service.update_item(
                    "guid", request_uuid, "response", response_s3_key)
                logger.Information(f'Updating status -> PROCESSED')
                dynamo_db_service.update_item(
                    "guid", request_uuid, "status", "PROCESSED")
                now = dt.datetime.now(dt.timezone.utc).isoformat()
                logger.Information(f'Updating processed_date -> {str(now)}')
                dynamo_db_service.update_item("guid", request_uuid, "processed_date",
                                              now)
                logger.Information(f'Database item updated',
                                   {
                                       "request_uuid": request_uuid,
                                       "event": "ENQUEUED_DOC2READOCR", "status": "OK",
                                       "endpoint_push": "", "code": 200
                                   })
                if "endpoint_push" in db_item and db_item["endpoint_push"] and db_item["endpoint_push"] != "":
                    poll_url = os.environ["ASYNC_POLL_URL"]
                    logger.Information(
                        f'START enqueuing to feedback pull -> {poll_url}')
                    # Pasar elemento a la cola de feedback automatico

                    req = json.dumps({
                        "guid": request_uuid
                    })
                    success = False
                    dispatch_error = ""
                    try:
                        response = requests.put(
                            poll_url,
                            data=req,
                            headers={"Content-Type": "application/json"},
                            timeout=600
                        )
                        if response.status_code == 200:
                            success = True
                            logger.Information(f'guid {request_uuid} succesfull re-enqueued',
                                               {
                                                   "request_uuid": request_uuid,
                                                   "event": "REQUEST_ENQUEUED_FEEDBACK", "status": "OK",
                                                   "endpoint_push": "", "code": 200
                                               })
                        else:
                            dispatch_error = f"Error enqueueing to the feedback queue Code -> {response.status_code} message -> {response.text} with data -> {str(req)}"
                            logger.Information(
                                f'ERROR moving to feedback queue for guid {request_uuid} to url {poll_url} {dispatch_error}',
                                {
                                    "request_uuid": request_uuid,
                                    "event": "REQUEST_ENQUEUED_FEEDBACK", "status": "OK",
                                    "endpoint_push": "", "code": response.status_code
                                })
                    except Exception as e:
                        logger.Information(
                            f'ERROR moving to feedback queue for guid {request_uuid} to url {poll_url} with data {str(req)}',
                            {
                                "request_uuid": request_uuid,
                                "event": "REQUEST_ENQUEUED_FEEDBACK", "status": "KO",
                                "endpoint_push": "", "code": 500
                            })
                    if not success:
                        logger.Information(
                            f'Updating status -> DISPATCH_ERROR')
                        dynamo_db_service.update_item(
                            "guid", request_uuid, "status", "DISPATCH_ERROR")
                        now = dt.datetime.now(dt.timezone.utc).isoformat()
                        logger.Information(
                            f'Updating dispatch_error_date -> {str(now)}')
                        dynamo_db_service.update_item(
                            "guid", request_uuid, "dispatch_error_date", now)
                        logger.Information(
                            f'Updating dispatch_error -> {dispatch_error}')
                        dynamo_db_service.update_item(
                            "guid", request_uuid, "dispatch_error", dispatch_error)

                logger.Information(f'Finished process for guid {request_uuid}',
                                   {
                                       "request_uuid": request_uuid,
                                       "event": "DOC2READOCR_FINISH", "status": "OK",
                                       "endpoint_push": "", "code": 200
                                   })
            except DynamoDbConnectionException as e:
                traceback.print_exc(file=sys.stdout)
                logger.Information(
                    f'ERROR processing request_uuid {request_uuid} ERROR -> {str(e)}',
                    {
                        "request_uuid": request_uuid,
                        "event": "ERROR_DOC2READOCR", "status": "KO",
                        "endpoint_push": "", "code": 500
                    })
                raise e
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                logger.Information(
                    f'ERROR processing request_uuid {request_uuid} ERROR -> {str(e)}',
                    {
                        "request_uuid": request_uuid,
                        "event": "ERROR_DOC2READOCR", "status": "KO",
                        "endpoint_push": "", "code": 500
                    })
        else:
            logger.Information(
                f'ERROR processing empty message',
                {
                    "request_uuid": "",
                    "event": "ERROR_DOC2READOCR", "status": "KO",
                    "endpoint_push": "", "code": 500
                })
