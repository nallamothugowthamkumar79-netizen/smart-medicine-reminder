import sys
import os
import unittest
import json

# Add backend directory to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from app import create_app
from services.cloudwatch_service import CloudWatchService, cloudwatch_service
from config import Config

class CloudWatchIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(test_config={
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_ENGINE_OPTIONS': {},
            'CLOUDWATCH_ENABLED': True
        })
        self.client = self.app.test_client()

    def test_cloudwatch_service_singleton(self):
        """Verify CloudWatch service initializes as a singleton with correct defaults."""
        s1 = CloudWatchService()
        s2 = CloudWatchService()
        self.assertIs(s1, s2)
        self.assertEqual(s1.namespace, 'SmartMedicine/Application')
        self.assertEqual(s1.log_group, '/aws/smart-medicine/backend')

    def test_system_telemetry_collection(self):
        """Verify system CPU and memory metrics are properly captured."""
        metrics = cloudwatch_service.get_system_metrics()
        self.assertIn('cpu_percent', metrics)
        self.assertIn('memory_percent', metrics)
        self.assertIn('uptime_seconds', metrics)
        self.assertGreaterEqual(metrics['cpu_percent'], 0.0)
        self.assertGreaterEqual(metrics['memory_percent'], 0.0)
        self.assertGreaterEqual(metrics['uptime_seconds'], 0)

    def test_record_metrics_simulation(self):
        """Verify recording API calls, reminders, and failures works without errors."""
        # 1. API Call
        cloudwatch_service.record_api_call('/api/today', 'GET', 200, 15.5)
        
        # 2. API 500 Error
        cloudwatch_service.record_api_call('/api/error-test', 'POST', 500, 42.1)

        # 3. Reminder Metrics
        cloudwatch_service.record_reminder_dispatched('sms', 1)
        cloudwatch_service.record_reminder_failure('invalid_phone', 1)
        cloudwatch_service.record_missed_dose(1)

        # 4. Log Event
        cloudwatch_service.log_event('info', 'Test CloudWatch structured log', {'test_key': 'test_val'})

    def test_health_endpoint_cloudwatch_telemetry(self):
        """Verify /api/health returns CloudWatch telemetry and CPU/RAM data."""
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('cloudwatch_monitoring', data)
        self.assertIn('system_telemetry', data)
        self.assertEqual(data['cloudwatch_monitoring']['namespace'], 'SmartMedicine/Application')
        self.assertIn('cpu_utilization_percent', data['system_telemetry'])
        self.assertIn('memory_utilization_percent', data['system_telemetry'])

if __name__ == '__main__':
    unittest.main()
