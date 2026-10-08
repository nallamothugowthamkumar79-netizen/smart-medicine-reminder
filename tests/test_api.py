import sys
import os
import unittest
import json
from datetime import date

# Add backend directory to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

from app import create_app
from models import db, User, Medicine, MedicineSchedule, MedicineLog, Notification

class SmartMedicineTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(test_config={
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'SQLALCHEMY_ENGINE_OPTIONS': {}
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def register_and_get_token(self, email='patient@example.com', name='Patient User'):
        res = self.client.post('/api/register', json={
            'name': name,
            'email': email,
            'phone': '+1234567890',
            'password': 'password123',
            'confirm_password': 'password123',
            'notification_preference': 'both'
        })
        token = json.loads(res.data)['token']
        return token, {'Authorization': f'Bearer {token}'}

    def test_health_check(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'healthy')

    def test_user_registration_and_login(self):
        reg_payload = {
            'name': 'Senior Patient',
            'email': 'senior@example.com',
            'phone': '+1234567890',
            'password': 'password123',
            'confirm_password': 'password123',
            'notification_preference': 'both'
        }
        res = self.client.post('/api/register', json=reg_payload)
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertIn('token', data)
        self.assertEqual(data['user']['email'], 'senior@example.com')

        # Duplicate registration
        res_dup = self.client.post('/api/register', json=reg_payload)
        self.assertEqual(res_dup.status_code, 409)

        # Login
        login_res = self.client.post('/api/login', json={
            'email': 'senior@example.com',
            'password': 'password123'
        })
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        self.assertIn('token', login_data)

    def test_medicine_crud_and_doses(self):
        token, headers = self.register_and_get_token()

        # 1. Add Medicine
        med_payload = {
            'medicine_name': 'Paracetamol 500mg',
            'medicine_type': 'Tablet',
            'dosage': '1 Tablet',
            'quantity': 30,
            'instructions': 'After Food',
            'start_date': date.today().isoformat(),
            'schedules': [
                {'scheduled_time': '08:00', 'reminder_method': 'both'},
                {'scheduled_time': '20:00', 'reminder_method': 'both'}
            ]
        }
        res = self.client.post('/api/medicines', json=med_payload, headers=headers)
        self.assertEqual(res.status_code, 201)
        med_data = json.loads(res.data)['medicine']
        med_id = med_data['id']
        self.assertEqual(len(med_data['schedules']), 2)

        # 2. Get All Medicines
        get_res = self.client.get('/api/medicines', headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(len(json.loads(get_res.data)['medicines']), 1)

        # 3. Toggle Medicine Active
        toggle_res = self.client.patch(f'/api/medicines/{med_id}/toggle', headers=headers)
        self.assertEqual(toggle_res.status_code, 200)
        self.assertFalse(json.loads(toggle_res.data)['active'])

        # Reactivate
        self.client.patch(f'/api/medicines/{med_id}/toggle', headers=headers)

        # 4. Fetch today's doses
        today_res = self.client.get('/api/today', headers=headers)
        self.assertEqual(today_res.status_code, 200)
        today_data = json.loads(today_res.data)
        self.assertEqual(today_data['summary']['total'], 2)
        self.assertEqual(today_data['summary']['pending'], 2)

        # 5. Mark first dose as taken
        first_dose_id = today_data['doses'][0]['id']
        taken_res = self.client.put(f'/api/doses/{first_dose_id}/taken', headers=headers)
        self.assertEqual(taken_res.status_code, 200)

        # 6. Mark second dose as missed
        second_dose_id = today_data['doses'][1]['id']
        missed_res = self.client.put(f'/api/doses/{second_dose_id}/missed', headers=headers)
        self.assertEqual(missed_res.status_code, 200)

        # 7. Check history and adherence rate
        hist_res = self.client.get('/api/history?filter=today', headers=headers)
        self.assertEqual(hist_res.status_code, 200)
        hist_data = json.loads(hist_res.data)
        stats = hist_data['statistics']
        self.assertEqual(stats['total_doses'], 2)
        self.assertEqual(stats['taken_doses'], 1)
        self.assertEqual(stats['missed_doses'], 1)
        self.assertEqual(stats['adherence_percentage'], 50.0)

        # 8. Delete Medicine
        del_res = self.client.delete(f'/api/medicines/{med_id}', headers=headers)
        self.assertEqual(del_res.status_code, 200)

    def test_profile_and_notifications(self):
        token, headers = self.register_and_get_token()

        # 1. Get Profile
        prof_res = self.client.get('/api/profile', headers=headers)
        self.assertEqual(prof_res.status_code, 200)
        self.assertEqual(json.loads(prof_res.data)['user']['email'], 'patient@example.com')

        # 2. Update Profile
        update_res = self.client.put('/api/profile', json={
            'name': 'Updated Patient Name',
            'phone': '+9876543210',
            'notification_preference': 'sms'
        }, headers=headers)
        self.assertEqual(update_res.status_code, 200)
        self.assertEqual(json.loads(update_res.data)['user']['name'], 'Updated Patient Name')

        # 3. Trigger Test Reminder
        test_notif_res = self.client.post('/api/notifications/test', json={
            'message': 'Testing AWS SNS reminder delivery'
        }, headers=headers)
        self.assertEqual(test_notif_res.status_code, 200)

        # 4. Fetch Notifications Feed
        notifs_res = self.client.get('/api/notifications', headers=headers)
        self.assertEqual(notifs_res.status_code, 200)
        self.assertGreaterEqual(len(json.loads(notifs_res.data)['notifications']), 1)

if __name__ == '__main__':
    unittest.main()
