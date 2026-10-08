import logging
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config
from services.cloudwatch_service import cloudwatch_service

logger = logging.getLogger(__name__)

class SNSService:
    def __init__(self):
        self.region = Config.AWS_REGION
        self.topic_arn = Config.SNS_TOPIC_ARN
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            kwargs = {'region_name': self.region}
            if Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
                kwargs['aws_access_key_id'] = Config.AWS_ACCESS_KEY_ID
                kwargs['aws_secret_access_key'] = Config.AWS_SECRET_ACCESS_KEY
                if Config.AWS_SESSION_TOKEN:
                    kwargs['aws_session_token'] = Config.AWS_SESSION_TOKEN

            self.client = boto3.client('sns', **kwargs)
            logger.info("SNS Service initialized successfully.")
        except Exception as e:
            logger.warning(f"Failed to initialize AWS SNS client: {e}. Running in simulation/fallback mode.")
            self.client = None

    def send_sms(self, phone_number, message):
        """
        Sends an SMS notification via Amazon SNS.
        """
        if not phone_number:
            return {'success': False, 'error': 'No phone number provided', 'status': 'failed'}

        # Format international phone number if needed
        clean_phone = phone_number.strip().replace(' ', '').replace('-', '')
        if not clean_phone.startswith('+'):
            clean_phone = '+' + clean_phone  # e.g., +1... or +91...

        if self.client:
            try:
                response = self.client.publish(
                    PhoneNumber=clean_phone,
                    Message=message,
                    MessageAttributes={
                        'AWS.SNS.SMS.SenderID': {
                            'DataType': 'String',
                            'StringValue': 'SmartMed'
                        },
                        'AWS.SNS.SMS.SMSType': {
                            'DataType': 'String',
                            'StringValue': 'Transactional'
                        }
                    }
                )
                logger.info(f"SMS successfully sent to {clean_phone}. MessageId: {response.get('MessageId')}")
                cloudwatch_service.record_reminder_dispatched('sms', 1)
                return {
                    'success': True,
                    'message_id': response.get('MessageId'),
                    'status': 'delivered'
                }
            except (ClientError, NoCredentialsError) as e:
                logger.error(f"AWS SNS SMS error: {e}")
                cloudwatch_service.record_reminder_failure('sms_error', 1)
                cloudwatch_service.log_event('error', f"AWS SNS SMS delivery failed to {clean_phone}: {str(e)}")
                return {'success': False, 'error': str(e), 'status': 'failed'}
        else:
            # Simulation mode when AWS credentials are not yet configured
            logger.info(f"[SIMULATED SNS SMS] To: {clean_phone} | Message: {message}")
            cloudwatch_service.record_reminder_dispatched('sms_simulated', 1)
            return {
                'success': True,
                'message_id': f'sim-sms-{hash(message + clean_phone) & 0xffffffff}',
                'status': 'simulated (AWS credentials not set)'
            }

    def send_email(self, email, subject, message):
        """
        Sends an Email notification via Amazon SNS Topic or Direct formatting.
        """
        if not email:
            return {'success': False, 'error': 'No email address provided', 'status': 'failed'}

        if self.client and self.topic_arn:
            try:
                response = self.client.publish(
                    TopicArn=self.topic_arn,
                    Subject=subject,
                    Message=message,
                    MessageAttributes={
                        'email': {
                            'DataType': 'String',
                            'StringValue': email
                        }
                    }
                )
                logger.info(f"Email sent via SNS Topic to {email}. MessageId: {response.get('MessageId')}")
                cloudwatch_service.record_reminder_dispatched('email', 1)
                return {
                    'success': True,
                    'message_id': response.get('MessageId'),
                    'status': 'delivered'
                }
            except (ClientError, NoCredentialsError) as e:
                logger.error(f"AWS SNS Email error: {e}")
                cloudwatch_service.record_reminder_failure('email_error', 1)
                cloudwatch_service.log_event('error', f"AWS SNS Email delivery failed to {email}: {str(e)}")
                return {'success': False, 'error': str(e), 'status': 'failed'}
        else:
            logger.info(f"[SIMULATED SNS EMAIL] To: {email} | Subject: {subject} | Body:\n{message}")
            cloudwatch_service.record_reminder_dispatched('email_simulated', 1)
            return {
                'success': True,
                'message_id': f'sim-email-{hash(subject + email) & 0xffffffff}',
                'status': 'simulated (AWS credentials not set)'
            }

    def send_reminder(self, user, medicine, scheduled_time, method_override=None):
        """
        Builds the standard medicine reminder message and delivers via the user's preferred channel.
        """
        method = method_override or user.notification_preference or 'both'
        time_display = scheduled_time
        
        # Format HH:MM to 12-hour AM/PM
        try:
            parts = scheduled_time.split(':')
            h, m = int(parts[0]), int(parts[1])
            period = 'AM' if h < 12 else 'PM'
            h12 = h % 12
            if h12 == 0:
                h12 = 12
            time_display = f"{h12:02d}:{m:02d} {period}"
        except Exception:
            pass

        instructions_text = f" ({medicine.instructions})" if medicine.instructions else ""
        message = (
            f"Medicine Reminder: Hello {user.name}, it is time to take your {medicine.medicine_name} "
            f"— {medicine.dosage}{instructions_text}. Scheduled time: {time_display}. "
            f"Please remember to mark it as taken in your Smart Medicine app!"
        )
        subject = f"Smart Medicine Reminder: {medicine.medicine_name} at {time_display}"

        results = {}
        if method in ['sms', 'both'] and user.phone:
            results['sms'] = self.send_sms(user.phone, message)
        if method in ['email', 'both'] and user.email:
            results['email'] = self.send_email(user.email, subject, message)

        overall_status = 'sent'
        if all(r.get('status') == 'failed' for r in results.values()) and results:
            overall_status = 'failed'
        elif any('simulated' in str(r.get('status', '')) for r in results.values()):
            overall_status = 'simulated'

        return {
            'message': message,
            'subject': subject,
            'results': results,
            'status': overall_status
        }

sns_service = SNSService()
