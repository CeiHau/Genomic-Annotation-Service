# archive_app_config.py
#
# Copyright (C) 2011-2022 Vas Vasiliadis
# University of Chicago
#
# Set app configuration options for archive utility
#
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

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

  # AWS DynamoDB table
  AWS_DYNAMODB_ANNOTATIONS_TABLE = f"{iam_username}_annotations"

   # AWS SQS queues
  AWS_SQS_WAIT_TIME = 20
  AWS_SQS_MAX_MESSAGES = 10
  AWS_SQS_REQUESTS_QUEUE_URL = f"https://sqs.us-east-1.amazonaws.com/127134666975/{iam_username}_a16_job_requests"
  
   # AWS S3 upload parameters
  AWS_S3_INPUTS_BUCKET = "gas-inputs"
  AWS_S3_RESULTS_BUCKET = "gas-results"

  # AWS SNF 
  STATE_MACHINE_ARN = f"arn:aws:states:us-east-1:127134666975:stateMachine:{iam_username}_a16_archive"

### EOF