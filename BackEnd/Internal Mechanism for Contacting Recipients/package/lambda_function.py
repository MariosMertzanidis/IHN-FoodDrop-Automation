import json
from datetime import datetime, timedelta
import boto3
import uuid
import pytz


from utilities import * 

indi_tz = pytz.timezone("America/Indianapolis")

def lambda_handler(event, context):

    print("Begin event: ", str(event))

    delete_CRON_job(event['rule_id'], event['unique_id'])

    matchingID = event['matchingID']
    index = int(event['index'])

    #using matchingID retrieve matching context
    matching_context = try_retrieve_matching_context(matchingID)

    #if matching_context was not found, then stop
    if not matching_context:
        return {
        'statusCode': 500,
        'body': json.dumps('Cannot contact next recipient, matchingID not found in database.')
        }

    if (int(matching_context["index"])+1 != index) and (index !=0):
        return {
        'statusCode': 200,
        'body': json.dumps('Stopping computation since we got an invalid index.')
        }
    
    startTime = datetime.strptime(matching_context["requestStartTime"], "%m-%d-%Y:%H-%M")

    startTime_aware = indi_tz.localize(startTime)

    time_now = datetime.now(indi_tz)

    time_window = timedelta(minutes = 60)

    #time_for_notification = timedelta(minutes = 30)

    #if time_now > startTime_aware + time_for_notification:
    #    notify_driver_wait(matching_context["driverDetails"]["phoneNumber"])

    #[Edge case: the last recipient case]
    if index >= len(matching_context['responseStatus']) or time_now > startTime_aware + time_window:
        print("Matching Ended")
        print(matching_context)

        if matching_context['responseStatus'][index-1] == "awaitingResponse":
            matching_context['responseStatus'][index-1] = "didNotRespond-didNotOpenLink"
        elif matching_context['responseStatus'][index - 1] == "OpenedLink":
            matching_context['responseStatus'][index - 1] = "didNotRespond-OpenedLink"

        print(matching_context)

        if matching_context['responseStatus'][index-1] == "didNotRespond-didNotOpenLink" or matching_context['responseStatus'][index-1] == "didNotRespond-OpenedLink" or matching_context['responseStatus'][index-1] == "no":
            print(matching_context)
            reply_to_driver_with_a_negative(matching_context['driverDetails']['phoneNumber'])
            matching_context['finalRecipient'] = "Nobody Accepted"
            update_Past_matchings_table(matching_context)
            delete_matching_context(matchingID)

    # check if previous index exists and if so has responded with a "no" and this recipient hasn't been notified
    # continue only if that is the case

    elif matching_context['responseStatus'][index] == "notYetContacted":

        print("the current recipient hasn't been contacted")

        if index >= 1 and matching_context['responseStatus'][index - 1] == "awaitingResponse":
            matching_context['responseStatus'][index - 1] = "didNotRespond-didNotOpenLink"
        elif index >= 1 and matching_context['responseStatus'][index - 1] == "OpenedLink":
            matching_context['responseStatus'][index - 1] = "didNotRespond-OpenedLink"

            print(f"the recipient index {index} didn't respond")

        if index == 0 or matching_context['responseStatus'][index - 1] == "no" or matching_context['responseStatus'][index - 1] == "didNotRespond-OpenedLink" or matching_context['responseStatus'][index - 1] == "didNotRespond-didNotOpenLink":

            print(f"inside the contact function")
            #update the matching context
            matching_context['responseStatus'][index] = "awaitingResponse"
            matching_context['index'] = str(index)

            print("updating matching context")
            update_matching_context(matching_context)
            print("matching context updated")

            #schedule a cron job for the next recipient
            print("scheduling cron job")
            schedule_cron_job(matchingID, index + 1)
            print("cron job scheduled")

            #notify the recipient via SMS
            recipient_phone_number = matching_context['recipientsOrder'][index]['contactNumber']
            recipient_key = matching_context['recipientsOrder'][index]['Key']
            sms_body = get_sms_body(matching_context, index, recipient_key)

            print(f"sms body to be sent to {recipient_phone_number} is {sms_body}")

            print(f"Updating listening for response table")
            send_SMS_using_twilio(sms_body, recipient_phone_number)
            schedule_reminder_to_reply_job(recipient_phone_number, matchingID, index)
    else:

        return {
            'statusCode': 200,
            'body': json.dumps('Stopping computation since recipient already contacted.')
        }

def notify_driver_wait(phone):
    sms_body = "Thank you for waiting. We are still trying to find a food bank for your donation."
    send_SMS_using_twilio(sms_body, phone)

def delete_CRON_job(rule_id, unique_id):

    print(f"Deleting CRON job with rule_id = {rule_id} and unique_id = {unique_id}")
    event_client = boto3.client('events')

    event_client.remove_targets(Rule=rule_id, Ids=[unique_id])
    event_client.delete_rule(Name=rule_id)

    lambda_clnt = boto3.client('lambda')

    lambda_clnt.remove_permission(
        FunctionName="arn:aws:lambda:us-east-2:215600070315:function:ContactNextRecipient",
        StatementId=unique_id
    )

def update_Past_matchings_table(matching_context):

    requestEndTime = datetime.now(indi_tz).strftime('%m-%d-%Y:%H-%M')
    requestStartTime = matching_context['requestStartTime']

    matching_context['totalProcessingTime'] = compute_total_processing_time(requestStartTime, requestEndTime)
    matching_context['requestEndTime'] = requestEndTime

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PastMatchings')

    table.put_item(Item=matching_context)

def schedule_cron_job(matchingID, index):

    rule_id = "event_ContactNextRecipient_" + str(uuid.uuid4())
    unique_id = str(uuid.uuid4())

    time = datetime.utcnow() + timedelta(minutes = get_maximum_minutes_to_respond())

    #rule for scheduling a cron job after the specified time
    event_client = boto3.client('events')
    rule = event_client.put_rule(Name=rule_id,
                             ScheduleExpression=f"cron({time.minute} {time.hour} {time.day} {time.month} ? {time.year})",
                             State='ENABLED')


    rslt = event_client.put_targets(Rule=rule_id,
                                    Targets=[
                                        {
                                            'Arn': "arn:aws:lambda:us-east-2:215600070315:function:ContactNextRecipient",
                                            'Id': unique_id,
                                            'Input': json.dumps({"rule_id": rule_id, "unique_id": unique_id, "rule_arn" : rule["RuleArn"], "matchingID" : matchingID, "index" : index})
                                        }
                                            ])


    #creating a 'lambda' client
    lambda_clnt = boto3.client('lambda')
    #Now, we add the permission
    rslt = lambda_clnt.add_permission(FunctionName="arn:aws:lambda:us-east-2:215600070315:function:ContactNextRecipient",
                                      StatementId=unique_id,
                                      Action='lambda:InvokeFunction',
                                      Principal='events.amazonaws.com',
                                      SourceArn=rule["RuleArn"])

    print(f"Scheduled CRON job with ruleID = {rule_id} and unique_id = {unique_id}")


def schedule_reminder_to_reply_job(recipient_phone_number, matchingID, index):
    rule_id = "event_RemindToReply_" + str(uuid.uuid4())
    unique_id = str(uuid.uuid4())

    time = datetime.utcnow() + timedelta(minutes = 5)

    #rule for scheduling a cron job after the specified time
    event_client = boto3.client('events')
    rule = event_client.put_rule(Name=rule_id,
                             ScheduleExpression=f"cron({time.minute} {time.hour} {time.day} {time.month} ? {time.year})",
                             State='ENABLED')


    rslt = event_client.put_targets(Rule=rule_id,
                                    Targets=[
                                        {
                                            'Arn': "arn:aws:lambda:us-east-2:215600070315:function:RemindToReply",
                                            'Id': unique_id,
                                            'Input': json.dumps({"rule_id": rule_id, "unique_id": unique_id, "rule_arn" : rule["RuleArn"], "matchingID" : matchingID, "phone_number" : recipient_phone_number, "index": index})
                                        }
                                            ])


    #creating a 'lambda' client
    lambda_clnt = boto3.client('lambda')
    #Now, we add the permission
    rslt = lambda_clnt.add_permission(FunctionName="arn:aws:lambda:us-east-2:215600070315:function:RemindToReply",
                                      StatementId=unique_id,
                                      Action='lambda:InvokeFunction',
                                      Principal='events.amazonaws.com',
                                      SourceArn=rule["RuleArn"])

    print(f"Scheduled CRON job for reminder with ruleID = {rule_id} and unique_id = {unique_id}")

def get_sms_body(matching_context, recipient, recipient_key):

    matchingID = matching_context["matchingID"]

    allowed_time_to_respond = get_maximum_minutes_to_respond()

    sms_body = f"[ACTION REQUIRED] IHN Food Drop Delivery Notification: A donation is available. For more information visit: https://dev8694.dz55j4kxqm9hg.amplifyapp.com?matchingID={matchingID}&index={recipient}&recipientID={recipient_key}. Accept or reject the donation through the above link within the next {allowed_time_to_respond} minutes."

    return sms_body


def try_retrieve_matching_context(matchingID):

    #check if a job with same matching is already in-progress.
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')


    get_matchingID_response = table.get_item(Key = {"matchingID": matchingID})

    #returns 0 if matching_context of the specified matchingID was not present
    if 'Item' in get_matchingID_response:
        return get_matchingID_response['Item']
    else:
        return 0

def delete_matching_context(matchingID):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')

    get_matchingID_response = table.get_item(Key = {"matchingID": matchingID})

    #delete only if it was already present
    if 'Item' in get_matchingID_response:
        delete_matchingID_response = table.delete_item(Key = {"matchingID": matchingID})


def update_matching_context(matching_context):

    delete_matching_context(matching_context['matchingID'])

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')

    response = table.put_item(Item=matching_context)

