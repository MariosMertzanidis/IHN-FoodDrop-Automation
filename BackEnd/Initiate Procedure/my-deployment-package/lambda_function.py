import json
import boto3
import base64
from datetime import datetime, timedelta
from utilities import * 
import uuid
import pytz

indi_tz = pytz.timezone("America/Indianapolis")

"""
-The Function that initiates the matching process.
-The object 'event' will contain the following information filled by the truck driver:
 "name","phoneNumber","companyName","foodType","foodAmount","currentCity","destinationCity",
 "rejectionReason", "canDeliverToColdStore", "canWaitTillTomorrow"
"""
def lambda_handler(event, context):

    print("Begin event: ", str(event))

    image = event["Image"]
    del event["Image"] #delete image from dictionary so that it is not carried around
    matchingID = compute_matching_ID(event)
    if matching_id_already_exists(matchingID):

        return {
        'statusCode': 500,
        'body': json.dumps('A request with the same matchingID is already in progress')
        }

    food_details = {
        "foodType" : event['foodType'],
        "foodAmount" : get_food_amount(event),
        "rejectionReason" : get_rejection_reason(event),
        "bulkOrPackaged" : event['bulkOrPackaged'],
        "refigeratedFrozenStable": event['RefrigFrozenStable'],
        "additionalInfo": event['AdditionalInfo']
    }

    driver_details = {
        "name" : event['name'],
        "phoneNumber" : event['phoneNumber'],
        "companyName" : event['companyName'],
        "currentCity" : event['currentCity'],
        "destinationCity" : event['destinationCity'],
        "departureTime": event["departureTime"],
        "willingToWait": event["willingToWait"],
        "nextBusinessDay": event["nextBusinessDay"]
    }

    #upload image to DynamoDB
    image_upload = upload_image_to_S3(image, matchingID)
    image_len = len(image)
    #send notification to the driver (why not also to the person who filled the form?)
    send_notification_message_of_request_submit(event)

    #return an array of recipients (represented as dictionary)
    recipient_order = compute_recipient_ordering(driver_details)
    print(f"recipient ordering is {recipient_order}")

    if len(recipient_order) == 0:
        send_sorry_notification(event)
        response = generate_and_store_past_matching_context(matchingID, food_details, driver_details, index = 0)
        return {
            'statusCode': 200,
            'body': json.dumps('Sorry, your request cannot be processed since no recipients are available right now for accepting the donation.')
        }

    #genereate and store matching context in dynamoDB
    matchingContext = generate_and_store_matching_context(matchingID, recipient_order, food_details, driver_details, index = 0)

    #schedule a compute job to contact the first recipient
    schedule_immediate_cron_job(matchingID, index = 0)

    return {
        'statusCode': 200,
        'body': json.dumps({"ImageDBResponse": image_upload, "Image_len": image_len})
    }


#upload base64 image to to apropriate S3 bucket and return the images URL
def upload_image_to_S3(image, matchingID):
    try:
        s3 = boto3.client('s3')

        image_data = base64.b64decode(image)

        bucket_name = "food-drop-images"
        key = matchingID

        resp = s3.put_object(Bucket=bucket_name, Key=key, Body=image_data, ContentType='image/jpeg')
    
        return resp
    except Exception as e:
        return str(e)


def get_food_amount(event):

    food_ammount = ""

    if len(event["foodAmountPallets"]):
        if str(event["foodAmountPallets"]) == "1":
            food_ammount += "1 pallet"
        else:
            food_ammount += event["foodAmountPallets"]+" pallets"

    if len(event["foodAmountCases"]):
        if len(food_ammount):
            food_ammount += ", "
        if str(event["foodAmountCases"]) == "1":
            food_ammount += "1 case"
        else:
            food_ammount += event["foodAmountCases"]+" cases"

    if len(event["foodAmountPounds"]):
        if len(food_ammount):
            food_ammount += ", "
        if str(event["foodAmountPounds"]) == "1":
            food_ammount += "1 pound"
        else:
            food_ammount += event["foodAmountPounds"]+" pounds"

    return food_ammount

def get_rejection_reason(event):

    if len(event["rejectionReasonOther"]):
        return event["rejectionReasonOther"]

    return event['rejectionReason']

def send_sorry_notification(event):

    recipient_name = event['name']

    sms_body = f"Sorry {recipient_name}, your Food Drop request cannot be processed since currently no recipients are available to accept the donation."

    #send message to driver
    send_text_message(event['phoneNumber'], event['name'], sms_body)

def send_notification_message_of_request_submit(event):
    #the message data
    recipient_name = event['name']
    sms_body = f"Dear {recipient_name}, your Food Drop request has been submitted successfully. We will notify you as soon as we find a match for you!"

    #send message to driver
    send_text_message(event['phoneNumber'], event['name'], sms_body)


#returns 1 if an entry with matchingID was already present
def matching_id_already_exists(matchingID):

    #check if a job with same matching is already in-progress.
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')


    get_matchingID_response = table.get_item(Key = {"matchingID": matchingID})

    return ('Item' in get_matchingID_response)

def generate_and_store_matching_context(matchingID, recipient_order, food_details, driver_details, index = 0):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('InProgressMatchingContext')

    response_status = ["notYetContacted" for ele in recipient_order]

    matchingContext = {
        'matchingID': matchingID,
        'recipientsOrder': recipient_order,
        'responseStatus': response_status,
        'foodDetails' : food_details,
        'driverDetails': driver_details,
        'index': str(index),
        'requestStartTime': datetime.now(indi_tz).strftime('%m-%d-%Y:%H-%M')
        }

    response = table.put_item(Item=matchingContext)

    return matchingContext

def generate_and_store_past_matching_context(matchingID, food_details, driver_details, index = 0):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('PastMatchings')

    time = datetime.now(indi_tz).strftime('%m-%d-%Y:%H-%M')

    matchingContext = {
        'matchingID': matchingID,
        'recipientsOrder': [],
        'responseStatus': [],
        'finalRecipient': "Nobody Accepted",
        'foodDetails' : food_details,
        'driverDetails': driver_details,
        'index': str(index),
        'requestStartTime': time,
        'requestEndTime': time,
        'totalProcessingTime': "0:00:00"
        }

    response = table.put_item(Item=matchingContext)

    return response


def compute_matching_ID(event):

    eventIdentifier = f"{event['name']}:{event['phoneNumber']}:{datetime.now(indi_tz).strftime('%m-%d-%Y:%H-%M')}"

    matchingID = str(hash(eventIdentifier))

    return matchingID

def compute_recipient_ordering(event):

    current_location = event['currentCity']
    destination = event['destinationCity']

    recipients = retrieve_recipients()

    delta_times = []
    last_donation_dates = []

    print("Printing Retrieved recipients:")
    print(recipients)

    for i in range(len(recipients)):

        recipient = recipients[i]

        recipient_location = recipient['recipientLocation']

        delta_time = compute_time_delta_minutes(current_location, destination, recipient_location)
        last_donation_date = datetime.strptime(recipient['lastDonationDate'], "%m/%d/%Y")

        delta_times.append(delta_time)
        last_donation_dates.append(last_donation_date)

    #generate ordering as per distances and last donation times
    fair_ordering = generate_fair_ordering(delta_times, last_donation_dates, recipients)

    #filter out recipients that are closed
    ordering_as_per_availability = get_ordering_as_per_availability(event, fair_ordering)

    return ordering_as_per_availability

def get_ordering_as_per_availability(event, fair_ordering):

    fair_ordering_per_availability = []

    for i in range(len(fair_ordering)):

        recipient = fair_ordering[i]

        if is_currently_available(event, recipient):
            fair_ordering_per_availability.append(recipient)

    return fair_ordering_per_availability


def is_currently_available(event, recipient):

    # ASSUMPTION: the depart time in the UI is of the same day and not the next day, for e.g., Driver is in Chicago at 11:00 PM and will depart 1:00 AM next day.
    # Assumption: the truck driver can cover the distance to the foodbank in one day

    truck_driver_tz = get_timezone_by_city(event['currentCity'])

    time_now = datetime.now(truck_driver_tz)

    year = time_now.strftime("%Y")

    next_business_day = event["nextBusinessDay"].strip("()").split("/")

    next_business_date = datetime(int(year), int(next_business_day[0]), int(next_business_day[1]))

    if event["willingToWait"] == "True" and event["nextBusinessDay"] != 'undefined':
        next_business_day = event["nextBusinessDay"].strip("()").split("/")

        next_business_date = datetime(int(year), int(next_business_day[0]), int(next_business_day[1]))
        
        if recipient['availability'][next_business_date.strftime("%w")]["is_open"]:
            return 1

    # recipient timezone
    recipient_lat = recipient['recipientLocation'].split(",")[0]
    recipient_long = recipient['recipientLocation'].split(",")[1]

    recipient_tz = get_timezone(recipient_lat, recipient_long)

    eta = get_eta(event['departureTime'], event['currentCity'], float(recipient_lat), float(recipient_long))

    # check availability of recipient on the ETA date
    availability_today = recipient['availability'][eta.strftime("%w")]


    if availability_today["is_open"] :

        opening_hour, opening_minute = availability_today["opening_time"].split(":")
        closing_hour, closing_minute = availability_today["closing_time"].split(":")

        opening_localized = datetime(eta.year, eta.month, eta.day, int(opening_hour), int(opening_minute))
        closing_localized = datetime(eta.year, eta.month, eta.day, int(closing_hour), int(closing_minute))

        print(f"eta = {eta},  opening_localized = {opening_localized}, and closing_localized={closing_localized}")
        if eta >= opening_localized and eta <= closing_localized:
            return 1

    return 0


def retrieve_recipients():

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Recipients')

    resp = table.scan()['Items']
    print(f"recipients from DynamoDB = {resp}")
    #recipients = [clean_recipient(ele) for ele in resp['Items']]

    return resp


def clean_recipient(recipient):

    clean_recipient = {}

    for key, value in recipient.items():

        clean_recipient[key] = value['S']

    return clean_recipient


def generate_fair_ordering(delta_times, last_donation_dates, recipients):

    list_of_tuples = []
    tuples_to_index_map = {}

    print(f"computed delta times in minutes are = {delta_times}")

    for i in range(len(recipients)):

        #division performed to create buckets by radius
        delta_time_rounded = int(delta_times[i]/DELTA_TIME_BUCKETING_CONSTANT)

        tuple = (delta_time_rounded, last_donation_dates[i], recipients[i]['recipientName'])

        list_of_tuples.append(tuple)
        tuples_to_index_map[tuple] = i


    list_of_tuples.sort()

    sorted_recipients = []

    for ele in list_of_tuples:
        sorted_recipients.append(recipients[tuples_to_index_map[ele]])



    print(f"recipients : {recipients}")
    print(f"delta times = {delta_times}")
    print(f"last donation dates = {last_donation_dates}")
    print(f"sorted recipients: {sorted_recipients}")

    return sorted_recipients


def schedule_immediate_cron_job(matchingID, index):

    event_client = boto3.client('events')

    rule_id = "event_ContactNextRecipient_" + str(uuid.uuid4())
    unique_id = str(uuid.uuid4())

    time = datetime.utcnow() + timedelta(minutes= 1)

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

    print(f"Scheduled CRON job with ruleID = {rule_id} and unique_id = {unique_id}")

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

    year = eta.year
    month = eta.month
    day = eta.day
    hour = eta.hour
    minute = eta.minute
    eta_without_tzinfo = datetime(year=year, month = month, day = day, hour = hour, minute = minute)

    return eta_without_tzinfo