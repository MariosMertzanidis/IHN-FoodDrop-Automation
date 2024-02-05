import boto3
import json
from datetime import datetime, timedelta
import base64


from utilities import *

def lambda_handler(event, context):

    print("Begin event:", str(event))

    eventBody = event

    matchingID = eventBody["matchingID"]
    index = eventBody["index"]
    recipientID = eventBody["recipientID"]

    dynamodb = boto3.resource('dynamodb')

    tableInProgressMatching = dynamodb.Table('InProgressMatchingContext')
    tablePastMatching = dynamodb.Table('PastMatchings')

    get_matchingID_response_inProgress = tableInProgressMatching.get_item(Key = {"matchingID": matchingID})

    #returns 0 if matching_context of the specified matchingID was not present
    if 'Item' in get_matchingID_response_inProgress:
        matching_context =  get_matchingID_response_inProgress['Item']
        matchingDone = False
    else:
        get_matchingID_response_past = tablePastMatching.get_item(Key = {"matchingID": matchingID})
        if 'Item' in get_matchingID_response_past:
            matching_context =  get_matchingID_response_past['Item']
            matching_index = int(matching_context["index"])
            recipient = matching_context["recipientsOrder"][matching_index]
            recipient_key = recipient["Key"]
            if matching_context["finalRecipient"]!= "Nobody Accepted" and  recipient_key == recipientID:
                driver_details = matching_context["driverDetails"]
                response = {"Type": "Already_Accept", "driver": driver_details["name"], "drivers_phone": driver_details["phoneNumber"]}
                resipient_lat, resipient_long = recipient["recipientLocation"].split(",")
                eta = get_eta(driver_details["departureTime"], driver_details["currentCity"], float(resipient_lat), float(resipient_long))
                response["eta"] = eta
                response["willing_to_wait"] = driver_details["willingToWait"]
                response["nextBusinessDay"] = driver_details["nextBusinessDay"]
                return json.dumps(response)
        
            else:
                return json.dumps({"Type": "Old_Matching"})
                
        else:
            return json.dumps({"Type": "No_Matching"})

    recipient = matching_context['recipientsOrder'][int(index)]

    if recipient["Key"] != recipientID:
        return json.dumps({"Type": "Index_ID_Mismatch"})
            
    if int(index) < int(matching_context['index']):
        myRespons = {"Type": "Re-add_Queueu"}
    else:
        myRespons = {"Type": "Ok"}

    myRespons["image"] =  get_image_from_bucket(matchingID)
    
    myRespons["food_amount"] = matching_context['foodDetails']['foodAmount']
    myRespons["food_type"] = matching_context['foodDetails']['foodType']
    myRespons["rejection_reason"] = matching_context['foodDetails']['rejectionReason']
    myRespons["bulk_or_package"] = matching_context['foodDetails']['bulkOrPackaged']
    myRespons["refigerated_frozen_stable"] = matching_context['foodDetails']['refigeratedFrozenStable']
    myRespons["additional_info"] =matching_context['foodDetails']['additionalInfo']
    


    current_location = matching_context['driverDetails']['currentCity']

    myRespons["driver_city"] = current_location
    myRespons["departure_time"] = matching_context['driverDetails']['departureTime']
    myRespons["company_name"] = matching_context['driverDetails']['companyName']
    myRespons["willing_to_wait"] = matching_context['driverDetails']["willingToWait"]
    myRespons["nextBusinessDay"] = matching_context['driverDetails']["nextBusinessDay"]

    recipient_lat = recipient['recipientLocation'].split(",")[0]
    recipient_long = recipient['recipientLocation'].split(",")[1]

    print("myResponse (no eta):", str(myRespons))

    # Assumption: When driver say tommorow morning but it is before 3:00 am he means 7:00-9:00 am on the same day.
    myRespons["eta"] = get_eta(matching_context['driverDetails']['departureTime'], current_location, float(recipient_lat), float(recipient_long))

    print("Final_respone: ", myRespons)

    update_link_was_clicked(matching_context["responseStatus"], int(index), matchingID, tableInProgressMatching)
   
    return json.dumps(myRespons)
    
def update_link_was_clicked(responseStatus, index, matchingID, table):
    print("In update link: ", str((responseStatus, index, matchingID)))
    if responseStatus[index] == "notYetContacted" or responseStatus[index] == "awaitingResponse":
        print("Updating to opened link")
        responseStatus[index] = "OpenedLink"
        response = table.update_item(
            Key = {"matchingID": matchingID},
            UpdateExpression="set #attr1 = :updatedList",
            ExpressionAttributeValues={ ':updatedList': responseStatus},
            ExpressionAttributeNames={'#attr1': "responseStatus"},
            ReturnValues="UPDATED_NEW"

        )
        print("Update:", response)


def get_image_from_bucket(matchingID):
    try:
        s3 = boto3.resource('s3')
        bucket = s3.Bucket("food-drop-images")
        image = bucket.Object(matchingID)
        hexa_byte_img = image.get().get('Body').read()
        base64_encoded_img = str(base64.b64encode(hexa_byte_img))[2:-1]
        if len(base64_encoded_img) < 100:
            return "-"
        else:
            return base64_encoded_img
    except:
        return "-"

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
