import json
import boto3


def lambda_handler(event, context):
    # TODO implement
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('InProgressMatchingContext')
    
    resp = table.scan()['Items']
    
    
    return {
        'statusCode': 200,
        'body': resp
    }