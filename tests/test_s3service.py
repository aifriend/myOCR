import json
import unittest

from common.s3.S3Service import S3Service


class FakeApp:
    def __init__(self, config):
        self.config = config


class TestS3Service(unittest.TestCase):
    EXISTING_FILE = 'existing_file.no_extension'
    EXISTING_FILE_CONTENT = b'Existing file content'
    UNEXISTING_FILE = 'unexisting_file.no_extension'

    def setUp(self):
        """Setup tests."""
        with open('config/config.json') as config_file:
            config = json.load(config_file)
        app = FakeApp(config)
        self.s3service = S3Service(
            app=app,
            bucket='rosetta.product.cs.proxy')
        self.s3service.upload_file(
            key=self.EXISTING_FILE, content=self.EXISTING_FILE_CONTENT)
        pass

    def teardown(self):
        """Tear down tests."""
        pass

    def test_check_file_exists(self):
        """Verify that an existing file returns True when check_file is executed"""
        result = self.s3service.check_file(key=self.EXISTING_FILE)
        self.assertTrue(result)

    def test_check_file_not_exists(self):
        """Verify that a non-existing file returns False when check_file is executed"""
        result = self.s3service.check_file(key=self.UNEXISTING_FILE)
        self.assertFalse(result)

    def test_get_file_exists(self):
        result = self.s3service.get_byte_file(key=self.EXISTING_FILE)
        self.assertEqual(result, self.EXISTING_FILE_CONTENT)
        pass

    def test_get_file_not_exists(self):
        with self.assertRaises(Exception):
            self.s3service.get_byte_file(key=self.UNEXISTING_FILE)

    TEST_FILE = 'test_file.test_extension'
    TEST_FILE_CONTENT = b'Test file content'

    def test_get_file_just_after_upload(self):
        self.s3service.upload_file(
            key=self.TEST_FILE, content=self.TEST_FILE_CONTENT)
        result = self.s3service.get_byte_file(key=self.TEST_FILE)
        self.assertEqual(result, self.TEST_FILE_CONTENT)


if __name__ == '__main__':
    unittest.main()
