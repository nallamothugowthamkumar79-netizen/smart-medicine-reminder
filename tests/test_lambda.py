import sys
import os
import unittest
import json

lambda_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lambda'))
sys.path.insert(0, lambda_dir)

import lambda_function

class LambdaTestCase(unittest.TestCase):
    def test_lambda_dry_run_without_db(self):
        # When DATABASE_HOST is not set or empty, lambda returns graceful dry-run status
        res = lambda_function.lambda_handler({'source': 'aws.events'}, None)
        self.assertEqual(res['statusCode'], 200)
        body = json.loads(res['body'])
        self.assertIn('message', body)

if __name__ == '__main__':
    unittest.main()
