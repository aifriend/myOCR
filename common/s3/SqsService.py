import boto3
import warnings

from api import app

warnings.filterwarnings('ignore')  # "error", "ignore", "always", "default", "module" or "once"


class SqsService(object):
    TIMEOUT = 99999

    def __init__(self, queue):

        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.__Session = None

        try:
            match = next(d for d in app.config['AWS']['QUEUES'] if d['ID'] == queue)
            self.aws_access_key_id = match['ACCESS_KEY_ID']
            self.aws_secret_access_key = match['SECRET_ACCESS_KEY']
            real_name = match.get('REAL_NAME', None)
            if real_name is not None:
                self.bucket = real_name
        except Exception as e:
            match = next(d for d in app.config['AWS']['QUEUES'] if d['ID'] == 'DEFAULT')
            self.aws_access_key_id = match['ACCESS_KEY_ID']
            self.aws_secret_access_key = match['SECRET_ACCESS_KEY']

        if self.aws_access_key_id is None or self.aws_secret_access_key is None:
            raise Exception('No AWS credentials found')

        self.getSession()

    def getSession(self):

        if self.__Session is None:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
            self.__Session = session

        return self.__Session

    def getSQSClient(self):
        if self.__Session is None:
            session = self.getSession()
        else:
            session = self.__Session
        return session.client(u'sqs')

    def get_queue_url(self, request_queue):
        sqs = self.getSQSClient()
        response = sqs.get_queue_url(QueueName=request_queue)
        queue_url = response['QueueUrl']
        print(queue_url)
        return queue_url

    def enqueue_sqs(self, request_queue, message_attr, message_body):
        message_body = (
            message_body
        )
        sqs = self.getSQSClient()

        queue_url = self.get_queue_url(request_queue)

        # Send message to SQS queue
        response = sqs.send_message(
            QueueUrl=queue_url,
            DelaySeconds=10,
            MessageAttributes=message_attr,
            MessageBody=message_body
        )

        MessageId = response['MessageId']
        return MessageId

    def get_sqs_message(self, request_queue):
        # Create SQS client
        sqs = self.getSQSClient()
        queue_url = self.get_queue_url(request_queue)
        # Receive message from SQS queue
        response = sqs.receive_message(
            QueueUrl=queue_url,
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )
        try:
            message = response['Messages'][0]
            receipt_handle = message['ReceiptHandle']
            return 200, message, receipt_handle, queue_url
        except:
            return 204, None, None, None

    def delete_sqs_message(self, queue_url, receipt_handle):
        # Create SQS client
        sqs = self.getSQSClient()
        # Delete received message from queue
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )

    @staticmethod
    def _check_by_extension(_elements, extension):
        extension = extension.upper()
        for obj in _elements:
            if obj.Size > 0 and obj.Key.upper().endswith(f'.{extension}'):
                return True
        return False
