import os
import time
import traceback
import logging
from flask import Flask, jsonify, send_from_directory, request, g
from flask_cors import CORS
from config import Config
from models import db, User, Medicine, MedicineSchedule, MedicineLog, Notification
from routes.auth import auth_bp
from routes.medicines import medicines_bp
from routes.doses import doses_bp
from routes.history import history_bp
from routes.notifications import notifications_bp
from services.scheduler_service import start_scheduler
from services.cloudwatch_service import cloudwatch_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_class=Config, test_config=None):
    # Frontend directory path
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
    
    app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
    app.config.from_object(config_class)
    if test_config:
        app.config.update(test_config)

    # Enable Cross-Origin Resource Sharing for modern decoupled frontends (S3 hosting, etc.)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize Database
    db.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(medicines_bp, url_prefix='/api/medicines')
    app.register_blueprint(doses_bp, url_prefix='/api')
    app.register_blueprint(history_bp, url_prefix='/api/history')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')

    # Amazon CloudWatch Request Telemetry Hooks
    @app.before_request
    def before_request_hook():
        g.start_time = time.time()

    @app.after_request
    def after_request_hook(response):
        if hasattr(g, 'start_time'):
            duration_ms = round((time.time() - g.start_time) * 1000, 2)
            # Record CloudWatch API traffic & latency metrics
            if request.path.startswith('/api'):
                cloudwatch_service.record_api_call(
                    endpoint=request.path,
                    method=request.method,
                    status_code=response.status_code,
                    duration_ms=duration_ms
                )
        return response

    # Global Exception Handler (Ships trace to CloudWatch Logs & increments APIErrors metric)
    @app.errorhandler(500)
    def handle_500_error(err):
        cloudwatch_service.log_event(
            level='error',
            message=f"500 Internal Error on {request.method} {request.path}: {str(err)}",
            details={'traceback': traceback.format_exc(), 'path': request.path, 'method': request.method}
        )
        cloudwatch_service.put_metric('APIErrors', 1, 'Count', {'Endpoint': request.path})
        return jsonify({'error': 'Internal server error occurred. Telemetry recorded in CloudWatch.'}), 500

    @app.errorhandler(Exception)
    def handle_unhandled_exception(err):
        cloudwatch_service.log_event(
            level='error',
            message=f"Unhandled Exception on {request.method} {request.path}: {str(err)}",
            details={'traceback': traceback.format_exc(), 'path': request.path, 'method': request.method}
        )
        cloudwatch_service.put_metric('APIErrors', 1, 'Count', {'Endpoint': request.path})
        return jsonify({'error': f"An error occurred: {str(err)}"}), 500

    # Health Check & CloudWatch Monitoring Telemetry Endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        db_status = 'connected'
        db_healthy = True
        try:
            db.session.execute(db.text('SELECT 1'))
        except Exception as e:
            db_status = f'disconnected: {str(e)}'
            db_healthy = False

        # Gather system telemetry (CPU, Memory, Disk, Uptime)
        telemetry = cloudwatch_service.get_system_metrics()
        
        # Publish health metrics to CloudWatch
        cloudwatch_service.publish_health_telemetry(db_connected=db_healthy)

        return jsonify({
            'status': 'healthy' if db_healthy else 'degraded',
            'service': 'Smart Medicine Reminder API',
            'database': db_status,
            'version': '1.0.0',
            'cloudwatch_monitoring': {
                'enabled': Config.CLOUDWATCH_ENABLED,
                'connected_to_aws': telemetry.get('cloudwatch_connected', False),
                'namespace': Config.CLOUDWATCH_METRIC_NAMESPACE,
                'log_group': Config.CLOUDWATCH_LOG_GROUP
            },
            'system_telemetry': {
                'cpu_utilization_percent': telemetry.get('cpu_percent'),
                'memory_utilization_percent': telemetry.get('memory_percent'),
                'memory_used_mb': telemetry.get('memory_used_mb'),
                'memory_total_mb': telemetry.get('memory_total_mb'),
                'disk_utilization_percent': telemetry.get('disk_percent'),
                'uptime_seconds': telemetry.get('uptime_seconds')
            }
        }), 200 if db_healthy else 503

    # Serve Frontend Single Page Application
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path != "" and os.path.exists(os.path.join(frontend_dir, path)):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, 'index.html')

    # Initialize tables and background reminder daemon
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables initialized successfully.")
        except Exception as e:
            logger.error(f"Error during database table initialization: {e}")

        # Start autonomous reminder scheduler (APScheduler)
        # Avoid running duplicate scheduler if Werkzeug reloader is active
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
            start_scheduler(app)

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Smart Medicine Reminder Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
