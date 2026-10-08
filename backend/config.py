import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-med-secret-key-2026-super-safe-production')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'smart-medicine-reminder-jwt-secret-key-2026-super-secure-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    # Database Configuration (Amazon RDS MySQL or Local SQLite fallback)
    DB_HOST = os.environ.get('DATABASE_HOST')
    DB_PORT = os.environ.get('DATABASE_PORT', '3306')
    DB_NAME = os.environ.get('DATABASE_NAME', 'smart_medicine_db')
    DB_USER = os.environ.get('DATABASE_USER', 'admin')
    DB_PASSWORD = os.environ.get('DATABASE_PASSWORD', '')

    if DB_HOST:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    else:
        # Seamless local SQLite database for instant local development/testing
        base_dir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(base_dir, 'smart_medicine.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # AWS Configuration
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_SESSION_TOKEN = os.environ.get('AWS_SESSION_TOKEN')
    SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

    # Amazon CloudWatch Configuration
    CLOUDWATCH_ENABLED = os.environ.get('CLOUDWATCH_ENABLED', 'True').lower() in ('true', '1', 'yes')
    CLOUDWATCH_LOG_GROUP = os.environ.get('CLOUDWATCH_LOG_GROUP', '/aws/smart-medicine/backend')
    CLOUDWATCH_LOG_STREAM = os.environ.get('CLOUDWATCH_LOG_STREAM', f'api-server-{os.getpid()}')
    CLOUDWATCH_METRIC_NAMESPACE = os.environ.get('CLOUDWATCH_METRIC_NAMESPACE', 'SmartMedicine/Application')
    CLOUDWATCH_BUFFER_SIZE = int(os.environ.get('CLOUDWATCH_BUFFER_SIZE', 20))

    # Application Settings
    GRACE_PERIOD_MINUTES = int(os.environ.get('GRACE_PERIOD_MINUTES', 60))
    TIMEZONE_OFFSET_HOURS = float(os.environ.get('TIMEZONE_OFFSET_HOURS', 5.5))  # Default IST (+5:30) or configurable
