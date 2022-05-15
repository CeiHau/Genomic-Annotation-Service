# notify.py
#
# Notify users of job completion
#
# Copyright (C) 2011-2021 Vas Vasiliadis
# University of Chicago
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import boto3
import time
import os
import sys
import json
import psycopg2
from botocore.exceptions import ClientError
import botocore

# Import utility helpers
sys.path.insert(1, os.path.realpath(os.path.pardir))
import helpers


# Get configuration
from configparser import ConfigParser
config = ConfigParser(os.environ)
config.read('notify_config.ini')

region_name = config['aws']['AwsRegionName']
queue_url = config['sqs']['URL']

'''Capstone - Exercise 3(d)
Reads result messages from SQS and sends notification emails.
'''
def handle_results_queue(sqs=None):
  # Read a message from the queue
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
  # print(response)
  if 'Messages' in response:
    print("begin")
    Message_body = json.loads(response['Messages'][0]['Body'])
    print()
    receipt_handle = response['Messages'][0]['ReceiptHandle']
    print()
    Message = json.loads(Message_body['Message'])

    compelete_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(Message['complete_time']))
    subject = "Results available for job " + Message['job_id']
    body =  "Your annotation job completed at " + compelete_time + ". " 
    body += "Click here to view job details and results: " + Message['link']
    recipients = Message['recipients']

    # Process message
    send_response = helpers.send_email_ses(recipients = recipients, sender=None, subject = subject, body = body)
    print(send_response)

    # Delete message
    sqs.delete_message(
      QueueUrl =queue_url,
      ReceiptHandle=receipt_handle
    )


  pass

if __name__ == '__main__':
  
  # Get handles to resources; and create resources if they don't exist

  # Poll queue for new results and process them
  sqs = boto3.client('sqs', region_name = region_name, config = botocore.client.Config(signature_version = 's3v4'))

  while True:
    handle_results_queue(sqs=sqs)

### EOF
