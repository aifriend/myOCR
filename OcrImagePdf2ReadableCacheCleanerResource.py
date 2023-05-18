import os
import sys
from flask import jsonify
from flask_restx import Resource, fields, reqparse

from commonsLib import loggerElk


class OcrImageDoc2ReadOcrCacheCleanerResource(Resource):
    from api import api

    ELK_ENABLED = os.environ["ELK_ENABLED"]
    if isinstance(ELK_ENABLED, str):
        ELK_ENABLED = True if ELK_ENABLED == "True" else False

    print(f"ELK_ENABLED: {ELK_ENABLED}")
    logger = loggerElk(__name__)
    DEFAULT_TXT_LEN_FOR_SKIP = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from api import app
        from CacheCleanerService import CacheCleanerService
        self.service = CacheCleanerService(app=app)

    request_fields = {
        'key': fields.String(required=True, description='Key of the file'),
        'bucket': fields.String(required=True, description='The bucket of the file'),
    }

    @api.doc(
        description='Remove cached files for Doc2ReadOcr',
        responses={
            200: 'OK',
            400: 'Invalid Argument',
            500: 'Internal Error'})
    @api.expect(request_fields)
    def post(self):
        key = ''
        try:
            self.logger.Information('OcrImageDoc2ReadOcrCacheCleanerResource::POST - init')
            parser = reqparse.RequestParser()
            parser.add_argument('key', type=str, location='json')
            parser.add_argument('bucket', type=str, location='json')
            args = parser.parse_args()
            return jsonify(self.service.post(args))

        except Exception as e:
            self.logger.Error(f'ERROR - OcrImageDoc2ReadOcrCacheCleanerResource::POST- {key} ' + str(e.args),
                              sys.exc_info())
            return jsonify({
                'status': 'False',
                'statusCode': 500,
                'message': str(e)
            })
