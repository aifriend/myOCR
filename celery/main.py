import boto3
import json

from celery import group
from doc2readOcr_processor import execTask


def get_keys(bucket, prefix='', max_keys=1000):
    print("Getting keys from s3")
    try:
        client = boto3.client(
            's3',
            aws_access_key_id='',
            aws_secret_access_key='')

        paginator = client.get_paginator("list_objects")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
        _keys = []
        for page in page_iterator:
            if "Contents" in page:
                for _key in page["Contents"]:
                    keyString = _key
                    _keys.append(keyString)

        return _keys if _keys else []

    except Exception as e:
        print(str(e.args))


def get_key_names_array(keys_array):
    print("Getting key names")
    return [k["Key"] for k in keys_array]


MAX_KEY_LIST = -1
DO_PDF_OCR = False

folder_list = ['']

key_list = []
bucket = ''
bucket_facade = ''
for folder in folder_list:
    keys = get_keys(bucket, folder)
    keys2 = get_key_names_array(keys)
    count = 1
    for key in keys2:
        if MAX_KEY_LIST != -1 and count > MAX_KEY_LIST:
            break
        # if key.lower().endswith('.pdf') and key.find('readOcr') == -1:
        if key.lower().endswith('.pdf'):
            key_list.append(key)
            count = count + 1

print('Number of documents: ' + str(len(key_list)))

document_result = []
for dkey in key_list:
    print('dkey: ' + str(dkey))
    document_result.append(execTask.s(bucket, bucket_facade, dkey))

job_group = group(document_result)
result = job_group.apply_async()
result.join()

# DUMP result into files
for (i, result_element) in enumerate(result):
    fileName = ""
    if result_element.get('idRequest') is not None:
        fileName = str(result_element.get().get('idRequest')).split('/')[1].split('.')[0] + '_processed.json'
    else:
        fileName = str(i) + '_NameNotFound_processed.json'
    json.dump(result_element.get(), open('./json_folder/' + fileName, mode='w+'))
