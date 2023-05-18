import certifi
import logging
import os
from datetime import datetime
from elasticsearch import Elasticsearch


class LogItem:

    def __init__(self, Message, Level, ObjectType, ObjectData):
        self.Message = Message
        self.Level = Level
        self.ObjectType = ObjectType
        self.ObjectData = ObjectData


class NoTrashFilter(logging.Filter):
    def __init__(self, loggingLevel):
        super().__init__()
        self.noTrashArray = ["_log", "LogInput", "LogResult", "Information", "Error", "Debug", "log_exception"]
        self.loggingLevel = loggingLevel

    def filter(self, record):
        return record.funcName in self.noTrashArray or record.levelno >= self.loggingLevel


class loggerFileAux:
    def __init__(self, debug_mode):
        self.DEBUG_MODE = debug_mode
        self.LOG_LIST = []

    def Log(self, level, message):
        if self.DEBUG_MODE:
            self.LOG_LIST.append({"level": level, "message": message})


class loggerElk:
    def __init__(self, owner__name__):

        switcher = {
            "CRITICAL": 50,
            "ERROR": 40,
            "WARNING": 30,
            "INFO": 20,
            "DEBUG": 10
        }
        self.serviceName = str(owner__name__)

        enableKibana = self.__get_boolean_os_var("ELK_ENABLED")
        enableFile = self.__get_boolean_os_var("FILE_ENABLED")

        try:
            self.lib_lob_level = str(os.environ["LIBRARIES_LOG_LEVEL"])
        except:
            print('ERROR GETTING THE ENV_VAR LIBRARIES_LOG_LEVEL... \'ERROR\' BY DEFAULT')
            self.lib_lob_level = "ERROR"
        try:
            logLevel = os.environ["LOG_LEVEL"]
        except:
            print('ERROR GETTING THE ENV_VAR LOG_LEVEL... \'DEBUG\' BY DEFAULT')
            logLevel = "DEBUG"

        logging.basicConfig(filemode='a')
        logging.getLogger().setLevel(logging.FATAL)
        self.logger = logging.getLogger()
        self.logger.handlers = []
        self.logger.setLevel(logLevel)
        self.logger.addFilter(NoTrashFilter(switcher.get(self.lib_lob_level, "")))
        # create formatter and add it to the handlers
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s (%(process)s %(threadName)s) - %(funcName)s -> %(lineno)s - %(message)s')

        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.addFilter(NoTrashFilter(switcher.get(self.lib_lob_level, "")))
        ch.setLevel(logLevel)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        # create file handler which logs even debug messages
        if enableFile:
            try:
                logFile = os.environ["LOG_FILE"]
                fh = logging.FileHandler(logFile)
                fh.addFilter(NoTrashFilter(switcher.get(self.lib_lob_level, "")))
                fh.setLevel(logLevel)
                fh.setFormatter(formatter)
                self.logger.addHandler(fh)
            except Exception as e:
                self.logger.warning("LOG_FILE env-var not provided or can't write the file::{}.".format(e))
                print("WARNING!: LOG_FILE env-var not provided or can't write the file::{}.".format(e))
        if enableKibana:
            self.elkEnabled = True
            try:

                self.elkIndex = os.environ["ELK_INDEX"]
                self.application = os.environ["APPLICATION"]
                self.environment = os.environ["ENVIRONMENT"]
                url = str(os.environ["ELK_URL"])
                try:
                    self.es = Elasticsearch(str(url), use_ssl=True, ca_certs=certifi.where())
                except Exception as e:
                    self.elkEnabled = False
                    self.logger.error('ERROR CREATING CONNECTION TO ELK - ' + str(e))
                    print('ERROR CREATING CONNECTION TO ELK - ' + str(e))
            except:
                self.elkEnabled = False
                self.logger.error('ERROR GETTING THE ENV_VARS. WITH ENABLE_ELK YOU NEED ELK_INDEX, '
                                  'APPLICATION, ENVIRONMENT AND ELK_URL')
                print('ERROR GETTING THE ENV_VARS. WITH ENABLE_ELK YOU NEED ELK_INDEX, '
                      'APPLICATION, ENVIRONMENT AND ELK_URL')

        else:
            self.elkEnabled = False

    def __sendItemToElk__(self, logItem: LogItem, extraAttrs=None):
        if self.elkEnabled:
            try:
                strDate = datetime.now().strftime("%Y.%m.%d")
                jsonBody = {
                    "file": self.serviceName,
                    "message": logItem.Message,
                    "@timestamp": datetime.now().isoformat(),
                    "level": logItem.Level,
                    "objectType": logItem.ObjectType,
                    "objectData": str(logItem.ObjectData),
                    "application": str(self.application),
                    "environment": str(self.environment)
                }
                if extraAttrs is not None:
                    for attribute, value in extraAttrs.items():
                        jsonBody[attribute] = value

                self.es.index(index=self.elkIndex + str(strDate), doc_type="TRACE", body=jsonBody)
            except:
                pass

    def LogResult(self, message, ObjectData, extraAttrs=None):
        li = LogItem(message, 'Information', "result", ObjectData)
        self.logger.info(message + " - result - " + str(ObjectData))
        self.__sendItemToElk__(li, extraAttrs)

    def LogInput(self, message, ObjectData, extraAttrs=None):
        li = LogItem(message, 'Information', "input", ObjectData)
        self.logger.info(message + " - input - " + str(ObjectData))
        self.__sendItemToElk__(li, extraAttrs)

    def Information(self, message, extraAttrs=None):
        li = LogItem(message, 'Information', "trace", "")
        self.logger.info(message)
        self.__sendItemToElk__(li, extraAttrs)

    def Debug(self, message, extraAttrs=None):
        li = LogItem(message, 'Debug', "trace", "")
        self.logger.debug(message)
        self.__sendItemToElk__(li, extraAttrs)

    def Error(self, message, sysExecInfo=None):
        error = list()
        if sysExecInfo is not None:
            for e in sysExecInfo:
                if hasattr(e, 'tb_frame'):
                    error.append(str(e.tb_frame))
                else:
                    error.append(str(e))
        li = LogItem(message, 'Error', "trace", error)
        error.insert(0, message)

        self.logger.exception(str(error))
        self.__sendItemToElk__(li)

    def __get_boolean_os_var(self, os_var):
        if not os_var in os.environ:
            return False
        nat_var = os.environ[os_var]
        if isinstance(nat_var, str):
            return True if nat_var == "True" else False
        else:
            return nat_var
