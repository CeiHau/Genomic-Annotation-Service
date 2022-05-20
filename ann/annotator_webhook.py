# annotator_webhook.py
#
# NOTE: This file lives on the AnnTools instance
# Modified to run as a web server that can be called by SNS to process jobs
# Run using: python annotator_webhook.py
#
# Copyright (C) 2011-2022 Vas Vasiliadis
# University of Chicago
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import requests, json, os, boto3, botocore
import subprocess

from flask import Flask, jsonify, request

app = Flask(__name__)
environment = 'ann_config.Config'
app.config.from_object(environment)

#  Get configuration
region_name = app.config['AWS_REGION_NAME']
table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
queue_url = app.config['AWS_SQS_REQUESTS_QUEUE_URL']

base_path = '/home/ubuntu/gas/ann/data'
if not os.path.exists(base_path):
    os.makedirs(base_path)

# Connect to SQS and get the message queue
sqs = boto3.client('sqs', region_name = region_name)

# Check if requests queue exists, otherwise create it



'''
A13 - Replace polling with webhook in annotator

Receives request from SNS; queries job queue and processes message.
Reads request messages from SQS and runs AnnTools as a subprocess.
Updates the annotations database with the status of the request.
'''
@app.route('/process-job-request', methods=['GET', 'POST'])
def annotate():
  # print('-----------------------request.headers-----------------------  ')
  # print(request.headers)
  # print('-----------------------request.data-----------------------  ')
  # print(json.loads(request.data.decode()))

  # print(type(request.data.decode()))
  if (request.method == 'GET'):
    return jsonify({
      "code": 405, 
      "error": "Expecting SNS POST request."
    }), 405

  # Get message 
  message =  json.loads(request.data.decode())

  # Check message type
  if request.headers['X-Amz-Sns-Message-Type'] == 'SubscriptionConfirmation':
    # Confirm SNS topic subscription confirmation
    print('\nConfirm SNS topic subscription confirmation')
    # Json parse the message
    response = requests.get(url = message['SubscribeURL'])
    print(response)
  else:  
    # Process job request notification
    print('\n --------Process job request notification--------')
    print(message)

    # Get information
    job_id = message['job_id']
    user_id = message['user_id']
    bucket_name = message['s3_inputs_bucket']
    file_name = message['input_file_name']
    key = message['s3_key_input_file']
    email = message['email']

    # Get the input file S3 object and copy it to a local file: https://boto3.amazonaws.com/v1/documentation/api/1.9.42/guide/s3-example-download-file.html
    s3 = boto3.resource('s3',region_name = region_name)
    
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
    dynamodb = boto3.resource('dynamodb', region_name = region_name)
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


  return jsonify({
    "code": 200, 
    "message": "Annotation job request processed."
  }), 200

app.run('0.0.0.0', debug=True)

### EOF