# GAS Framework
An enhanced web framework (based on [Flask](https://flask.palletsprojects.com/)) for use in the capstone project. Adds robust user authentication (via [Globus Auth](https://docs.globus.org/api/auth)), modular templates, and some simple styling based on [Bootstrap](https://getbootstrap.com/docs/3.3/).

Directory contents are as follows:
* `/web` - The GAS web app files
* `/ann` - Annotator files
* `/util` - Utility scripts/apps for notifications, archival, and restoration
* `/aws` - AWS user data files


## A14
I use AWS Step Functions with AWS Lambda functions. <br>
In the Lambda function, I move the S3 object to Glacier and update the DynamoDB and then delete Object from S3. <br>
In the Step Functions, I add a Wait Flow for waiting 300 seconds (5min), and then invoke the Lambda Function. <br>

Lambda function:
```
import json
import boto3
def lambda_handler(event, context):
    # TODO implement
    
    # Get information
    region_name = event['region_name']
    bucket_name = event['bukcet_name']
    key = event['s3_key_result_file']
    job_id = event['job_id']
    
    # Open a connection to the S3 service
    s3 = boto3.resource('s3', region_name = region_name)
    
    # Get the object body as a streaming body
    object = s3.Object(bucket_name, key)
    object_body = object.get()['Body']
    
    # Open a connection to the Glacier service
    glacier = boto3.client('glacier', region_name = region_name)
    response = glacier.upload_archive(vaultName='ucmpcs', body = object_body.read())
    print(response)

    #  Capture the object’s Glacier ID
    archiveId = response['archiveId']
    
    # Add Glacier object ID to job item in DynamoDB as:
    dynamodb = boto3.resource('dynamodb', region_name = region_name)
    table = dynamodb.Table('wxh_annotations')
    try:
        table.update_item(
            Key = {'job_id':job_id},
            UpdateExpression = 'SET results_file_archive_id = :val', 
            ExpressionAttributeValues = {
              ':val' : archiveId,   # Adds the name of the S3 results bucket
            }
        )
    except botocore.exceptions.ClientError as error:
        print("Update DynamoDB failed!", error)
    
    # Delte object form S3
    object.delete()
    
    return {
        'statusCode': 2001,
        'body': json.dumps('Hello from Lambda!'),
        'event':event,
        'response':response
        # 'object_body': json.dumps(object.get()['Body'])
    }
```

the Step Functions:
```
{
  "Comment": "A Hello World example of the Amazon States Language using Pass states",
  "StartAt": "Wait",
  "States": {
    "Wait": {
      "Type": "Wait",
      "Seconds": 300,
      "Next": "Lambda Invoke"
    },
    "Lambda Invoke": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "OutputPath": "$.Payload",
      "Parameters": {
        "Payload.$": "$",
        "FunctionName": "arn:aws:lambda:us-east-1:127134666975:function:wxh_a14_archive:$LATEST"
      },
      "Retry": [
        {
          "ErrorEquals": [
            "Lambda.ServiceException",
            "Lambda.AWSLambdaException",
            "Lambda.SdkClientException"
          ],
          "IntervalSeconds": 2,
          "MaxAttempts": 6,
          "BackoffRate": 2
        }
      ],
      "End": true
    }
  }
}
```
