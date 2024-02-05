import json
from datetime import datetime, timedelta
import boto3
import uuid

from utilities import *

# only sending to the final recipient (for now)
def lambda_handler(event, context):
    
    print("start")
    delete_CRON_job(event['rule_id'], event['unique_id'], event['rule_arn'])
    
    matchingID = event['matchingID']
    phone_number = event['phone_number']
    index = event['index']

    print("before the check")
    print(f"phone number = {phone_number}, matchingID = {matchingID}, index = {index}, and is_waiting_for_reply = {is_waiting_for_reply(phone_number, matchingID)}")
    if is_waiting_for_reply(matchingID, index) == True:
        print("sending sms now")
        send_reminder_sms(phone_number)

def send_reminder_sms(phone_number):

    sms_body = f"[Reminder to reply]: Please respond within the next {get_maximum_minutes_to_respond()-5} mins using the link above to accept or reject the donation. No response would be considered as a NO. \n Thank you!"

    send_SMS_using_twilio(sms_body, phone_number)
  
    
def delete_CRON_job(rule_id, unique_id, rule_arn):

    print(f"Deleting CRON job with rule_id = {rule_id} and unique_id = {unique_id}")
    event_client = boto3.client('events')
    lambda_clnt = boto3.client('lambda')

    # rslt = lambda_clnt.add_permission(FunctionName="arn:aws:lambda:us-east-2:223196649183:function:RemindToReply",
    #                                   StatementId=unique_id,
    #                                   Action='lambda:InvokeFunction',
    #                                   Principal='events.amazonaws.com',
    #                                   SourceArn=rule_arn)
    
    event_client.remove_targets(Rule=rule_id, Ids=[unique_id])
    event_client.delete_rule(Name=rule_id)

    lambda_clnt = boto3.client('lambda')
    
    lambda_clnt.remove_permission(
        FunctionName="arn:aws:lambda:us-east-2:215600070315:function:RemindToReply",
        StatementId=unique_id
    )

def is_waiting_for_reply(matchingID, index):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')
    
    get_matchingID_response = table.get_item(Key = {"matchingID": matchingID})
    
    #delete only if it was already present
    if 'Item' in get_matchingID_response:
        
        print("matching Context Retrieved")
        current_index = get_matchingID_response['Item']['index']

        print(f"{current_index} and {index}")
        return str(current_index) == str(index)

    else:
        print("matching Context Retrieved")
        return False
                
