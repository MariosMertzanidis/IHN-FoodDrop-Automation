import json
import boto3

def lambda_handler(event, context):
    
    print("Begin event:", str(event))


    matchingID = event["matchingID"]
    is_truck_driver = event["is_truck_driver"]
    feedback = event["feedback"]

    dynamodb = boto3.resource('dynamodb')
    tablePastMatching = dynamodb.Table('PastMatchings')

    past_matching = tablePastMatching.get_item(Key = {"matchingID": matchingID})
    
    if 'Item' not in past_matching:
        
        return {
        'statusCode': 404,
        'body': json.dumps('We cannot locate your matching in our system.')
        }
        
    else:
        
        matching_context = past_matching['Item']
        update_matching_context_with_feedback(matching_context, feedback, is_truck_driver)
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': "Your feedback has been received. Thanks!"
        }

     
def update_matching_context_with_feedback(matching_context, feedback, is_truck_driver):
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PastMatchings')
    
    delete_matchingID_response = table.delete_item(Key = {"matchingID": matching_context['matchingID']})
    
    if is_truck_driver == "false":
        matching_context['feedback_from_final_recipient'] = feedback
    else:
        matching_context['feedback_from_driver'] = feedback
        
    response = table.put_item(Item=matching_context)
    

    
