import json
import boto3

def lambda_handler(event, context):
    
    print("Begin event:", str(event))

    # eventBody = json.loads(event["body"])

    matchingID = event["matchingID"]
    is_truck_driver = event["is_truck_driver"]
    # recipientID = event["recipientID"]

    dynamodb = boto3.resource('dynamodb')

    tablePastMatching = dynamodb.Table('PastMatchings')

    past_matching = tablePastMatching.get_item(Key = {"matchingID": matchingID})
    
    
    if 'Item' not in past_matching:
        
        return {
        'statusCode': 404,
        'body': json.dumps('We cannot locate your matching in our system!')
        }
    elif is_truck_driver == "false":
        
        matching_context = past_matching['Item']
        
        response = {}
        response['feedback_already_present'] = 0
        response['foodType'] = matching_context['foodDetails']['foodType']
        
        if 'feedback_from_final_recipient' in matching_context and len(matching_context['feedback_from_final_recipient']) > 0:
            response['feedback_already_present'] = 1
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(response)
        }
    elif is_truck_driver == "true":
        
        matching_context = past_matching['Item']
        
        response = {}
        response['feedback_already_present'] = 0
        response['foodType'] = matching_context['foodDetails']['foodType']
        
        if 'feedback_from_driver' in matching_context and len(matching_context['feedback_from_driver']) > 0:
            response['feedback_already_present'] = 1
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps(response)
        }
