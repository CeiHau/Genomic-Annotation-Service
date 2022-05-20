from flask import Flask, request, Response, jsonify
import uuid
import subprocess
import os
import boto3
import botocore
import json

# Get configuration
from configparser import ConfigParser
config = ConfigParser(os.environ)
config.read('ann_config.ini')
region_name = config['aws']['AwsRegionName']
queue_url = config['sqs']['URL']
table_name = config['dynamodb']['TABLENAME']

# Connect to SQS and get the message queue
sqs = boto3.client('sqs', region_name = region_name)

base_path = '/home/ubuntu/gas/ann/data'
if not os.path.exists(base_path):
    os.makedirs(base_path)

# Poll the message queue in a loop 
while True:
    # Attempt to read a message from the queue
    # Use long polling - DO NOT use sleep() to wait between polls
    # ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/sqs-example-long-polling.html
    
    response = sqs.receive_message(
        QueueUrl = queue_url,
        AttributeNames=[
            'SentTimestamp'
        ],
        MaxNumberOfMessages=1,
        MessageAttributeNames=[
            'All'
        ],
        WaitTimeSeconds=10
    ) 
    print(response)
    # If message read, extract job parameters from the message body as before
    if 'Messages' in response:
        print("begin")
        Message_body = json.loads(response['Messages'][0]['Body'])
        print()
        receipt_handle = response['Messages'][0]['ReceiptHandle']
        print()
        Message = json.loads(Message_body['Message'])

        job_id = Message['job_id']
        user_id = Message['user_id']
        bucket_name = Message['s3_inputs_bucket']
        file_name = Message['input_file_name']
        key = Message['s3_key_input_file']
        email = Message['email']
        
        # Include below the same code you used in prior homework
        # Get the input file S3 object and copy it to a local file: https://boto3.amazonaws.com/v1/documentation/api/1.9.42/guide/s3-example-download-file.html
        s3 = boto3.resource('s3',region_name = region_name, config = botocore.client.Config(signature_version = 's3v4'))
        
        new_path = base_path +'/' + job_id
        if not os.path.exists(new_path):
            os.makedirs(new_path)
            
        try:
            s3.Bucket(bucket_name).download_file(key, new_path +'/' + file_name)
            print("Downloading...")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                raise("The object does not exist.")
            else:
                raise(e)

        # Launch annotation job as a background process with erro handling
        try:
        # https://stackoverflow.com/questions/4856583/how-do-i-pipe-a-subprocess-call-to-a-text-file save the stdout to file
            job = subprocess.Popen(["python", "/home/ubuntu/gas/ann/run.py", new_path +'/' + file_name, job_id, user_id, email])
            print("Luach annotation job")
        except subprocess.CalledProcessError:
            response_data = {
                "code": 500,
                "status": "error",
                "message": "annotator runs fail"
            }
            
            raise(response_data)     

        # Update the “job_status” key in the annotations DynamoDB table to “RUNNING” only if its current status is “PENDING” with erro handling
        dynamodb = boto3.resource('dynamodb', region_name = region_name, config = botocore.client.Config(signature_version = 's3v4'))
        table = dynamodb.Table(table_name)
        try:
            table.update_item(
                Key = {"job_id": job_id}, 
                UpdateExpression = 'SET job_status = :val1',
                ConditionExpression = 'job_status = :val2',  # https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_UpdateItem.html -> Conditional Update
                ExpressionAttributeValues={
                    ':val1': "RUNNING",
                    ':val2': "PENDING"
                }          
            )
        except botocore.exceptions.ClientError as error:
            response_body = {
                "code": 500,
                "data":{
                "status":"error",
                "message":error
                }
            }
            raise(response_body)        

        # Delete message from queue, if job was successfully submitted
        sqs.delete_message(
            QueueUrl =queue_url,
            ReceiptHandle=receipt_handle
        )