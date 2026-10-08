#!/bin/bash
# =============================================================================
# SMART MEDICINE REMINDER - EC2 PROVISIONING & SETUP SCRIPT
# =============================================================================

set -e

echo "=== [1/6] Updating packages & installing system dependencies ==="
sudo dnf update -y || sudo apt-get update -y
sudo dnf install -y python3-pip git nginx || sudo apt-get install -y python3-pip git nginx

echo "=== [2/6] Preparing Application Directory ==="
sudo mkdir -p /var/www/smart-medicine
sudo chown -R $USER:$USER /var/www/smart-medicine
cd /var/www/smart-medicine

# Copy or clone backend files here
echo "=== [3/6] Setting up Python Virtual Environment ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "=== [4/6] Creating Systemd Service for Flask / Gunicorn ==="
sudo bash -c 'cat << EOF > /etc/systemd/system/smart-medicine.service
[Unit]
Description=Smart Medicine Reminder Flask Service
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/var/www/smart-medicine/backend
Environment="PATH=/var/www/smart-medicine/venv/bin"
EnvironmentFile=/var/www/smart-medicine/backend/.env
ExecStart=/var/www/smart-medicine/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF'

echo "=== [5/6] Configuring Nginx Reverse Proxy (Port 80 -> 5000) ==="
sudo bash -c 'cat << EOF > /etc/nginx/conf.d/smart-medicine.conf
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF'

echo "=== [6/7] Installing & Configuring Amazon CloudWatch Agent ==="
sudo dnf install -y amazon-cloudwatch-agent || sudo apt-get install -y amazon-cloudwatch-agent

sudo bash -c 'cat << EOF > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "metrics": {
    "namespace": "SmartMedicine/EC2",
    "metrics_collected": {
      "cpu": {
        "measurement": [
          "cpu_usage_idle",
          "cpu_usage_iowait",
          "cpu_usage_system",
          "cpu_usage_user"
        ],
        "metrics_collection_interval": 60,
        "totalcpu": true
      },
      "mem": {
        "measurement": [
          "mem_used_percent"
        ],
        "metrics_collection_interval": 60
      },
      "disk": {
        "measurement": [
          "used_percent"
        ],
        "metrics_collection_interval": 60,
        "resources": [
          "/"
        ]
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/nginx/access.log",
            "log_group_name": "/aws/ec2/smart-medicine-backend",
            "log_stream_name": "nginx-access-{instance_id}"
          },
          {
            "file_path": "/var/log/nginx/error.log",
            "log_group_name": "/aws/ec2/smart-medicine-backend",
            "log_stream_name": "nginx-error-{instance_id}"
          }
        ]
      }
    }
  }
}
EOF'

# Start and enable CloudWatch Agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json || true
sudo systemctl enable amazon-cloudwatch-agent || true

echo "=== [7/7] Reloading and Starting Services ==="
sudo systemctl daemon-reload
sudo systemctl enable smart-medicine
sudo systemctl restart smart-medicine
sudo systemctl restart nginx

echo "=== Smart Medicine Reminder is now running on EC2 with CloudWatch monitoring! ==="
