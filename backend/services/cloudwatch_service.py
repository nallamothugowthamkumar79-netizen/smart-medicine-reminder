import os
import sys
import time
import json
import logging
import datetime
import threading
import psutil
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config

logger = logging.getLogger('cloudwatch_service')

class CloudWatchService:
    """
    Amazon CloudWatch integration service for Smart Medicine Reminder System.
    Handles:
      - Custom Metric publishing (API traffic, latency, errors, reminders, CPU/RAM, DB health)
      - CloudWatch Logs ingestion (streaming backend application logs)
      - System telemetry and resource monitoring via psutil
      - Graceful local fallback when AWS credentials are not configured
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CloudWatchService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.enabled = Config.CLOUDWATCH_ENABLED
        self.region = Config.AWS_REGION
        self.namespace = Config.CLOUDWATCH_METRIC_NAMESPACE
        self.log_group = Config.CLOUDWATCH_LOG_GROUP
        self.log_stream = Config.CLOUDWATCH_LOG_STREAM
        self.is_aws_connected = False
        self.cw_client = None
        self.logs_client = None
        self.next_sequence_token = None
        self._start_time = time.time()

        if self.enabled:
            self._init_aws_clients()

        self._initialized = True

    def _init_aws_clients(self):
        """Initialize CloudWatch and CloudWatch Logs Boto3 clients safely."""
        try:
            session_kwargs = {'region_name': self.region}
            if Config.AWS_ACCESS_KEY_ID and Config.AWS_SECRET_ACCESS_KEY:
                session_kwargs['aws_access_key_id'] = Config.AWS_ACCESS_KEY_ID
                session_kwargs['aws_secret_access_key'] = Config.AWS_SECRET_ACCESS_KEY
                if Config.AWS_SESSION_TOKEN:
                    session_kwargs['aws_session_token'] = Config.AWS_SESSION_TOKEN

            self.cw_client = boto3.client('cloudwatch', **session_kwargs)
            self.logs_client = boto3.client('logs', **session_kwargs)

            # Test connection
            self.cw_client.list_metrics(Namespace=self.namespace)
            self._ensure_log_stream_exists()
            self.is_aws_connected = True
            logger.info(f"Connected to Amazon CloudWatch in {self.region} (Namespace: {self.namespace})")
        except (NoCredentialsError, ClientError) as e:
            self.is_aws_connected = False
            logger.info(f"Amazon CloudWatch running in local simulation fallback mode: {e}")
        except Exception as e:
            self.is_aws_connected = False
            logger.warning(f"CloudWatch initialization notice: {e}")

    def _ensure_log_stream_exists(self):
        """Ensures the CloudWatch Log Group and Stream exist."""
        if not self.logs_client:
            return
        try:
            self.logs_client.create_log_group(logGroupName=self.log_group)
        except Exception:
            pass

        try:
            self.logs_client.create_log_stream(
                logGroupName=self.log_group,
                logStreamName=self.log_stream
            )
        except Exception:
            pass

    def put_metric(self, metric_name, value, unit='Count', dimensions=None):
        """
        Publish a single metric to Amazon CloudWatch.
        Units: 'Count', 'Milliseconds', 'Percent', 'Bytes', etc.
        """
        if not self.enabled:
            return

        dims = [{'Name': 'Environment', 'Value': os.environ.get('FLASK_ENV', 'production')}]
        if dimensions:
            for k, v in dimensions.items():
                dims.append({'Name': k, 'Value': str(v)})

        metric_data = {
            'MetricName': metric_name,
            'Value': float(value),
            'Unit': unit,
            'Timestamp': datetime.datetime.now(datetime.timezone.utc),
            'Dimensions': dims
        }

        if self.is_aws_connected and self.cw_client:
            try:
                self.cw_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=[metric_data]
                )
            except Exception as e:
                logger.debug(f"Failed to emit CloudWatch metric {metric_name}: {e}")
        else:
            logger.debug(f"[CloudWatch Metric Simulation] {self.namespace} -> {metric_name}: {value} {unit}")

    def record_api_call(self, endpoint, method, status_code, duration_ms):
        """Record API request metrics and latency."""
        status_category = f"{status_code // 100}xx"
        
        # 1. Total Requests
        self.put_metric('APIRequests', 1, 'Count', {
            'Endpoint': endpoint,
            'Method': method,
            'StatusCode': str(status_code),
            'StatusCategory': status_category
        })

        # 2. Response Time / Latency
        self.put_metric('APIResponseTime', duration_ms, 'Milliseconds', {
            'Endpoint': endpoint,
            'Method': method
        })

        # 3. If 5xx error, increment APIErrors metric for CloudWatch Alarm
        if status_code >= 500:
            self.put_metric('APIErrors', 1, 'Count', {
                'Endpoint': endpoint,
                'StatusCode': str(status_code)
            })

    def record_reminder_dispatched(self, method_type='all', count=1):
        """Emits metric when a dose reminder is successfully sent."""
        self.put_metric('RemindersDispatched', count, 'Count', {'Channel': method_type})

    def record_reminder_failure(self, reason='sns_error', count=1):
        """Emits metric when a reminder dispatch fails (triggers high-priority alarm)."""
        self.put_metric('ReminderFailures', count, 'Count', {'Reason': reason})

    def record_missed_dose(self, count=1):
        """Emits metric when an overdue dose is marked missed."""
        self.put_metric('MissedDosesMarked', count, 'Count')

    def log_event(self, level, message, details=None):
        """
        Ship a structured log message to CloudWatch Logs (and standard logger).
        """
        log_payload = {
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'level': level.upper(),
            'message': message,
            'service': 'smart-medicine-backend',
            'details': details or {}
        }
        json_msg = json.dumps(log_payload)

        # Standard console log
        if level.lower() == 'error':
            logger.error(json_msg)
        elif level.lower() == 'warning':
            logger.warning(json_msg)
        else:
            logger.info(json_msg)

        # Ship to CloudWatch Logs
        if self.is_aws_connected and self.logs_client:
            try:
                timestamp_ms = int(time.time() * 1000)
                kwargs = {
                    'logGroupName': self.log_group,
                    'logStreamName': self.log_stream,
                    'logEvents': [{'timestamp': timestamp_ms, 'message': json_msg}]
                }
                if self.next_sequence_token:
                    kwargs['sequenceToken'] = self.next_sequence_token

                resp = self.logs_client.put_log_events(**kwargs)
                self.next_sequence_token = resp.get('nextSequenceToken')
            except Exception as e:
                logger.debug(f"CloudWatch Logs write notice: {e}")

    def get_system_metrics(self):
        """Collects CPU, Memory, Disk, and Process health."""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            try:
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
            except Exception:
                disk_percent = 0.0
            uptime_seconds = int(time.time() - self._start_time)
            
            return {
                'cpu_percent': round(cpu_percent, 1),
                'memory_percent': round(mem.percent, 1),
                'memory_used_mb': round(mem.used / (1024 * 1024), 1),
                'memory_total_mb': round(mem.total / (1024 * 1024), 1),
                'disk_percent': round(disk_percent, 1),
                'uptime_seconds': uptime_seconds,
                'cloudwatch_connected': self.is_aws_connected,
                'cloudwatch_namespace': self.namespace,
                'cloudwatch_log_group': self.log_group
            }
        except Exception as e:
            logger.warning(f"Error reading system telemetry: {e}")
            return {
                'cpu_percent': 0.0,
                'memory_percent': 0.0,
                'uptime_seconds': int(time.time() - self._start_time),
                'cloudwatch_connected': self.is_aws_connected
            }

    def publish_health_telemetry(self, db_connected=True):
        """Publish periodic health telemetry to CloudWatch for alarms."""
        metrics = self.get_system_metrics()
        self.put_metric('CPUUtilization', metrics.get('cpu_percent', 0), 'Percent')
        self.put_metric('MemoryUtilization', metrics.get('memory_percent', 0), 'Percent')
        self.put_metric('DatabaseConnected', 1 if db_connected else 0, 'Count')

# Singleton instance export
cloudwatch_service = CloudWatchService()
