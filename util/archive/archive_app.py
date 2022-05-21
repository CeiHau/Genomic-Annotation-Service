# archive_app.py
#
# Archive free user data
#
# Copyright (C) 2011-2021 Vas Vasiliadis
# University of Chicago
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import json, requests
import os,sys

import boto3
from flask import Flask, request, session, jsonify

app = Flask(__name__)
environment = 'archive_app_config.Config'
app.config.from_object(environment)


#  Get configuration
region_name = app.config['AWS_REGION_NAME']
table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
queue_url = app.config['AWS_SQS_REQUESTS_QUEUE_URL']
bucket_name = app.config['AWS_S3_RESULTS_BUCKET']
state_machine_arn = app.config['STATE_MACHINE_ARN']

# Import utility helpers
sys.path.insert(1, os.path.realpath(os.path.pardir))
import helpers

@app.route('/', methods=['GET'])
def home():
  user_id = session['primary_identity']
  print(user_id)
  return (f"This is the Archive utility: POST requests to /archive.")

@app.route('/archive', methods=['POST'])
def archive_free_user_data():

  # Get message 
  message =  json.loads(request.data.decode())
  print(message)
  
  if request.headers['X-Amz-Sns-Message-Type'] == 'SubscriptionConfirmation':
    # Confirm SNS topic subscription confirmation
    print('----------------confirm----------------')
    response = requests.get(url = message['SubscribeURL'])
    print(response)
  else:  
    # Get information from message
    print('\n --------Process job request notification--------')
    print(message)
    user_id = message['user_id']
    job_id = message['job_id']
    s3_key_result_file = message['s3_key_result_file']
    profile = helpers.get_user_profile(user_id)
    user_type = profile[4]

    # Check user type
    if user_type == 'free_user':
      # For free user, move S3 object to glacier
      # Set the input
      input = json.dumps({
        'region_name' : region_name,
        'bukcet_name' : bucket_name,
        'job_id': job_id,
        's3_key_result_file': s3_key_result_file,
      })
      
      # Open a connection to the S3 service
      sfn_client = boto3.client('stepfunctions', region_name = region_name)

      # Execute step function
      execution_response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn, 
        name = job_id,
        input=input
      )
      print(execution_response)

  return jsonify({
    "code": 200, 
    "message": "Archive the S3 object."
  }), 200


# Run using dev server (remove if running via uWSGI)
app.run('0.0.0.0', debug=True)
### EOF