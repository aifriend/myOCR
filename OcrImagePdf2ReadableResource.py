import os
import sys
from flask import jsonify
from flask_restx import Resource, reqparse

from Doc2ReadOcrArgParser import Doc2ReadOcrArgParser
from commonsLib import loggerElk


class OcrImageDoc2ReadOcrResource(Resource):
    from api import api

    ELK_ENABLED = os.environ["ELK_ENABLED"]
    if isinstance(ELK_ENABLED, str):
        ELK_ENABLED = True if ELK_ENABLED == "True" else False

    print(f"ELK_ENABLED: {ELK_ENABLED}")
    logger = loggerElk(__name__)
    DEFAULT_TXT_LEN_FOR_SKIP = 100

    os.environ[
        'TIKA_SERVER_JAR'] = 'https://repo1.maven.org/maven2/org/apache/tika/tika-server/1.23/tika-server-1.23.jar'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from api import app
        try:
            from Doc2ReadOcrService import Doc2ReadOcrService, Doc2ReadOcrInput
            self.service = Doc2ReadOcrService(app=app)
        except Exception as ex:
            self.logger.Error("Not found Tesseract: TestService running...")
            from TestService import TestService
            self.service = TestService()

    ocrRequest = api.model('OcrRequest', Doc2ReadOcrArgParser.api_model(True))

    @api.doc(
        description='OCR text from an scanned PDF, and inserting in the same PDF',
        responses={
            200: 'OK',
            400: 'Invalid Argument',
            500: 'Internal Error'})
    @api.expect(ocrRequest)
    def post(self):
        key = ''
        try:
            # os.setpgrp()

            self.logger.Information('OcrImageDoc2ReadOcrResource::POST - init')
            parser = reqparse.RequestParser()
            args = Doc2ReadOcrArgParser.parse_args(parser, False)
            key = args['key'] if 'key' in args else ''
            return jsonify(self.service.post(args))

            # ret = {}
            # queue = multiprocessing.Queue()
            # queue.put(ret)

            # p1 = Process(target=self.service.postQueue, name='service_post', args=(queue, args))
            # p1.start()
            # p1.join(timeout=5)
            # p1.terminate()
            # os.killpg(0, 9)

            # return jsonify(queue.get())

        except Exception as e:
            self.logger.Error(f'ERROR - OcrImageDoc2ReadOcrResource::POST- {key} ' + str(e.args), sys.exc_info())
            return jsonify({
                'status': 'False',
                'statusCode': 500,
                'result': key,
                'resultText': '',
                'resultTextNonNative': '',
                'was_readOcr': 'False'
            })
