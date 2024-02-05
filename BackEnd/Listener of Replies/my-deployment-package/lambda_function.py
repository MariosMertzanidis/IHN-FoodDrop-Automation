from datetime import datetime, timedelta
import boto3
import uuid
import json
from utilities import *
import pytz

indi_tz = pytz.timezone("America/Indianapolis")

IHN_contact = "<Insert Number Here>"

def lambda_handler(event, context):

    print("Begin event: ", str(event))

    matchingID = event["matchingID"]
    recip_key = event["recipientID"]
    reply = event["reply"]

    
    #Check if we were listening for a response from this contact number.
    matching_context = get_matching_context_for_response(matchingID, recip_key, reply)

    print("Matching Context: ", matching_context)

    if matching_context == 0:
       
        return json.dumps({"Type": "Error_Order",
            "Error": "Sorry, as per our system, no responses were being awaited from your end for this order."})
        
    
    elif matching_context == 1:
                
        return json.dumps({"Type": "Added_Queue",
            "Error": "Sorry, as per our system, your time window was over. You have been added back to the queue."})
        
    elif matching_context == 2:
        return json.dumps({"Type": "Reject",
            "Msg": "Thank you for response"})
        
    elif matching_context == 3:
        return json.dumps({"Type": "Already_in_queue",
            "Msg": "You are already in the queue"})
        

    index = matching_context["index"]
    phone_number = matching_context["recipientsOrder"][int(index)]["contactNumber"]

    print(f"Got a YES response from {phone_number} for the request with matchingID = {matchingID}.")


    #delete matching context
    delete_matching_context(matchingID)

    #exchange contacts
    index = matching_context['index']
    response_string_recipient = exchange_contacts_driver_recipient(matching_context, index, phone_number)

    #put matching context in past matchings table
    matching_context['finalRecipient'] = matching_context['recipientsOrder'][int(index)]['recipientName']
    matching_context['finalRecipientContactNumber'] = matching_context['recipientsOrder'][int(index)]['contactNumber']
    matching_context['responseStatus'][int(index)] = "yes"
    update_Past_matchings_table(matching_context)

    #Update the recipients table with the new latest donation date
    update_recipients_table(matching_context['finalRecipient'])

    schedule_feedback_collection_job(matchingID)

    print("Over and Out!")

    return response_string_recipient

    

def add_recip_to_queue(matchingID, recipientsOrder, responseStatus, recipientIndex, actualIndex):
    print("In update queue: ", str((matchingID, recipientsOrder, responseStatus)))
    print("Updating to opened link")
    responseStatus.append("notYetContacted")
    recipient = recipientsOrder[recipientIndex].copy()
    recipient["reAddBool"] = "True"
    recipientsOrder.insert(actualIndex+1, recipient)
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')
    response = table.update_item(
        Key = {"matchingID": matchingID},
        UpdateExpression="set #attr1 = :updatedResponseStatus, #attr2 = :updatedRecipientsOrder",
        ExpressionAttributeValues={ ':updatedResponseStatus': responseStatus, ':updatedRecipientsOrder': recipientsOrder},
        ExpressionAttributeNames={'#attr1': "responseStatus", '#attr2': "recipientsOrder"},
        ReturnValues="UPDATED_NEW"

    )
    print("Update:", response)

def update_recipients_table(recipient_name):

    print("Start Updating Recipient Table")

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Recipients')

    print(f"Recipient's name who accepted the matching request = {recipient_name}")

    get_recipient_response = table.get_item(Key = {"recipientName": recipient_name})

    #delete only if it was already present
    if 'Item' in get_recipient_response:
        delete_recipient_response = table.delete_item(Key = {"recipientName": recipient_name})

        recipient = get_recipient_response['Item']

        # utc date today!
        recipient['lastDonationDate'] = datetime.today().strftime("%m/%d/%Y")

        print(f"Updating the last donation date of recipient: {recipient_name} to {recipient['lastDonationDate']}")

        response = table.put_item(Item=recipient)

    print("Finished Updating Recipient Table")





def delete_matching_context(matchingID):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')

    print("Start Deleting Matching Context")

    get_matchingID_response = table.get_item(Key = {"matchingID": matchingID})

    #delete only if it was already present
    if 'Item' in get_matchingID_response:
        delete_matchingID_response = table.delete_item(Key = {"matchingID": matchingID})

def update_matching_context(matching_context):

    delete_matching_context(matching_context['matchingID'])

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')

    response = table.put_item(Item=matching_context)


def schedule_feedback_collection_job(matchingID):

    event_client = boto3.client('events')

    time = datetime.utcnow() + timedelta(hours = 24)
    rule_id = "event_CollectFeedback_" + str(uuid.uuid4())
    unique_id = str(uuid.uuid4())

    #create a rule to start a job after 20 seconds
    rule = event_client.put_rule(Name=rule_id,
                             ScheduleExpression=f"cron({time.minute} {time.hour} {time.day} {time.month} ? {time.year})",
                             State='ENABLED')


    rslt = event_client.put_targets(Rule=rule_id,
                                    Targets=[
                                        {
                                            'Arn': "arn:aws:lambda:us-east-2:215600070315:function:CollectFeedback",
                                            'Id': unique_id,
                                            'Input': json.dumps({"rule_id": rule_id, "unique_id": unique_id, "rule_arn" : rule["RuleArn"], "matchingID" : matchingID})
                                        }
                                            ])


    # Let's start by creating a 'lambda' client
    #
    lambda_clnt = boto3.client('lambda')
    # Now, we add the permission

    rslt = lambda_clnt.add_permission(FunctionName="arn:aws:lambda:us-east-2:215600070315:function:CollectFeedback",
                                      StatementId=unique_id,
                                      Action='lambda:InvokeFunction',
                                      Principal='events.amazonaws.com',
                                      SourceArn=rule["RuleArn"])

def schedule_immediate_cron_job(matchingID, index):

    event_client = boto3.client('events')

    time = datetime.utcnow() + timedelta(minutes = 1)
    rule_id = "event_ContactNextRecipient_" + str(uuid.uuid4())
    unique_id = str(uuid.uuid4())

    #create a rule to start a job after 20 seconds
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


    # Let's start by creating a 'lambda' client
    #
    lambda_clnt = boto3.client('lambda')
    # Now, we add the permission
    #
    rslt = lambda_clnt.add_permission(FunctionName="arn:aws:lambda:us-east-2:215600070315:function:ContactNextRecipient",
                                      StatementId=unique_id,
                                      Action='lambda:InvokeFunction',
                                      Principal='events.amazonaws.com',
                                      SourceArn=rule["RuleArn"])


def update_Past_matchings_table(matching_context):

    print("Start Updating Past Matchings")

    requestEndTime = datetime.now(indi_tz).strftime('%m-%d-%Y:%H-%M')
    requestStartTime = matching_context['requestStartTime']

    matching_context['totalProcessingTime'] = compute_total_processing_time(requestStartTime, requestEndTime)
    matching_context['requestEndTime'] = requestEndTime
    matching_context['matchingID'] = matching_context['matchingID']

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PastMatchings')

    table.put_item(Item=matching_context)

    print("Finished Updating Past Matchings")


def get_eta_localized(matching_context, recipient, time_delta):

    # ASSUMPTION: the depart time in the UI is of the same day and not the next day, for e.g., Driver is in Chicago at 11:00 PM and will depart 1:00 AM next day.

    # recipient timezone
    recipient_lat = recipient['recipientLocation'].split(",")[0]
    recipient_long = recipient['recipientLocation'].split(",")[1]
    truck_driver_tz = get_timezone_by_city(matching_context['driverDetails']['currentCity'])

    # truck driver depart time
    today = datetime.now(truck_driver_tz)
    rec_depart_time_str = matching_context['driverDetails']['departureTime'].split(":")

    # ASSUMPTION: the depart time in the UI is of the same day and not the next day, for e.g., Driver is in Chicago at 11:00 PM and will depart 1:00 AM next day.
    departure_time_local = datetime(today.year, today.month, today.day, int(rec_depart_time_str[0]), int(rec_depart_time_str[1]))
    departure_time = convert_time(matching_context['driverDetails']['currentCity'], departure_time_local, float(recipient_lat), float(recipient_long))

    #ETA
    return departure_time + timedelta(minutes=time_delta)


def exchange_contacts_driver_recipient(matching_context, index, phone_number):

    index = int(index)

    print("Begin Contact of Driver")

    recipient = matching_context['recipientsOrder'][index]
    print("Recipient: ", recipient)

    recipient_lat = recipient['recipientLocation'].split(",")[0]
    recipient_long = recipient['recipientLocation'].split(",")[1]

    eta = get_eta(matching_context['driverDetails']['departureTime'], matching_context['driverDetails']['currentCity'], float(recipient_lat), float(recipient_long))

    print("Eta is:", eta)



    sms_body = f"Your Food Drop request has been accepted by {recipient['recipientName']}. \nTheir contact number is {recipient['contactNumber']}. \nTheir location is {recipient['readableRecipientLocation']}. A link to their location can be found here: https://www.google.com/maps/search/?api=1&query={recipient_lat},{recipient_long}. \nThey will be expecting you at {eta}. If your ETA changes, please contact the facility directly at the number above. Facilities are not guaranteed to be open to accept your load if your arrival time is later than originally scheduled. If you cannot make it to the delivery please contact {IHN_contact}."

    print("Sms Body:", sms_body)
    #send the contact details of driver to the recipients
    driversPhoneNumber = matching_context['driverDetails']['phoneNumber']
    name = matching_context['driverDetails']['name']

    #send the contact details of the recipient to the driver
    send_SMS_using_twilio(sms_body, driversPhoneNumber)

    message =  json.dumps({"Type": "Accept",
                "driver": name,
                "drivers_phone": driversPhoneNumber})
            
    print("Final Message: ", message)

    return message


def get_matching_context_for_response(matchingID, recipient_id, reply):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')

    get_item_response = table.get_item(Key = {"matchingID": matchingID})

    if 'Item' not in get_item_response:
        return 0
    else:
        matching_context = get_item_response['Item']
        actualIndex = int(matching_context["index"])
        recipient_key = matching_context['recipientsOrder'][actualIndex]["Key"] 
    

    if reply == "yes":

        if recipient_key != recipient_id:
            recipientsOrder = matching_context["recipientsOrder"]
            recipIndex = -1
            for i, recipient in enumerate(recipientsOrder):
                if recipient["Key"] ==  recipient_id:
                    recipIndex = i
                

            if recipIndex == -1:
                return 0
            elif recipIndex >= actualIndex:
                return 3
            else:
                add_recip_to_queue(matchingID, recipientsOrder, matching_context["responseStatus"], recipIndex, actualIndex)
                return 1
            
        else:
            return get_item_response['Item']

    else:
        if recipient_key != recipient_id:
            return 0

        matching_context['responseStatus'][actualIndex] = "no"
        update_matching_context(matching_context)

        #schedule a cron job immediately
        schedule_immediate_cron_job(matching_context['matchingID'], actualIndex + 1)

        return 2


def get_eta(depart_str, depart_location, final_lat, final_long):

    truck_driver_tz = get_timezone_by_city(depart_location)

    year = int(depart_str.split("T")[0].split("-")[0])
    month = int(depart_str.split("T")[0].split("-")[1])
    day = int(depart_str.split("T")[0].split("-")[2])
    hour = int(depart_str.split("T")[1].split(":")[0])
    minute = int(depart_str.split("T")[1].split(":")[1])

    driver_time = datetime(year, month, day, hour, minute)

    commute_time = commute_time_seconds(depart_location, (final_lat, final_long))/60.0

    driver_time_in_dest = convert_time(depart_location, driver_time, float(final_lat), float(final_long))

    eta = driver_time_in_dest + timedelta(minutes=commute_time)

    print("Calculated ETA "+ eta.strftime("%I:%M %p, (%m/%d)"))

    return eta.strftime("%I:%M %p, (%m/%d)")
