import json
import boto3


def delete_recipient(recipientName):
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('Recipients')

    return table.delete_item(Key = {"recipientName": recipientName})

def lambda_handler(event, context):
    # TODO implement
    
    recipientName = event['recipientName']
    
    response = delete_recipient(recipientName)
    

    return {
        'statusCode': 200,
        'body': "Item Deleted Successfully"
    }