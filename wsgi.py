import os

os.environ['ELK_URL'] = 'https://elk-sandbox-aofo6qam.eu-west-1.es.amazonaws.com'
os.environ['ELK_INDEX'] = ''
os.environ['APPLICATION'] = 'ML.DOCUMENT.CLASSIFIER'
os.environ['ENVIRONMENT'] = 'Development'
os.environ['LOG_LEVEL'] = 'DEBUG'
os.environ['LOG_FILE'] = 'logFile.log'
os.environ['LIBRARIES_LOG_LEVEL'] = 'ERROR'
os.environ['ELK_ENABLED'] = 'False'
os.environ['FILE_ENABLED'] = 'True'
os.environ['DATABASE_CONFIG'] = 'async'
os.environ['BUCKET_REQUEST_STORAGE'] = 'async.poll'
os.environ['LISTENED_QUEUE'] = 'async'
os.environ['ASYNC_POLL_URL'] = 'http://127.0.0.1:7013/api'

from api import app

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=7003)
