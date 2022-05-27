# thaw_app.py
#
# Thaws upgraded (premium) user data
#
# Copyright (C) 2011-2021 Vas Vasiliadis
# University of Chicago
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import json, requests
import os

import boto3, botocore
from flask import Flask, request, session, jsonify

app = Flask(__name__)
environment = 'thaw_app_config.Config'
app.config.from_object(environment)
app.url_map.strict_slashes = False

#  Get configuration
region_name = app.config['AWS_REGION_NAME']
table_name = app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE']
vault_name = app.config['AWS_GLACIER_VAULT']
accoud_id = app.config['AWS_ACCOUNT_ID']
sns_topic = app.config['AWS_SNS_THAW_RESULTS_TOPIC']

@app.route('/', methods=['GET'])
def home():
  return (f"This is the Thaw utility: POST requests to /thaw.")
  
@app.route('/thaw', methods=['POST'])
def thaw_premium_user_data():
  # Get message 
  message =  json.loads(request.data.decode())
  if request.headers['X-Amz-Sns-Message-Type'] == 'SubscriptionConfirmation':
    # Confirm SNS topic subscription confirmation
    print('----------------confirm----------------')
    response = requests.get(url = message['SubscribeURL'])
  else:
    # Open a connection to the Glacier service
    client = boto3.client('glacier', region_name = region_name)
    for archive_info in message['archive_info_lst']:
      archive_id = archive_info['archive_id']
      job_id = archive_info['job_id']
      print('\n############ For archive id = ',archive_id)
      try:
        print('Try Expedited retrieval...')
        response = client.initiate_job(
          vaultName = vault_name,
          jobParameters = {
            'Type': 'archive-retrieval',
            'Description': job_id,
            'ArchiveId':archive_id,
            'SNSTopic':sns_topic,
            'Tier':'Expedited'
          }
        )
        print('Expedited retrieval request succeed!')
        print('The job id is ', response['job_id'])
        print()
      except client.exceptions.InsufficientCapacityException as error:
        try:
          print('Expedited retrieval request fails')
          print('Try Standard retrieval...')
          response = client.initiate_job(
            vaultName = vault_name,
            jobParameters = {
              'Type': 'archive-retrieval',
              'Description': job_id,
              'ArchiveId': archive_id,
              'SNSTopic': sns_topic,
              'Tier': 'Standard'
            }
          )
          print('Standard retrieval request succeed')
          print('The job id is ', response['job_id'])
          print()
        except client.exceptions.InsufficientCapacityException as error:
          response_body = {
            "code": 500,
            "data":{
              "status":"unable to initiate Glacier job",
              "message":error
            }
          }
          return response_body, 500
      print(response)

      # Open a connection to the DybamoDB service
      dynamodb = boto3.resource('dynamodb', region_name = region_name)
      table = dynamodb.Table(table_name)

      # Update the archive status in dynamoDB
      try:
        table.update_item(
          Key = {'job_id':job_id},
          UpdateExpression = 'SET archive_status = :val', 
          ExpressionAttributeValues = {':val' : 'InProgress'}
        )
      except botocore.exceptions.ClientError as error:
        print("Update DynamoDB failed!", error)


  return jsonify({
    "code": 200, 
    "message": "Thaw the Glacier object."
  }), 200
    

app.run('0.0.0.0', debug=True, port = 4433)
