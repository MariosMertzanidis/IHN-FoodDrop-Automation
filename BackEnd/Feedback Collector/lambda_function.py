import json
from datetime import datetime, timedelta
import boto3
import uuid

from utilities import *

# only sending to the final recipient (for now)
def lambda_handler(event, context):
    
    delete_CRON_job(event['rule_id'], event['unique_id'])

    print(event)
    
    matchingID = event['matchingID']

    #using matchingID retrieve matching context from past matchings table
    matching_context = try_retrieve_matching_context(matchingID)
    
    #if matching_context was not found, then stop
    if not matching_context:
        return {
        'statusCode': 500,
        'body': json.dumps('Cannot contact next recipient, matchingID not found in database.')
        }

    final_recipient_contact = matching_context['finalRecipientContactNumber']
    food_type = matching_context['foodDetails']['foodType']


    driver_name = matching_context['driverDetails']['name']
    driver_contact = matching_context['driverDetails']['phoneNumber']

    sms_body = f"[ACTION REQUIRED] Feedback collection: We would love to hear any feedback or suggestions you have regarding the donation of {food_type} you received earlier. Please use the following link to share your feedback with us. \n Thank you! \n https://dev.d3e2yubt3ip0ja.amplifyapp.com/?matchingID={matchingID}"
    sms_body_td = f"[ACTION REQUIRED] Feedback collection: Dear {driver_name}, we would love to hear any feedback or suggestions you have regarding the donation of {food_type} you completed using the Food Drop service earlier. Please use the following link to share your feedback with us. \n Thank you! \n https://dev.d3e2yubt3ip0ja.amplifyapp.com/?matchingID={matchingID}&td=true"

    send_feedback_SMS_using_twilio(sms_body, final_recipient_contact)
    send_feedback_SMS_using_twilio(sms_body_td, driver_contact)

    # update_listening_for_response_table(final_recipient_contact, matchingID)
    
    
def delete_CRON_job(rule_id, unique_id):

    print(f"Deleting CRON job with rule_id = {rule_id} and unique_id = {unique_id}")
    event_client = boto3.client('events')
    
    event_client.remove_targets(Rule=rule_id, Ids=[unique_id])
    event_client.delete_rule(Name=rule_id)

    lambda_clnt = boto3.client('lambda')
         
def try_retrieve_matching_context(matchingID):
    
    #check if a job with same matching is already in-progress.
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PastMatchings')
    
    
    get_matchingID_response = table.get_item(Key = {"matchingID": matchingID})
    
    #returns 0 if matching_context of the specified matchingID was not present
    if 'Item' in get_matchingID_response:
        return get_matchingID_response['Item']
    else:
        return 0
    
def update_listening_for_response_table(phoneNumber, matchingID):
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('WaitingForReply')
    
    due_responses = {
        "contactNumber": phoneNumber,
        "queue": [],
        "feedbackQueue": []
    }
    
    get_matchingID_response = table.get_item(Key = {"contactNumber": phoneNumber})
    
    #delete only if it was already present
    if 'Item' in get_matchingID_response:
        
        due_responses = get_matchingID_response['Item']
        table.delete_item(Key = {"contactNumber": phoneNumber})

        if 'feedbackQueue' not in due_responses:
            due_responses["feedbackQueue"] = []
    
    due_responses["feedbackQueue"].append(matchingID)
    
    table.put_item(Item = due_responses)
    
                
