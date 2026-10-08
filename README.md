# 🏥 Smart Medicine Reminder System - Full-Stack AWS Healthcare Application

> **A full-stack, cloud-native medication adherence platform built with AWS (EC2, RDS MySQL, S3, Lambda, SNS, IAM, and Amazon CloudWatch) and a responsive, elderly-friendly Government Health Portal frontend.**

---

## 📋 Table of Contents
- [Project Overview](#-project-overview)
- [AWS Cloud Architecture](#-aws-cloud-architecture)
- [AWS Services Utilized](#-aws-services-utilized)
- [Amazon CloudWatch Observability & Monitoring](#-amazon-cloudwatch-observability--monitoring)
- [Project Directory Structure](#-project-directory-structure)
- [Getting Started (Local Development)](#-getting-started-local-development)
- [Deploying to AWS](#-deploying-to-aws)
- [Security & Best Practices](#-security--best-practices)

---

## 🎯 Project Overview

The **Smart Medicine Reminder System** is engineered to eliminate missed prescription doses among seniors and patients with chronic illnesses. It provides:
- **Elderly-Friendly Government Health UI**: High contrast, tactile controls, multi-language branding, and font resizers (`A-`, `A`, `A+`).
- **Autonomous Multi-Channel Alerts**: Automated SMS to mobile phones and Email reminders dispatched via **Amazon SNS**.
- **Real-Time Adherence Tracking**: Instant "Mark as Taken" with Web Audio chime confirmation and historical adherence percentage analytics.
- **Enterprise Cloud Reliability**: Decoupled, serverless architecture powered by **AWS Lambda**, **Amazon CloudWatch**, **Amazon RDS MySQL**, and **Amazon EC2**.

---

## 🏛️ AWS Cloud Architecture

```text
       +-------------------------------------------------------+
       |               End User / Senior Patient               |
       +-------------------------------------------------------+
              |                                          ^
              | HTTP / HTTPS                             | SMS & Email Alerts
              v                                          |
       +--------------+                           +--------------+
       |  Amazon S3   |                           |  Amazon SNS  |
       | Static Web   |                           | Multi-Channel|
       +------+-------+                           +-------+------+
              |                                           ^
              | REST API Calls                            | Alert Dispatch
              v                                           |
       +--------------+     SQL Query             +-------+------+
       |  Amazon EC2  +-------------------------->|  Amazon RDS  |
       | Flask Server |                           |  MySQL 8.0   |
       +------+-------+                           +-------+------+
              |                                           ^
       Metrics| & Logs                                    | Active Doses
              v                                           |
       +--------------+     Schedule Rule         +-------+------+
       |Amazon        +-------------------------->|  AWS Lambda  |
       |CloudWatch    |     rate(1 minute)        |ReminderEngine|
       +--------------+                           +--------------+
```

---

## ☁️ AWS Services Utilized

1. **Amazon EC2 (Elastic Compute Cloud)**: Virtual Linux host (`t3.micro`) running the Python Flask REST API server under Gunicorn and Nginx with systemd service management.
2. **Amazon RDS (Relational Database Service - MySQL 8.0)**: Managed relational database storing `users`, `medicines`, `medicine_schedules`, `medicine_logs`, and `notifications` with automated backups and ACID consistency.
3. **Amazon S3 (Simple Storage Service)**: Static website hosting for the patient portal SPA with 99.999999999% durability and low-latency asset delivery.
4. **AWS Lambda**: Autonomous serverless compute engine checking dose schedules every minute without persistent idle compute costs.
5. **Amazon SNS (Simple Notification Service)**: Multi-channel messaging delivering transactional SMS alerts directly to phones and Email notifications via subscription topics.
6. **AWS IAM (Identity and Access Management)**: Least-privilege roles (`SmartMed-EC2-Role`, `SmartMed-Lambda-Role`) ensuring temporary STS credentials without hardcoded access keys.
7. **Amazon CloudWatch**: Complete operational observability suite for application logs, custom metrics, scheduled triggers, failure alarms, and CPU/memory telemetry.

---

## 📊 Amazon CloudWatch Observability & Monitoring

The system implements end-to-end telemetry across all application layers using **Amazon CloudWatch**:

### 1. Application & Backend Monitoring
- **Custom Metrics (`SmartMedicine/Application`)**:
  - `APIRequests`: Request volume broken down by endpoint, method, and HTTP status category.
  - `APIResponseTime`: Real-time API latency measured in milliseconds per endpoint.
  - `APIErrors`: Count of 5xx internal server errors.
  - `RemindersDispatched`: Tracked per delivery channel (`sms`, `email`).
  - `ReminderFailures`: Tracked per failure reason.
  - `MissedDosesMarked`: Total overdue doses automatically flagged as missed.
  - `DatabaseConnected`: 1 for healthy database connectivity, 0 for failure.

### 2. EC2 & OS-Level Monitoring
- **Amazon CloudWatch Agent (`amazon-cloudwatch-agent`)**:
  - Configured via `/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json`.
  - Continuously streams OS metrics to namespace `SmartMedicine/EC2`:
    - CPU utilization (`cpu_usage_idle`, `cpu_usage_system`, `cpu_usage_user`).
    - Memory utilization (`mem_used_percent`).
    - Disk space utilization (`used_percent`).

### 3. Lambda Serverless Monitoring
- CloudWatch logs every execution into `/aws/lambda/SmartMedicineReminderEngine`.
- Publishes custom execution telemetry to `SmartMedicine/ReminderEngine`:
  - `LambdaRemindersSent`: Count of doses processed.
  - `LambdaMissedDosesMarked`: Count of overdue transitions.
  - `LambdaExecutionErrors`: Unhandled Lambda exceptions.

### 4. Application Log Collection
- Backend Python service (`cloudwatch_service.py`) streams structured JSON logs to CloudWatch Logs log group:
  - Log Group: `/aws/smart-medicine/backend`
  - Stream: `api-server-<pid>`
- Nginx access and error logs streamed to `/aws/ec2/smart-medicine-backend`.

### 5. Automated CloudWatch Alarms for Important Failures
CloudFormation provisions 5 automated alarms that immediately dispatch alert notifications to `MedicineSNSTopic` (SMS & Email):

| Alarm Name | Monitored Metric | Threshold | Action |
| :--- | :--- | :--- | :--- |
| **SmartMed-EC2-HighCPU-Alarm** | `CPUUtilization` (EC2) | $\ge 80\%$ for 2 periods (10 min) | Alerts Admin via SNS |
| **SmartMed-Backend-HighErrorRate-Alarm** | `APIErrors` (Application) | $\ge 5$ errors in 5 min | Alerts Admin via SNS |
| **SmartMed-Database-ConnectionFailure-Alarm** | `DatabaseConnected` | $< 1$ (Connection lost) | Alerts Admin via SNS |
| **SmartMed-Lambda-ExecutionFailure-Alarm** | `Errors` (Lambda) | $\ge 1$ failure in 5 min | Alerts Admin via SNS |
| **SmartMed-Reminder-DeliveryFailure-Alarm** | `ReminderFailures` (Application)| $\ge 1$ delivery failure | Alerts Admin via SNS |

### 6. CPU Usage & Application Health Telemetry Endpoint
Query `GET /api/health` to receive real-time system metrics and CloudWatch telemetry:
```json
{
  "status": "healthy",
  "database": "connected",
  "cloudwatch_monitoring": {
    "enabled": true,
    "connected_to_aws": false,
    "namespace": "SmartMedicine/Application",
    "log_group": "/aws/smart-medicine/backend"
  },
  "system_telemetry": {
    "cpu_utilization_percent": 12.4,
    "memory_utilization_percent": 65.2,
    "memory_used_mb": 10485.9,
    "memory_total_mb": 15800.6,
    "uptime_seconds": 180
  }
}
```

---

## 📂 Project Directory Structure

```
smart-medicine-reminder/
├── backend/
│   ├── app.py                     # Flask application factory, CORS, request telemetry & health check
│   ├── config.py                  # Database, AWS & CloudWatch configuration
│   ├── models.py                  # SQLAlchemy ORM models (User, Medicine, Schedules, Logs, Notifications)
│   ├── wsgi.py                    # Production WSGI entrypoint for Gunicorn
│   ├── requirements.txt           # Python dependencies (includes psutil)
│   ├── routes/
│   │   ├── auth.py                # Registration, Login, Profile & JWT token verification
│   │   ├── medicines.py           # CRUD operations for medicines and schedules
│   │   ├── doses.py               # Today's dose tracking, Mark as Taken / Missed
│   │   ├── history.py             # Historical logs, filters & Adherence % calculation
│   │   └── notifications.py       # Notification audit logs & manual test trigger
│   └── services/
│       ├── cloudwatch_service.py  # Amazon CloudWatch metrics, logs & system telemetry engine
│       ├── sns_service.py         # AWS SNS client (SMS & Email dispatch with CloudWatch metrics)
│       └── scheduler_service.py   # Autonomous scheduler daemon with CloudWatch telemetry
├── frontend/
│   ├── index.html                 # National Health Portal UI + responsive patient dashboard
│   ├── css/
│   │   └── style.css              # Government aesthetic, high contrast UI & large touch buttons
│   └── js/
│       ├── api.js                 # Centralized API fetch client with JWT management
│       └── app.js                 # View router, chime synthesizer, IST clock & DOM controller
├── lambda/
│   ├── lambda_function.py         # Standalone AWS Lambda handler with CloudWatch metrics
│   └── requirements.txt           # PyMySQL & Boto3 for Lambda Layer
├── aws/
│   ├── cloudformation.yaml        # Infrastructure as Code (S3, EC2, RDS, Lambda, SNS, IAM, CloudWatch)
│   ├── deploy_aws.py              # Automated Python Boto3 provisioning & monitoring summary
│   ├── ec2_setup.sh               # UserData bootstrap script (Gunicorn + Nginx + CloudWatch Agent)
│   └── rds_schema.sql             # MySQL DDL schema for Amazon RDS
├── tests/
│   ├── test_api.py                # End-to-end API, Auth, CRUD & Adherence test suite
│   ├── test_lambda.py             # AWS Lambda handler test suite
│   └── test_cloudwatch.py         # Amazon CloudWatch metrics, logging & telemetry test suite
├── README.md                      # Complete system documentation & CloudWatch guide
└── VIVA_GUIDE.md                  # Academic viva presentation guide & architecture Q&A
```

---

## 🚀 Getting Started (Local Development)

The application features **zero-friction local execution** with an automatic SQLite fallback when Amazon RDS credentials are not yet entered, allowing complete local verification:

### 1. Install Dependencies
```bash
cd smart-medicine-reminder
pip install -r backend/requirements.txt
```

### 2. Launch the Application
```bash
cd backend
python app.py
```

### 3. Open in Browser
Open **`http://localhost:5000`** in your browser.
- Register a new citizen account.
- Add your prescribed medicines with daily schedule times.
- View real-time dose status on the dashboard and mark doses as taken.
- Test the instant SMS/Email reminder dispatch button.

### 4. Run Automated Tests
```bash
python -m unittest tests/test_api.py tests/test_lambda.py tests/test_cloudwatch.py
```

---

## ☁️ Deploying to AWS

### Option 1: Automated Script (`deploy_aws.py`)
1. Configure AWS credentials:
   ```bash
   aws configure
   ```
2. Run the deployment script:
   ```bash
   python aws/deploy_aws.py
   ```
The script will package the Lambda zip, deploy the CloudFormation stack, create S3 static website hosting, provision RDS MySQL and EC2, configure CloudWatch Agent & Alarms, and upload frontend files automatically.

### Option 2: AWS Management Console
1. **Amazon RDS**: Create a MySQL 8.0 `db.t3.micro` instance named `smart_medicine_db`. Run the DDL statements from `aws/rds_schema.sql`.
2. **Amazon SNS**: Create a Standard Topic named `SmartMedicineReminders`. Add SMS and Email subscriptions.
3. **AWS Lambda**: Create a Python 3.11 function, paste `lambda/lambda_function.py`, and set environment variables (`DATABASE_HOST`, `DATABASE_USER`, `DATABASE_PASSWORD`, `SNS_TOPIC_ARN`, `AWS_REGION`).
4. **Amazon CloudWatch Events**: Create a Schedule Rule with rate `rate(1 minute)` targeting the Lambda function.
5. **Amazon CloudWatch Alarms & Logs**: Create log group `/aws/smart-medicine/backend` and alarms for EC2 CPU and API errors.
6. **Amazon EC2**: Launch an Amazon Linux 2023 `t3.micro` instance. Run `aws/ec2_setup.sh`.
7. **Amazon S3**: Create a bucket with Static Website Hosting enabled. Upload the contents of `frontend/`.

---

## 🔒 Security & Least-Privilege IAM Roles
- **No Hardcoded Keys**: All AWS credentials and database passwords are loaded via environment variables or IAM instance profiles.
- **Principle of Least Privilege**:
  - `SmartMed-EC2-Role`: Scoped to `logs:PutLogEvents` on `/aws/*`, `cloudwatch:PutMetricData` restricted to namespace `SmartMedicine/*`, and `sns:Publish`.
  - `SmartMed-Lambda-Role`: Restricted to `cloudwatch:PutMetricData` on namespace `SmartMedicine/ReminderEngine` and `sns:Publish`.
- **SQL Injection Prevention**: SQLAlchemy ORM and parameterized queries ensure input sanitization.
- **Password Security**: Passwords hashed using standard cryptographic algorithms (`generate_password_hash`).
- **Access Isolation**: JWT tokens ensure users can strictly access only their own medical records and schedules.
