import boto3
import json
import os
import warnings
from botocore.exceptions import ClientError

# "error", "ignore", "always", "default", "module" or "once"
warnings.filterwarnings('ignore')


class DynamoDbConnectionException(Exception):
    pass


class DynamoDbService(object):

    def __init__(self, app):
        database = os.environ["DATABASE_CONFIG"]

        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.dynamo_table = None
        self.region = None
        self.__Session = None

        try:
            match = next(
                d for d in app.config['AWS']['DATABASES'] if d['ID'] == database)
            self.aws_access_key_id = match['ACCESS_KEY_ID']
            self.aws_secret_access_key = match['SECRET_ACCESS_KEY']
            self.dynamo_table = match['DYNAMO_TABLE']
            self.region = match['REGION']
        except Exception:
            match = next(
                d for d in app.config['AWS']['DATABASES'] if d['ID'] == 'DEFAULT')
            self.aws_access_key_id = match['ACCESS_KEY_ID']
            self.aws_secret_access_key = match['SECRET_ACCESS_KEY']
            self.dynamo_table = match['DYNAMO_TABLE']
            self.region = match['REGION']

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

    def getDynamoDbClient(self):
        if self.__Session is None:
            session = self.getSession()
        else:
            session = self.__Session
        return session.resource(u'dynamodb', region_name=self.region)

    def get_item(self, pk_name, pk_value):
        try:
            client = self.getDynamoDbClient()
            table = client.Table(self.dynamo_table)
            response = table.get_item(
                Key={
                    pk_name: pk_value,
                }
            )
        except ClientError as e:
            print(e.response['Error']['Message'])
            raise DynamoDbConnectionException(f'Unable to connect to DynamoDB table: {self.dynamo_table}')
        else:
            print(response)
            if "Item" not in response:
                return None
            item = response['Item']
            return item

    def delete_item(self, pk_name, pk_value):
        try:
            client = self.getDynamoDbClient()
            table = client.Table(self.dynamo_table)
            response = table.delete_item(
                Key={
                    pk_name: pk_value
                }
            )
        except ClientError as e:
            if e.response['Error']['Code'] == "ConditionalCheckFailedException":
                print(e.response['Error']['Message'])
            else:
                raise
        else:
            print("DeleteItem succeeded:")
            res = json.dumps(response, indent=4)
            return res

    def insert_item(self, item):
        client = self.getDynamoDbClient()
        table = client.Table(self.dynamo_table)
        # with put_item function we insert data in Table
        response = table.put_item(
            Item=item
        )
        return response

    def update_item(self, pk_name, pk_value, updating_key, updating_value):
        client = self.getDynamoDbClient()
        table = client.Table(self.dynamo_table)
        response = table.update_item(
            Key={
                pk_name: pk_value
            },
            AttributeUpdates={
                updating_key: {
                    'Value': updating_value,
                    'Action': 'PUT'
                }
            },
            ReturnValues='UPDATED_NEW',
        )
