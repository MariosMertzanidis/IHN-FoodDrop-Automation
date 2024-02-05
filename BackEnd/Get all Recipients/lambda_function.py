import json
import boto3


def fetch_recipients():
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('Recipients')

    resp = table.scan()['Items']

    return json.dumps(resp)

def lambda_handler(event, context):
    # TODO implement
    
    print(event)
    
    
    recipients = fetch_recipients()
    
    return {
        'statusCode': 200,
        'headers': {
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,PUT,DELETE'
                },
        'body': recipients
    }

