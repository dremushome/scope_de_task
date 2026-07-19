import os
import time
import boto3
from botocore.client import Config

def bootstrap():
    print("Bootstrapping MinIO buckets...")
    s3 = boto3.client(
        's3',
        endpoint_url='http://localhost:9000',
        aws_access_key_id='minioadmin',
        aws_secret_access_key='minioadmin',
        config=Config(signature_version='s3v4')
    )
    
    # Wait for MinIO to be available
    max_retries = 30
    for i in range(max_retries):
        try:
            s3.list_buckets()
            break
        except Exception:
            if i == max_retries - 1:
                print("Failed to connect to MinIO after multiple attempts.")
                raise
            print(f"Waiting for MinIO to start (attempt {i+1}/{max_retries})...")
            time.sleep(1)
    
    # Ensure buckets exist
    for bucket in ['landing', 'archive']:
        try:
            # Check if bucket exists
            s3.head_bucket(Bucket=bucket)
            print(f"Bucket '{bucket}' already exists.")
        except Exception:
            try:
                s3.create_bucket(Bucket=bucket)
                print(f"Created bucket '{bucket}'.")
            except Exception as e:
                print(f"Failed to create bucket '{bucket}': {e}")
                
    # Upload fixtures to landing bucket
    fixture_dir = os.path.join("tests", "fixtures")
    if os.path.exists(fixture_dir):
        for filename in os.listdir(fixture_dir):
            if filename.endswith(".xlsm"):
                filepath = os.path.join(fixture_dir, filename)
                try:
                    s3.upload_file(filepath, 'landing', filename)
                    print(f"Successfully uploaded {filename} to 'landing' bucket.")
                except Exception as e:
                    print(f"Failed to upload {filename}: {e}")
    else:
        print(f"Fixture directory '{fixture_dir}' not found.")

if __name__ == "__main__":
    bootstrap()
