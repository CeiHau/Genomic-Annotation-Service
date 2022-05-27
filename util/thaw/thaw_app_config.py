# thaw_app_config.py
#
# Copyright (C) 2011-2021 Vas Vasiliadis
# University of Chicago
#
# Set app configuration options for thaw utility
#
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import os

basedir = os.path.abspath(os.path.dirname(__file__))


# Get the IAM username that was stashed at launch time
try:
  with open('/home/ubuntu/.launch_user', 'r') as file:
    iam_username = file.read().replace('\n', '')
except FileNotFoundError as e:
  if ('LAUNCH_USER' in  os.environ):
    iam_username = os.environ['LAUNCH_USER']
  else:
    # Unable to set username, so exit
    print("Unable to find launch user name in local file or environment!")
    raise e

class Config(object):

  CSRF_ENABLED = True

  AWS_REGION_NAME = "us-east-1"

  AWS_ACCOUNT_ID = '127134666975'

  # AWS DynamoDB table
  AWS_DYNAMODB_ANNOTATIONS_TABLE = f"{iam_username}_annotations"

  #AWS SNS topics
  AWS_SNS_THAW_RESULTS_TOPIC = f"arn:aws:sns:us-east-1:127134666975:{iam_username}_a16_thaw_results"
  
  # AWS Glacier
  AWS_GLACIER_VAULT = "ucmpcs"

### EOF
