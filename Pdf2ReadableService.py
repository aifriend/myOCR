import base64
# Our deps
import ocrmypdf
import os
import sys
import tempfile
import traceback
from PyDOC2 import PdfFileWriter, PdfFileReader, errors
from tika import parser

from common.s3.S3FileNotFoundException import S3FileNotFoundException
from common.s3.S3Service import S3Service
from commonsLib import loggerElk


class Doc2ReadOcrInput:
    def __init__(self, source, data, bucket, lang, persistence, key,
                 txtLenForSkip, forcescan, forcenonative, disableocr, max_pages, kb_limit_size):
        pass
        self.source = source
        self.data = data
        self.bucket = bucket
        self.lang = lang
        self.persistence = persistence
        self.key = key
        self.txtLenForSkip = txtLenForSkip
        self.forcescan = forcescan
        self.forcenonative = forcenonative
        self.disableocr = disableocr
        self.max_pages = max_pages
        self.kb_limit_size = kb_limit_size


class Doc2ReadOcrService():
    ELK_ENABLED = os.environ["ELK_ENABLED"]
    if isinstance(ELK_ENABLED, str):
        ELK_ENABLED = True if ELK_ENABLED == "True" else False

    print(f"ELK_ENABLED: {ELK_ENABLED}")
    logger = loggerElk(__name__)
    DEFAULT_TXT_LEN_FOR_SKIP = 100

    os.environ[
        'TIKA_SERVER_JAR'] = 'https://repo1.maven.org/maven2/org/apache/tika/tika-server/1.23/tika-server-1.23.jar'

    def __init__(self, app, *args, **kwargs):
        self.app = app
        ocrmypdf.configure_logging(
            ocrmypdf.Verbosity.default, progress_bar_friendly=False, manage_root_logger=False)

    def post(self, input):
        original_key = None
        try:
            self.logger.Information('Doc2ReadOcrService::POST - init.')
            self.logger.Information(f'input: {input}')
            if 'forcescan' not in input:
                input['forcescan'] = 0
            if 'forcenonative' not in input:
                input['forcenonative'] = 0
            if 'lang' not in input:
                input['lang'] = 'spa'
            if 'disableocr' not in input:
                input['disableocr'] = 0
            if 'txtLenForSkip' not in input or input['txtLenForSkip'] is None:
                input['txtLenForSkip'] = self.DEFAULT_TXT_LEN_FOR_SKIP
            if 'max_pages' not in input:
                input['max_pages'] = None
            if 'kb_limit_size' not in input:
                input['kb_limit_size'] = 0
            else:
                if input['kb_limit_size'] is None:
                    input['kb_limit_size'] = 0
                else:
                    input['kb_limit_size'] = int(input['kb_limit_size']) * 1024

            # self.logger.Information(f"Doc2ReadOcrService::POST- {input['key']} - PROCESS START")
            # self.logger.LogInput(f"Doc2ReadOcrService::POST- {input['key']} - Input: ", input)
            source = input['source']
            data = input['data']
            forcescan = input['forcescan']
            forcenonative = 0
            if 'forcenonative' in input:
                if not input['forcenonative'] is None:
                    forcenonative = int(input['forcenonative'])
            key = input['key']
            bucket = input['bucket']
            kb_limit_size = input['kb_limit_size']
            txtLenForSkip = input['txtLenForSkip']
            max_pages = input['max_pages']
            persistence = input['persistence']
            disableocr = input['disableocr']

            skip_big_image = 10
            tesseract_timeout = 20
            max_file_size = 20.0 * 1048576

            self.logger.Information(f'key: {key}')
            if not self.isValidExtension(key):
                return {
                    'status': 'False',
                    'statusCode': 500,
                    'result': original_key,
                    'resultText': f'No valid file extension ({key}) provided',
                    'resultTextNonNative': '',
                    'was_readOcr': 'False'
                }

            lang = input['lang']
            if source == "BASE64":
                data_decoded = base64.b64decode(data)
            elif source == "FILE":
                with open(data, mode='rb') as file:
                    data_decoded = file.read()
            elif source == "S3":
                original_key = key
                self.logger.Debug(
                    f'OcrImageDoc2ReadOcrResource::POST- {key} param key: ' + key)
                s3_service = S3Service(
                    app=self.app, bucket=bucket, domain=None)
                if forcescan != 1:
                    cacheText = s3_service.checkCacheS3(key + '.txt')
                    cacheReadOcrText = s3_service.checkCacheS3Exists(
                        key + '.readOcr.pdf')
                    cacheTextNonNative = s3_service.checkCacheS3(
                        key + '.nonnative.txt')
                    if cacheText is not None:
                        result = {
                            'status': 'True',
                            'statusCode': 200,
                            'result': key,
                            'txt_key': key + '.txt',
                            'resultText': cacheText,
                            'resultTextNonNative': cacheTextNonNative,
                            'was_readOcr': 'False'
                        }
                        if cacheReadOcrText:
                            result['readOcr_key'] = key + '.readOcr.pdf'
                        if cacheTextNonNative:
                            result['readOcr_nonnative_key'] = key + \
                                                               '.nonnative.txt'
                        return result

                data_decoded = s3_service.get_byte_file(key)
            else:
                raise Exception('No valid source ({}) provided'.format(source))

            if sys.getsizeof(data_decoded) > max_file_size:
                # File's size limit exceeded
                self.logger.Error(f'413 for key: {key}')
                return '', 413

            if kb_limit_size > 0:
                kb_data_size = (len(data_decoded) * 3) / 4
                self.logger.Debug(f'kb_data_size: {kb_data_size}')
                if kb_data_size > kb_limit_size:
                    # File's limit size exceeded
                    self.logger.Error(f'413 for key: {key}')
                    return '', 413

            with tempfile.NamedTemporaryFile() as fp:
                fp.write(data_decoded)
                fp.flush()
                out_file_name = fp.name + '.out'

                self.logger.Information(
                    f"OcrImageDoc2ReadOcrResource::POST- {key} documentUnscannedText start")
                text = self.documentUnscannedTextByPages(fp)
                self.logger.Information(
                    f"OcrImageDoc2ReadOcrResource::POST- {key} documentUnscannedText end")

                text_clean = self.cleanAll(text)
                if len(text_clean) < txtLenForSkip:
                    self.logger.Information(
                        f"OcrImageDoc2ReadOcrResource::POST- {key} text size lower than txtLenForSkip " + str(
                            len(text_clean)))

                if (len(text_clean) < txtLenForSkip) or forcenonative == 1:
                    self.logger.Information(
                        f"OcrImageDoc2ReadOcrResource::POST- {key} start scan")
                    self.logger.Information(
                        f"OcrImageDoc2ReadOcrResource::POST- {key} documentIsScanned TRUE")
                    ocr_options = dict(
                        optimize=0, output_type='pdf', fast_web_view=0, skip_big=skip_big_image,
                        pages=max_pages, jobs=1, clean=True, deskew=True, language=lang, sidecar=True,
                        force_ocr=True, tesseract_timeout=tesseract_timeout
                    )
                    try:
                        ocrmypdf.ocr(fp.name, out_file_name, **ocr_options)
                    except ocrmypdf.exceptions.UnsupportedImageFormatError:
                        self.logger.Error(
                            f"OcrImageDoc2ReadOcrResource::POST- {key} 406 (UnsupportedImageFormatError) for key: {key}")
                        return '', 406
                    except ocrmypdf.exceptions.EncryptedPdfError:
                        # DECRYPT PDF
                        self.logger.Information(
                            f"OcrImageDoc2ReadOcrResource::POST- {key} Decrypting PDF...")
                        command = f"qpdf --password='' --decrypt {fp.name} {fp.name + '.decrypted.pdf'}"
                        os.system(command)
                        ocrmypdf.ocr(fp.name + '.decrypted.pdf',
                                     out_file_name, **ocr_options)

                    self.logger.Debug(
                        f"OcrImageDoc2ReadOcrResource::POST- {key} OCR Done")
                    self.doPersistence(persistence, key +
                                       ".readOcr.pdf", out_file_name, bucket)

                    with open(out_file_name, 'r') as second_pass_file:
                        textSecondPass = self.documentUnscannedTextByPages(
                            second_pass_file)
                        textSecondPass = base64.b64encode(
                            textSecondPass.encode('utf-8')).decode('utf-8')
                        self.doPersistenceFromData(
                            persistence, key + ".txt", bucket, textSecondPass)
                        # self.doPersistenceFromData(
                        #     persistence, key + ".readOcr.txt", bucket, textSecondPass)

                    resultTextNonNative = ''
                    # if forcenonative==1:
                    #    with open(out_file_name, 'r') as native_file:
                    #        resultTextNonNative = native_file.read()
                    #        native_file.close()

                    # os.remove(out_file_name)
                    self.logger.Information(
                        f'OcrImageDoc2ReadOcrResource::POST- {key} - PROCESS END')
                    return {
                        'status': 'True',
                        'statusCode': 200,
                        'result': key,
                        'resultText': textSecondPass,
                        'resultTextNonNative': resultTextNonNative,
                        'readOcr_key': key + '.readOcr.pdf',
                        'txt_key': key + '.txt',
                        'was_readOcr': 'False'
                    }
                else:
                    self.logger.Information(
                        f"OcrImageDoc2ReadOcrResource::POST- {key} The document source is a PDF native document.")

                    textNonNative = ''
                    if disableocr != 1 and disableocr != '1':
                        ocr_options = dict(
                            optimize=0, output_type='pdf', fast_web_view=0, skip_big=skip_big_image,
                            jobs=1, pages='1,2,3,4,5,6', language=lang, force_ocr=True,
                            tesseract_timeout=tesseract_timeout
                        )
                        try:
                            self.logger.Information(
                                f"OcrImageDoc2ReadOcrResource::POST- {key} Trying ocr tesseract second pass.")
                            ocrmypdf.ocr(fp.name, out_file_name, **ocr_options)
                            self.logger.Debug(
                                f"OcrImageDoc2ReadOcrResource::POST- out_file_name {out_file_name}")
                            self.logger.Debug(
                                f"OcrImageDoc2ReadOcrResource::POST- {key} OCR Done")
                        except ocrmypdf.exceptions.UnsupportedImageFormatError:
                            self.logger.Error(
                                f"OcrImageDoc2ReadOcrResource::POST- {key} 406 (UnsupportedImageFormatError) for key: {key}")
                            return '', 406
                        except ocrmypdf.exceptions.EncryptedPdfError:
                            # DECRYPT PDF
                            self.logger.Information(
                                f"OcrImageDoc2ReadOcrResource::POST- {key} Decrypting PDF...")
                            command = f"qpdf --password='' --decrypt {fp.name} {fp.name + '.decrypted.pdf'}"
                            os.system(command)
                            ocrmypdf.ocr(fp.name + '.decrypted.pdf',
                                         out_file_name, **ocr_options)
                            self.logger.Debug(
                                f"OcrImageDoc2ReadOcrResource::POST- {key} OCR Done")

                        with open(out_file_name, 'r') as second_pass_file:
                            textNonNative = self.documentUnscannedTextByPages(
                                second_pass_file)
                            textNonNative = base64.b64encode(
                                textNonNative.encode('utf-8')).decode('utf-8')
                        os.remove(out_file_name)

                    text = self.sanitize_utf8(text)
                    # text = base64.b64encode (text.encode("utf-8")).decode('utf-8')
                    self.doPersistenceFromData(
                        persistence, key + ".txt", bucket, text)
                    if disableocr != 1 and disableocr != '1':
                        self.doPersistenceFromData(
                            persistence, key + ".nonnative.txt", bucket, textNonNative)
                    self.logger.Information(
                        f'OcrImageDoc2ReadOcrResource::POST- {key} - PROCESS END')
                    return {
                        'status': 'True',
                        'statusCode': 200,
                        'result': key,
                        'resultText': text,
                        'resultTextNonNative': textNonNative,
                        'readOcr_key': '',
                        'txt_key': key + '.txt',
                        'readOcr_nonnative_key': key + '.nonnative.txt',
                        'was_readOcr': 'True'
                    }
        except S3FileNotFoundException as e:
            response = 'MlDocumentClassifierDataPreparationVectorizerResource::POST ' + str(e)
            self.logger.Error(
                f"OcrImageDoc2ReadOcrResource::POST- " + str(response), sys.exc_info())
            final_response = response
            return final_response, 404
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            self.logger.Error(
                f'ERROR - OcrImageDoc2ReadOcrResource::POST- ' + str(e.args), sys.exc_info())
            # return {'message': 'Something went wrong: ' + str(e)}, 500
            return {
                'status': 'False',
                'statusCode': 500,
                'result': original_key,
                'resultText': '',
                'resultTextNonNative': '',
                'was_readOcr': 'False'
            }
        # non_bmp_map = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)

    non_bmp_map = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)

    def sanitize_utf8(self, text):
        # strip unwanted unicode images
        text = text.translate(self.non_bmp_map)

        # convert to latin-1 to remove all stupid unicode characters
        # you may want to adapt this to your personal needs
        #
        # for some strange reason I have to first transform the string to bytes with latin-1
        # encoding and then do the reverse transform from bytes to string with latin-1 encoding as
        # well... maybe has to be revised later
        bText = text.encode('latin-1', 'ignore')
        decode = bText.decode('latin-1', 'ignore')
        return base64.b64encode(bytes(decode, 'utf-8')).decode('latin-1')

    def isValidExtension(self, key):
        keyCase = key.lower()
        if keyCase.find('.') == -1 or keyCase.endswith('pdf'):
            return True
        return False

    def cleanAll(self, data):
        s = data.replace('\n', '')
        s = s.replace('\f', '')
        s = s.replace('\t', '')
        s = s.replace('\\n', '')
        s = s.replace('\\f', '')
        s = s.replace('\\t', '')
        return s

    def documentUnscannedTextByPages(self, fp):
        try:
            res = self.documentUnscannedTextByPagesInternal(fp)
        except errors.PdfReadError:
            self.logger.Information(
                f"OcrImageDoc2ReadOcrResource::POST- Decrypting PDF...")
            command = f"qpdf --password='' --decrypt {fp.name} {fp.name + '.decrypted.pdf'}"
            os.system(command)
            with open(fp.name + '.decrypted.pdf', 'r') as decrypted:
                res = self.documentUnscannedTextByPagesInternal(decrypted)

        return res

    def documentUnscannedTextByPagesInternal(self, fp):
        try:
            inputpdf = PdfFileReader(open(fp.name, "rb"))
        except:
            return ''

        total_all_text = ''
        for i in range(inputpdf.numPages):
            self.logger.Information(
                f"OcrImageDoc2ReadOcrResource::POST- documentUnscannedTextByPagesInternal page: " + str(i))
            output = PdfFileWriter()
            output.addPage(inputpdf.getPage(i))
            with tempfile.NamedTemporaryFile(mode="wb") as filetemp:
                outputStream = open(filetemp.name, "wb")
                output.write(outputStream)
                outputStream.close()
                try:
                    file_data = parser.from_file(filetemp.name)
                    # Get files text content
                    all_text = file_data['content']

                    if all_text is None:
                        all_text = '\r\n'

                    total_all_text = total_all_text + '[[[' + str(i + 1) + ']]]' + all_text

                except Exception as e:
                    self.logger.Error(
                        'ERROR - OcrImageDoc2ReadOcrResource::POST' + str(e.args), sys.exc_info())
                    return ''
        return total_all_text

    def doPersistenceFromData(self, persistence, key, bucket, data2Write):
        self.logger.Information(
            "OcrImageDoc2ReadOcrResource::POST - doPersistenceFromData: " + key)
        if persistence == 'S3':
            s3_service = S3Service(app=self.app, bucket=bucket, domain=None)
            response = s3_service.upload_file(str(key), data2Write)
            self.logger.Debug(
                f"OcrImageDoc2ReadOcrResource::POST- doPersistenceFromData response {str(response)}")
            return key
        elif persistence == 'BASE64':
            return base64.b64encode(data2Write).decode('utf-8')
        pass

    def doPersistence(self, persistence, key, file, bucket):
        with open(file, mode='rb') as file:
            data2Write = file.read()
            return self.doPersistenceFromData(persistence, key, bucket, data2Write)
