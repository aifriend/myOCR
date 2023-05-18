import aio_pika
import pika
import warnings
from aio_pika import ExchangeType

from api import app

# "error", "ignore", "always", "default", "module" or "once"
warnings.filterwarnings('ignore')


class RabbitMqService(object):
    TIMEOUT = 99999

    def __init__(self, queue):

        self.rabbit_mq_user = None
        self.rabbit_mq_pass = None
        self.queue_host = None
        self.queue_name = None
        self.__Session = None

        try:
            match = next(
                d for d in app.config['AWS']['QUEUES'] if d['ID'] == queue)
        except:
            match = next(
                d for d in app.config['AWS']['QUEUES'] if d['ID'] == 'DEFAULT')

        self.queue_host = match['HOST']
        self.rabbit_mq_user = match['USER']
        self.rabbit_mq_pass = match['PASSWORD']
        self.queue_name = match['QUEUE_NAME']

        if self.rabbit_mq_user is None or self.rabbit_mq_pass is None:
            raise Exception('No AWS credentials found')

    async def subscribe_to_queue(self, loop, callback=None):
        # async def subscribe_to_queue(self, loop):
        connection = await aio_pika.connect_robust(
            host=self.queue_host, port=5672, loop=loop,
            login=self.rabbit_mq_user, password=self.rabbit_mq_pass
        )
        # Creating channel
        channel = await connection.channel()

        await channel.set_qos(prefetch_count=1)
        # Declaring queue
        logs_exchange = await channel.declare_exchange(self.queue_name, ExchangeType.DIRECT, durable=True)
        queue = await channel.declare_queue(self.queue_name, auto_delete=False, durable=True)
        # Binding the queue to the exchange
        await queue.bind(logs_exchange)

        # Start listening the queue with name 'task_queue'
        await queue.consume(callback)
        connection.close()

    def get_connection(self):
        credentials = pika.PlainCredentials(
            self.rabbit_mq_user, self.rabbit_mq_pass)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.queue_host,
                credentials=credentials
            ))
        return connection

    def enqueue(self, message_body):
        connection = self.get_connection()
        channel = connection.channel()

        channel.queue_declare(queue=self.queue_name, durable=True)

        channel.basic_publish(
            exchange='',
            routing_key=self.queue_name,
            body=message_body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        connection.close()
        return
