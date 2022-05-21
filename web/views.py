# views.py
#
# Copyright (C) 2011-2022 Vas Vasiliadis
# University of Chicago
#
# Application logic for the GAS
#
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import uuid
import time
import json
from datetime import datetime

import boto3
from botocore.client import Config
from boto3.dynamodb.conditions import Key, Attr 
from botocore.exceptions import ClientError

from flask import (abort, flash, redirect, render_template, 
  request, session, url_for)

from app import app, db
from decorators import authenticated, is_premium

from auth import get_profile

"""Start annotation request
Create the required AWS S3 policy document and render a form for
uploading an annotation input file using the policy document

Note: You are welcome to use this code instead of your own
but you can replace the code below with your own if you prefer.
"""
@app.route('/annotate', methods=['GET'])
@authenticated
def annotate():
  # Open a connection to the S3 service
  s3 = boto3.client('s3', 
    region_name=app.config['AWS_REGION_NAME'], 
    config=Config(signature_version='s3v4'))

  bucket_name = app.config['AWS_S3_INPUTS_BUCKET']
  user_id = session['primary_identity']

  # Generate unique ID to be used as S3 key (name)
  key_name = app.config['AWS_S3_KEY_PREFIX'] + user_id + '/' + \
    str(uuid.uuid4()) + '~${filename}'

  # Create the redirect URL
  redirect_url = str(request.url) + "/job"

  # Define policy conditions
  encryption = app.config['AWS_S3_ENCRYPTION']
  acl = app.config['AWS_S3_ACL']
  fields = {
    "success_action_redirect": redirect_url,
    "x-amz-server-side-encryption": encryption,
    "acl": acl
  }
  conditions = [
    ["starts-with", "$success_action_redirect", redirect_url],
    {"x-amz-server-side-encryption": encryption},
    {"acl": acl}
  ]

  # Generate the presigned POST call
  try:
    presigned_post = s3.generate_presigned_post(
      Bucket=bucket_name, 
      Key=key_name,
      Fields=fields,
      Conditions=conditions,
      ExpiresIn=app.config['AWS_SIGNED_REQUEST_EXPIRATION'])
  except ClientError as e:
    app.logger.error(f'Unable to generate presigned URL for upload: {e}')
    return abort(500)

  # Render the upload form which will parse/submit the presigned POST
  return render_template('annotate.html',
    s3_post=presigned_post,
    role=session['role'])


"""Fires off an annotation job
Accepts the S3 redirect GET request, parses it to extract 
required info, saves a job item to the database, and then
publishes a notification for the annotator service.

Note: Update/replace the code below with your own from previous
homework assignments
"""
@app.route('/annotate/job', methods=['GET'])
@authenticated
def create_annotation_job_request():

  region = app.config['AWS_REGION_NAME']

  # Parse redirect URL query parameters for S3 object info
  bucket_name = request.args.get('bucket')
  s3_key = request.args.get('key')

  # Extract the job ID from the S3 key
  index1 = s3_key.find('/')
  index2 = s3_key.find('~')
  index3 = s3_key[index1+1 : index2].find('/') + index1 + 1
  job_id = s3_key[index3+1 : index2]
  file_name = s3_key[index2+1 : ]
  user_id = session.get('primary_identity')
  submit_time = int(time.time())

  # Persist job to database
  data = { "job_id": job_id,
          "user_id": user_id,
          "input_file_name": file_name,
          "s3_inputs_bucket": bucket_name,
          "s3_key_input_file": s3_key,
          "submit_time": submit_time,
          "job_status": "PENDING"
        }
  # ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/dynamodb.html -> Creating a new item
  dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'], config=Config(signature_version='s3v4'))
  table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
  table = dynamodb.Table(table_name)

  #Erro handling: adding item to  DynamoDB
  try:
    table.put_item(Item = data)
  except botocore.exceptions.ClientError as error:
    response_body = {
      "code": 500,
      "data":{
        "status":"error",
        "message":error
      }
    }
    return response_body, 500

  # Send message to request queue
  # Move your code here...
  # ref: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sns.html#SNS.Client.publish
  # Open a connection to the S3 service
  client = boto3.client('sns', 
  region_name=app.config['AWS_REGION_NAME'], 
  config=Config(signature_version='s3v4'))
  profile = get_profile(identity_id = user_id)
  data['email'] = profile.email
  tpic_arn = app.config['AWS_SNS_JOB_REQUEST_TOPIC']
  response = client.publish(
    TopicArn = tpic_arn,
    Message = json.dumps(data)
  )

  return render_template('annotate_confirm.html', job_id=job_id)


"""List all annotations for the user
"""
@app.route('/annotations', methods=['GET'])
@authenticated
def annotations_list():
  # Open a connection to the DynamoDB service
  dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'], config=Config(signature_version='s3v4'))
  table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
  table = dynamodb.Table(table_name)

  # Query the table
  # ref: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/getting-started-step-7.html
  user_id = session['primary_identity']
  response = table.query(
    IndexName = 'user_id_index',
    KeyConditionExpression = Key('user_id').eq(user_id)
    )
    
  # Get list of annotations to display
  ann_lst = []
  for item in response['Items']:
    ann = {}
    ann['job_id'] = item['job_id']
    submit_time = item['submit_time']
    ann['input_file_name'] = item['input_file_name']
    ann['status'] = item['job_status']
    ann['submit_time'] = time.strftime('%Y-%m-%d %H:%M', time.localtime(submit_time))
    ann['redirect_url']  = request.url + '/' + ann['job_id']
    ann_lst.append(ann)
  return render_template('annotations.html', annotations=ann_lst)


"""Display details of a specific annotation job
"""
@app.route('/annotations/<id>', methods=['GET'])
@authenticated
def annotation_details(id):
  # Open a connection to the DynamoDB service
  dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'], config=Config(signature_version='s3v4'))
  table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
  table = dynamodb.Table(table_name)

  # Retrieve job information from the annotations database by id
  # ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/dynamodb.html
  response = table.get_item(
    Key={
        'job_id': id,
    }
  )
  item = response['Item']
  print(item)
  # if 'results_file_archive_id' in item:
  #   print("moved to archive")
  # else:
  #   print("keep the same")
  user_id = session['primary_identity']
  if user_id != item['user_id']:
    abort(403)
  # Open a connection to the S3 service
  s3_client = boto3.client('s3', region_name=app.config['AWS_REGION_NAME'], config=Config(signature_version='s3v4'))
  bucket_name = app.config['AWS_S3_RESULTS_BUCKET']
  
  vcf_key_name = app.config['AWS_S3_KEY_PREFIX'] + user_id + '/' + item['job_id'] + '~'  + item['input_file_name'][:-3] + "annot.vcf"
  # Generate presigned URL for the S3 object
  # ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
  try:
    response_vcf = s3_client.generate_presigned_url(
      'get_object',
      Params={'Bucket': bucket_name, 'Key': vcf_key_name},
      ExpiresIn=60)
  except ClientError as e:
    app.logger.error(f'Unable to generate presigned URL for download: {e}')
    return abort(500)
  try:
    input_file_link = s3_client.generate_presigned_url(
      'get_object',
      Params={'Bucket': app.config['AWS_S3_INPUTS_BUCKET'],'Key': item['s3_key_input_file']},
      ExpiresIn=60)
  except ClientError as e:
    app.logger.error(f'Unable to generate presigned URL for download: {e}')
    return abort(500)


  item['submit_time'] = time.strftime('%Y-%m-%d %H:%M', time.localtime(item['submit_time']))
  item['input_file_link'] = input_file_link
  if item['job_status'] == 'COMPLETED':
    item['complete_time'] = time.strftime('%Y-%m-%d %H:%M', time.localtime(item['complete_time']))
    item['response_vcf'] = response_vcf                                             
    item['response_log'] = request.url + '/' + 'log'

  return render_template('annotation.html', annotation = item)

"""Display the log file contents for an annotation job
"""
@app.route('/annotations/<id>/log', methods=['GET'])
@authenticated
def annotation_log(id):
  # Open a connection to the DynamoDB service
  dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'], config=Config(signature_version='s3v4'))
  table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
  table = dynamodb.Table(table_name)

  # Retrieve job information from the annotations database by id
  # ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/dynamodb.html
  response = table.get_item(
    Key={
        'job_id': id,
    }
  )
  item = response['Item']

  # Open a connection to the S3 service
  s3_client = boto3.client('s3', region_name=app.config['AWS_REGION_NAME'], config=Config(signature_version='s3v4'))
  bucket_name = app.config['AWS_S3_RESULTS_BUCKET']
  user_id = session['primary_identity']
  log_key_name = app.config['AWS_S3_KEY_PREFIX'] + user_id + '/' + item['job_id'] + '~' + item['input_file_name'] + ".count.log"
  
  obj = s3_client.get_object(Bucket = bucket_name, Key = log_key_name)
  file_body = obj['Body'].read() 
  contents = file_body.decode('utf-8')
  return render_template('view_log.html', job_id = id, log_file = contents) 

"""Subscription management handler
"""
import stripe
from auth import update_profile

@app.route('/subscribe', methods=['GET', 'POST'])
@authenticated
def subscribe():
  if (request.method == 'GET'):
    # Display form to get subscriber credit card info
    pass
    
  elif (request.method == 'POST'):
    # Process the subscription request

    # Create a customer on Stripe

    # Subscribe customer to pricing plan

    # Update user role in accounts database

    # Update role in the session

    # Request restoration of the user's data from Glacier
    # ...add code here to initiate restoration of archived user data
    # ...and make sure you handle files not yet archived!

    # Display confirmation page
    pass


"""Set premium_user role
"""
@app.route('/make-me-premium', methods=['GET'])
@authenticated
def make_me_premium():
  # Hacky way to set the user's role to a premium user; simplifies testing
  update_profile(
    identity_id=session['primary_identity'],
    role="premium_user"
  )
  return redirect(url_for('profile'))


"""Reset subscription
"""
@app.route('/unsubscribe', methods=['GET'])
@authenticated
def unsubscribe():
  # Hacky way to reset the user's role to a free user; simplifies testing
  update_profile(
    identity_id=session['primary_identity'],
    role="free_user"
  )
  return redirect(url_for('profile'))


"""DO NOT CHANGE CODE BELOW THIS LINE
*******************************************************************************
"""

"""Home page
"""
@app.route('/', methods=['GET'])
def home():
  return render_template('home.html')

"""Login page; send user to Globus Auth
"""
@app.route('/login', methods=['GET'])
def login():
  app.logger.info(f"Login attempted from IP {request.remote_addr}")
  # If user requested a specific page, save it session for redirect after auth
  if (request.args.get('next')):
    session['next'] = request.args.get('next')
  return redirect(url_for('authcallback'))

"""404 error handler
"""
@app.errorhandler(404)
def page_not_found(e):
  return render_template('error.html', 
    title='Page not found', alert_level='warning',
    message="The page you tried to reach does not exist. \
      Please check the URL and try again."
    ), 404

"""403 error handler
"""
@app.errorhandler(403)
def forbidden(e):
  return render_template('error.html',
    title='Not authorized', alert_level='danger',
    message="You are not authorized to access this page. \
      If you think you deserve to be granted access, please contact the \
      supreme leader of the mutating genome revolutionary party."
    ), 403

"""405 error handler
"""
@app.errorhandler(405)
def not_allowed(e):
  return render_template('error.html',
    title='Not allowed', alert_level='warning',
    message="You attempted an operation that's not allowed; \
      get your act together, hacker!"
    ), 405

"""500 error handler
"""
@app.errorhandler(500)
def internal_error(error):
  return render_template('error.html',
    title='Server error', alert_level='danger',
    message="The server encountered an error and could \
      not process your request."
    ), 500

### EOF