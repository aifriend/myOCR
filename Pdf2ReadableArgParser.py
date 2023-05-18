from flask_restx import fields


class Doc2ReadOcrArgParser:
    def init(self):
        pass

    @staticmethod
    def parse_args(parser, is_enqueuing):
        parser.add_argument('source', type=str, location='json')
        parser.add_argument('data', type=str, location='json')
        parser.add_argument('bucket', type=str, location='json')
        parser.add_argument('lang', type=str, location='json')
        parser.add_argument('persistence', type=str, location='json')
        parser.add_argument('key', type=str, location='json')
        parser.add_argument('txtLenForSkip', type=int, location='json')
        parser.add_argument('forcescan', type=int, location='json')
        parser.add_argument('forcenonative', type=int, location='json')
        parser.add_argument('disableocr', type=int, location='json')
        parser.add_argument('max_pages', type=int, location='json')
        parser.add_argument('kb_limit_size', type=int, location='json')
        if is_enqueuing:
            parser.add_argument('queue', type=str, location='json')
            parser.add_argument('endpoint_push', type=str, location='json')
        return parser.parse_args()

    @staticmethod
    def api_model(is_enqueuing):
        model = {
            'source': fields.String(required=True,
                                    description='The source channel to obtain the image (in PNG). [BASE64, FILE, S3]'),
            'bucket': fields.String(required=True, description='The bucket of the file'),
            'data': fields.String(required=True, description='Content of the file in [Base64 | URL | S3 URL]'),
            'lang': fields.String(required=True, description='OCR language (spa/eng)'),
            'persistence': fields.String(required=True, description='Type of file persistence'),
            'key': fields.String(required=True, description='Key of the file'),
            'forcescan': fields.String(required=True, description='Force Scan file and dismiss previous txt files'),
            'forcenonative': fields.String(required=True, description='Force No Native Scan file'),
            'disableocr': fields.String(required=True, description='Disable the OCR for native documents'),
            'txtLenForSkip': fields.String(required=True, description='Max len to discard'),
            'kb_limit_size': fields.Integer(required=False, description='Max file size to process it'),
        }
        if is_enqueuing:
            model["queue"] = fields.String(required=True, description='Queue where is gonna append')
            model["endpoint_push"] = fields.String(required=False, description='Endpoint to send result')

        return model
