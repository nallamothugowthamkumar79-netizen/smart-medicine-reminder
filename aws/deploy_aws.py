import os
import sys
import time
import zipfile
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

def print_banner():
    print("=" * 70)
    print("   SMART MEDICINE REMINDER SYSTEM - AWS DEPLOYMENT AUTOMATOR")
    print("=" * 70)

def check_aws_credentials():
    print("\n[Step 1/5] Verifying AWS Credentials...")
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        print(f"  ✓ Connected to AWS Account: {identity.get('Account')}")
        print(f"  ✓ IAM Principal: {identity.get('Arn')}")
        return True
    except (NoCredentialsError, ClientError) as e:
        print("\n  [!] AWS Credentials Error:")
        print("  Could not find active AWS credentials.")
        print("  Please configure credentials using:")
        print("    1. Environment variables (AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY)")
        print("    2. Or run: aws configure")
        return False

def package_lambda_zip(output_path="lambda_package.zip"):
    print("\n[Step 2/5] Packaging AWS Lambda Reminder Function...")
    lambda_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lambda"))
    lambda_py = os.path.join(lambda_dir, "lambda_function.py")
    
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(lambda_py, arcname="lambda_function.py")
    print(f"  ✓ Created {output_path}")
    return output_path

def deploy_cloudformation_stack(stack_name="SmartMedicineReminderStack", region="us-east-1"):
    print(f"\n[Step 3/5] Deploying CloudFormation Stack: {stack_name} in {region}...")
    cf = boto3.client("cloudformation", region_name=region)
    cf_template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "cloudformation.yaml"))
    
    with open(cf_template_path, "r", encoding="utf-8") as f:
        template_body = f.read()

    params = [
        {"ParameterKey": "DBMasterPassword", "ParameterValue": "SmartMedPass2026!"},
        {"ParameterKey": "AdminEmail", "ParameterValue": "patient-alerts@example.com"}
    ]

    try:
        print("  Checking if stack already exists...")
        cf.describe_stacks(StackName=stack_name)
        print("  Stack exists, updating...")
        cf.update_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=params,
            Capabilities=["CAPABILITY_NAMED_IAM"]
        )
    except ClientError as e:
        if "does not exist" in str(e):
            print("  Stack does not exist. Creating new stack...")
            cf.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=["CAPABILITY_NAMED_IAM"]
            )
        else:
            print(f"  Notice: {e}")

    print("  Waiting for CloudFormation stack provisioning (this may take 5-10 minutes for RDS)...")
    waiter = cf.get_waiter("stack_create_complete")
    try:
        waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 30, "MaxAttempts": 30})
        print("  ✓ Stack provisioning complete!")
    except Exception as ex:
        print(f"  Note: Waiter completed with status: {ex}")

    # Fetch outputs
    desc = cf.describe_stacks(StackName=stack_name)
    outputs = desc["Stacks"][0].get("Outputs", [])
    print("\n[Step 4/5] AWS Infrastructure Deployed Successfully:")
    endpoints = {}
    for out in outputs:
        print(f"  • {out['OutputKey']}: {out['OutputValue']}")
        endpoints[out['OutputKey']] = out['OutputValue']
    return endpoints

def upload_frontend_to_s3(bucket_name, region="us-east-1"):
    print(f"\n[Step 5/5] Uploading Frontend files to S3 bucket: {bucket_name}...")
    s3 = boto3.client("s3", region_name=region)
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

    content_types = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".svg": "image/svg+xml"
    }

    for root, _, files in os.walk(frontend_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, frontend_dir).replace("\\", "/")
            ext = os.path.splitext(file)[1].lower()
            ctype = content_types.get(ext, "text/plain")

            with open(full_path, "rb") as f:
                s3.put_object(
                    Bucket=bucket_name,
                    Key=rel_path,
                    Body=f.read(),
                    ContentType=ctype
                )
            print(f"  ✓ Uploaded {rel_path} ({ctype})")
    print(f"  ✓ Frontend published successfully to S3!")

def main():
    print_banner()
    if not check_aws_credentials():
        print("\nDeployment paused until AWS credentials are provided.")
        sys.exit(1)
    
    package_lambda_zip()
    endpoints = deploy_cloudformation_stack()
    bucket_url = endpoints.get("WebsiteURL", "")
    if bucket_url:
        bucket_name = bucket_url.replace("http://", "").split(".")[0]
        upload_frontend_to_s3(bucket_name)

    print("\n" + "=" * 70)
    print("   AWS CLOUDWATCH MONITORING & SYSTEM DEPLOYMENT SUMMARY")
    print("=" * 70)
    print(f"  • Frontend Website:    {endpoints.get('WebsiteURL', 'N/A')}")
    print(f"  • Backend REST API:    {endpoints.get('BackendAPIURL', 'N/A')}")
    print(f"  • CloudWatch Dashboard:{endpoints.get('CloudWatchDashboardName', 'SmartMedicine-Operational-Dashboard')}")
    print(f"  • CloudWatch Logs:     {endpoints.get('BackendLogGroupName', '/aws/smart-medicine/backend')}")
    print(f"  • SNS Topic ARN:       {endpoints.get('SNSTopicArn', 'N/A')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
