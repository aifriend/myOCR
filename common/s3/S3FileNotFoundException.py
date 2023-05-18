class S3FileNotFoundException(Exception):
    def __init__(self, key):
        # Call the base class constructor with the parameters it needs
        super(S3FileNotFoundException, self).__init__(f"The key '{key}' was not found")
