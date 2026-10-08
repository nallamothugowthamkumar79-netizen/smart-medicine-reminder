import os
import json
import logging
import datetime
import boto3
import pymysql

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment configuration
DB_HOST = os.environ.get('DATABASE_HOST')
DB_USER = os.environ.get('DATABASE_USER', 'admin')
DB_PASSWORD = os.environ.get('DATABASE_PASSWORD', '')
DB_NAME = os.environ.get('DATABASE_NAME', 'smart_medicine_db')
DB_PORT = int(os.environ.get('DATABASE_PORT', 3306))
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
GRACE_PERIOD_MINUTES = int(os.environ.get('GRACE_PERIOD_MINUTES', 60))
TIMEZONE_OFFSET_HOURS = float(os.environ.get('TIMEZONE_OFFSET_HOURS', 5.5))  # Default IST

sns_client = boto3.client('sns', region_name=AWS_REGION)
cw_client = boto3.client('cloudwatch', region_name=AWS_REGION)

def get_db_connection():
    if not DB_HOST:
        logger.warning("DATABASE_HOST not configured in Lambda environment variables.")
        return None
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )

def lambda_handler(event, context):
    """
    AWS Lambda Handler executed on Amazon CloudWatch Scheduled Rule (every 1-5 minutes).
    Checks scheduled doses, triggers SNS SMS/Email notifications, and records logs.
    """
    logger.info("Lambda Smart Medicine Reminder check triggered.")
    
    # Calculate local time
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    local_now = utc_now + datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS)
    today_date = local_now.date()
    current_time_str = local_now.strftime('%H:%M')
    
    logger.info(f"Local time: {local_now.isoformat()} | Checking scheduled time: {current_time_str}")

    conn = get_db_connection()
    if not conn:
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'DATABASE_HOST not set, running in dry-run mode.'})
        }

    notifications_sent = 0
    missed_marked = 0

    try:
        with conn.cursor() as cursor:
            # 1. Query medicines due right now
            due_query = """
                SELECT 
                    ms.id AS schedule_id, ms.scheduled_time, ms.reminder_method,
                    m.id AS medicine_id, m.medicine_name, m.medicine_type, m.dosage, m.instructions,
                    u.id AS user_id, u.name AS user_name, u.email, u.phone, u.notification_preference
                FROM medicine_schedules ms
                JOIN medicines m ON ms.medicine_id = m.id
                JOIN users u ON m.user_id = u.id
                WHERE m.active = 1
                  AND m.start_date <= %s
                  AND (m.end_date IS NULL OR m.end_date >= %s)
                  AND ms.scheduled_time = %s
            """
            cursor.execute(due_query, (today_date, today_date, current_time_str))
            due_doses = cursor.fetchall()
            logger.info(f"Found {len(due_doses)} doses due for {current_time_str}")

            for dose in due_doses:
                med_id = dose['medicine_id']
                user_id = dose['user_id']
                user_name = dose['user_name']
                med_name = dose['medicine_name']
                dosage = dose['dosage']
                instructions = dose['instructions'] or 'as prescribed'
                user_phone = dose['phone']
                user_email = dose['email']
                pref = dose['reminder_method'] or dose['notification_preference'] or 'both'

                # Ensure log entry exists
                check_log_query = """
                    SELECT id, status FROM medicine_logs 
                    WHERE medicine_id = %s AND user_id = %s AND scheduled_date = %s AND scheduled_time = %s
                """
                cursor.execute(check_log_query, (med_id, user_id, today_date, current_time_str))
                existing_log = cursor.fetchone()

                if not existing_log:
                    insert_log_query = """
                        INSERT INTO medicine_logs (medicine_id, user_id, scheduled_date, scheduled_time, status, created_at)
                        VALUES (%s, %s, %s, %s, 'pending', NOW())
                    """
                    cursor.execute(insert_log_query, (med_id, user_id, today_date, current_time_str))
                    conn.commit()

                # Dispatch reminder if pending
                if not existing_log or existing_log['status'] == 'pending':
                    instructions_text = f" ({instructions})" if instructions else ""
                    msg_body = (
                        f"Medicine Reminder: Hello {user_name}, it is time to take {med_name} — "
                        f"{dosage}{instructions_text}. Scheduled time: {current_time_str}. "
                        f"Open your app to mark it as taken!"
                    )

                    # Send SNS SMS
                    if pref in ['sms', 'both'] and user_phone:
                        try:
                            clean_phone = user_phone.strip().replace(' ', '').replace('-', '')
                            if not clean_phone.startswith('+'):
                                clean_phone = '+' + clean_phone
                            sns_client.publish(
                                PhoneNumber=clean_phone,
                                Message=msg_body
                            )
                            logger.info(f"Sent SMS reminder to {clean_phone}")
                        except Exception as e:
                            logger.error(f"SNS SMS error: {e}")

                    # Send SNS Email
                    if pref in ['email', 'both'] and (SNS_TOPIC_ARN or user_email):
                        try:
                            if SNS_TOPIC_ARN:
                                sns_client.publish(
                                    TopicArn=SNS_TOPIC_ARN,
                                    Subject=f"Medicine Reminder: {med_name}",
                                    Message=msg_body
                                )
                                logger.info(f"Sent SNS topic email for {user_email}")
                        except Exception as e:
                            logger.error(f"SNS Topic error: {e}")

                    # Insert into notifications
                    insert_notif_query = """
                        INSERT INTO notifications (user_id, medicine_id, message, notification_type, sent_at, status)
                        VALUES (%s, %s, %s, 'reminder', NOW(), 'sent')
                    """
                    cursor.execute(insert_notif_query, (user_id, med_id, msg_body))
                    conn.commit()
                    notifications_sent += 1

            # 2. Check for overdue doses to mark as 'missed'
            grace_threshold = local_now - datetime.timedelta(minutes=GRACE_PERIOD_MINUTES)
            overdue_time_str = grace_threshold.strftime('%H:%M')

            overdue_query = """
                SELECT ml.id, ml.user_id, ml.medicine_id, ml.scheduled_time, m.medicine_name
                FROM medicine_logs ml
                JOIN medicines m ON ml.medicine_id = m.id
                WHERE ml.scheduled_date = %s
                  AND ml.status = 'pending'
                  AND ml.scheduled_time <= %s
            """
            cursor.execute(overdue_query, (today_date, overdue_time_str))
            overdue_logs = cursor.fetchall()

            for olog in overdue_logs:
                update_missed_query = "UPDATE medicine_logs SET status = 'missed' WHERE id = %s"
                cursor.execute(update_missed_query, (olog['id'],))
                
                notif_query = """
                    INSERT INTO notifications (user_id, medicine_id, message, notification_type, sent_at, status)
                    VALUES (%s, %s, %s, 'missed', NOW(), 'sent')
                """
                cursor.execute(notif_query, (
                    olog['user_id'],
                    olog['medicine_id'],
                    f"Alert: Dose of {olog['medicine_name']} scheduled at {olog['scheduled_time']} was marked as MISSED."
                ))
                missed_marked += 1

            conn.commit()

        # Emit CloudWatch Custom Metrics for Lambda Monitoring
        try:
            cw_client.put_metric_data(
                Namespace='SmartMedicine/ReminderEngine',
                MetricData=[
                    {
                        'MetricName': 'LambdaRemindersSent',
                        'Value': float(notifications_sent),
                        'Unit': 'Count',
                        'Timestamp': datetime.datetime.now(datetime.timezone.utc)
                    },
                    {
                        'MetricName': 'LambdaMissedDosesMarked',
                        'Value': float(missed_marked),
                        'Unit': 'Count',
                        'Timestamp': datetime.datetime.now(datetime.timezone.utc)
                    }
                ]
            )
            logger.info("Published reminder metrics to Amazon CloudWatch.")
        except Exception as cw_err:
            logger.warning(f"Failed to publish CloudWatch metric from Lambda: {cw_err}")

    except Exception as exec_err:
        logger.error(f"Error during Lambda execution: {exec_err}", exc_info=True)
        try:
            cw_client.put_metric_data(
                Namespace='SmartMedicine/ReminderEngine',
                MetricData=[{
                    'MetricName': 'LambdaExecutionErrors',
                    'Value': 1.0,
                    'Unit': 'Count',
                    'Timestamp': datetime.datetime.now(datetime.timezone.utc)
                }]
            )
        except Exception:
            pass
        raise exec_err

    finally:
        conn.close()

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Reminder process executed successfully',
            'notifications_sent': notifications_sent,
            'missed_marked': missed_marked,
            'timestamp': local_now.isoformat()
        })
    }
