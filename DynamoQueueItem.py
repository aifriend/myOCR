class DynamoQueueItem(object):
    def __init__(self, message_id, request, status):
        self.message_id = message_id
        self.request = request
        self.status = status
