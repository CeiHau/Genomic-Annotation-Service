# run.py
#
# Copyright (C) 2011-2019 Vas Vasiliadis
# University of Chicago
#
# Wrapper script for running AnnTools
#
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import sys
import time
import driver
import boto3
import botocore
import os
import json
from botocore.client import Config

# sys.path.insert(1, "/home/ubuntu/gas/web")
# from auth import get_profile
"""A rudimentary timer for coarse-grained profiling
"""
class Timer(object):
  def __init__(self, verbose=True):
    self.verbose = verbose

  def __enter__(self):
    self.start = time.time()
    return self

  def __exit__(self, *args):
    self.end = time.time()
    self.secs = self.end - self.start
    if self.verbose:
      print(f"Approximate runtime: {self.secs:.2f} seconds")

# Get configuration
from configparser import ConfigParser
config = ConfigParser(os.environ)
config.read('ann_config.ini')
region_name = config['aws']['AwsRegionName']
table_name = config['dynamodb']['TABLENAME']
tpic_arn = config['sns']['arn']

if __name__ == '__main__':
    # Call the AnnTools pipeline
    if len(sys.argv) > 1:
        with Timer():
            driver.run(sys.argv[1], 'vcf')
        complete_time = int(time.time())
        job_id = sys.argv[2]
        user_id = sys.argv[3]
        email = sys.argv[4]

        s3 = boto3.client('s3',region_name=region_name, config = botocore.client.Config(signature_version = 's3v4'))
        folder_name = os.path.dirname(sys.argv[1])

        # ref: https://boto3.amazonaws.com/v1/documentation/api/1.9.42/guide/s3-example-creating-buckets.html
        # 1. Upload the results file to S3 results bucket
        result_file = os.path.basename(sys.argv[1])[:-4] + ".annot.vcf"
        s3_key_result_file  =  'wxh/' + user_id + '/' + job_id + '~' + result_file
        s3.upload_file(folder_name+ "/" + result_file, 'gas-results', 'wxh/' + user_id + '/' + job_id + '~' + result_file)

        # 2. Upload the log file to S3 results bucket
        log_file =  os.path.basename(sys.argv[1]) + ".count.log"
        s3_key_log_file = 'wxh/' + user_id + '/' + job_id + '~' + log_file
        s3.upload_file(folder_name+ "/" + log_file, 'gas-results', 'wxh/' + user_id + '/' + job_id + '~' + log_file)

        # 3. Clean up (delete) local job files
        os.remove(folder_name+ "/" + result_file)
        os.remove(folder_name+ "/" + log_file)

        # Updates the job item in DynamoDB table 
        dynamodb = boto3.resource('dynamodb', region_name = region_name, config = botocore.client.Config(signature_version = 's3v4'))
        table = dynamodb.Table(table_name)
        try:
          table.update_item(
            Key = {'job_id':job_id},
            UpdateExpression = 'SET s3_results_bucket = :val, s3_key_result_file = :val1, s3_key_log_file = :val2, complete_time =:val3, job_status = :val4', 
            ExpressionAttributeValues = {
              ':val' : 'gas-results',   # Adds the name of the S3 results bucket
              ':val1': s3_key_result_file,  # Adds the name of the S3 key for the results file
              ':val2': s3_key_log_file, # Adds the name of the S3 key for the log file
              ':val3': complete_time, # Adds the completion time (use the current system time)
              ':val4': "COMPLETED"  # Updates the “job_status” key to “COMPLETED”
            }
          )
        except botocore.exceptions.ClientError as error:
          print("Update DynamoDB failed!", error)

        # Publishes a notification to the SNS when job is completed
        # Open a connection to the SNS service
        client = boto3.client('sns', region_name = region_name, config=Config(signature_version='s3v4'))
        try:
          response = client.publish(
          TopicArn = tpic_arn,
          Message = json.dumps({
            "user_id": user_id,
            "job_id":  job_id ,
            "s3_key_result_file": s3_key_result_file,
            "recipients":email,
            "complete_time": complete_time,
            "link": "https://wxh-a14-web.ucmpcs.org:4433/annotations" + '/' + job_id
          })
          )
        except botocore.exceptions.ClientError as error:
          print("Publish notification failed!", errro)
       

    else:
        print("A valid .vcf file must be provided as input to this program.")

### EOF

