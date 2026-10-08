import logging
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, Medicine, MedicineSchedule, MedicineLog, Notification, User
from services.sns_service import sns_service
from services.cloudwatch_service import cloudwatch_service
from config import Config

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def get_current_local_time():
    """
    Returns current local datetime adjusting for configured timezone offset.
    """
    offset = timedelta(hours=Config.TIMEZONE_OFFSET_HOURS)
    # Using system local time or utc + offset
    now_local = datetime.now()
    return now_local

def check_and_send_reminders(app):
    """
    Core reminder logic:
    1. Finds all active medicines scheduled for the current minute.
    2. Sends SNS notifications (SMS/Email) to the user.
    3. Creates/updates MedicineLog and Notification audit records.
    4. Automatically flags overdue pending medicines as 'missed' if past grace period.
    """
    with app.app_context():
        try:
            now = get_current_local_time()
            current_time_str = now.strftime('%H:%M')
            today = now.date()

            # -------------------------------------------------------------
            # 1. Check for Doses Scheduled for the Current Minute
            # -------------------------------------------------------------
            active_schedules = (
                db.session.query(MedicineSchedule, Medicine, User)
                .join(Medicine, MedicineSchedule.medicine_id == Medicine.id)
                .join(User, Medicine.user_id == User.id)
                .filter(
                    Medicine.active == True,
                    Medicine.start_date <= today,
                    (Medicine.end_date == None) | (Medicine.end_date >= today),
                    MedicineSchedule.scheduled_time == current_time_str
                )
                .all()
            )

            for schedule, medicine, user in active_schedules:
                # Ensure a log entry exists for today at this scheduled time
                log = MedicineLog.query.filter_by(
                    medicine_id=medicine.id,
                    user_id=user.id,
                    scheduled_date=today,
                    scheduled_time=schedule.scheduled_time
                ).first()

                if not log:
                    log = MedicineLog(
                        medicine_id=medicine.id,
                        user_id=user.id,
                        scheduled_date=today,
                        scheduled_time=schedule.scheduled_time,
                        status='pending'
                    )
                    db.session.add(log)
                    db.session.commit()

                # If the dose has not yet been marked taken, send reminder notification
                if log.status == 'pending':
                    # Check if notification already sent in the last 10 minutes to avoid duplicates
                    recent_notification = Notification.query.filter(
                        Notification.user_id == user.id,
                        Notification.medicine_id == medicine.id,
                        Notification.notification_type == 'reminder',
                        Notification.sent_at >= datetime.utcnow() - timedelta(minutes=10)
                    ).first()

                    if not recent_notification:
                        reminder_res = sns_service.send_reminder(
                            user=user,
                            medicine=medicine,
                            scheduled_time=schedule.scheduled_time,
                            method_override=schedule.reminder_method
                        )

                        notification = Notification(
                            user_id=user.id,
                            medicine_id=medicine.id,
                            message=reminder_res['message'],
                            notification_type='reminder',
                            status=reminder_res['status']
                        )
                        db.session.add(notification)
                        db.session.commit()
                        logger.info(f"Dispatched reminder for {medicine.medicine_name} to user {user.name}")

            # -------------------------------------------------------------
            # 2. Check for Overdue Doses and Mark as 'Missed'
            # -------------------------------------------------------------
            grace_delta = timedelta(minutes=Config.GRACE_PERIOD_MINUTES)
            pending_logs = MedicineLog.query.filter(
                MedicineLog.scheduled_date == today,
                MedicineLog.status == 'pending'
            ).all()

            for plog in pending_logs:
                try:
                    sched_parts = plog.scheduled_time.split(':')
                    sched_dt = datetime.combine(today, datetime.min.time()).replace(
                        hour=int(sched_parts[0]),
                        minute=int(sched_parts[1])
                    )
                    if now > (sched_dt + grace_delta):
                        plog.status = 'missed'
                        # Record missed notification
                        med_name = plog.medicine.medicine_name if plog.medicine else 'Prescribed Medicine'
                        missed_notif = Notification(
                            user_id=plog.user_id,
                            medicine_id=plog.medicine_id,
                            message=f"Alert: Scheduled dose of {med_name} at {plog.scheduled_time} was marked as MISSED.",
                            notification_type='missed',
                            status='sent'
                        )
                        db.session.add(missed_notif)
                        cloudwatch_service.record_missed_dose(1)
                        logger.info(f"Marked dose ID {plog.id} as missed.")
                except Exception as ex:
                    logger.warning(f"Error checking overdue dose {plog.id}: {ex}")

            db.session.commit()

        except Exception as e:
            logger.error(f"Error in scheduler reminder job: {e}", exc_info=True)
            cloudwatch_service.log_event('error', f"Scheduler execution error: {str(e)}")
            cloudwatch_service.put_metric('APIErrors', 1, 'Count', {'Component': 'Scheduler'})
            db.session.rollback()

def start_scheduler(app):
    """
    Starts APScheduler in background thread.
    Checks for due reminders every 60 seconds.
    """
    if not scheduler.running:
        scheduler.add_job(
            func=check_and_send_reminders,
            args=[app],
            trigger='interval',
            seconds=60,
            id='medicine_reminder_job',
            replace_existing=True
        )
        scheduler.start()
        logger.info("Medicine reminder scheduler started (interval: 60s).")

def trigger_check_now(app):
    """Manual trigger endpoint for immediate testing."""
    check_and_send_reminders(app)
