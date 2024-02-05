import json
import boto3


def fetch_recipient(name):
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('Recipients')

    resp = table.get_item(Key = {"recipientName": name})

    print(f"response from the db was = {resp}, it's type is {type(resp)}")
    return json.dumps(resp)

def lambda_handler(event, context):
    # TODO implement
    
    print(f"event = {event}")
    name = event["queryStringParameters"]['nameString']
    
    recipient = fetch_recipient(name)
    
    return {
        'statusCode': 200,
        'headers': {
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,PUT,DELETE'
                },
        'body': recipient
    }
