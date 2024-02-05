import json
import re
import boto3
import googlemaps
import random

GMAPS_API_key = '-'

letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

digits = "012345678901234567890123456789"

def add_recipient(recipientObject):

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('Recipients')

    return table.put_item(Item=recipientObject)

def remove_extra_spaces_from_coordinaes(coordinate_string):

    latlong = [chunk.strip() for chunk in coordinate_string.split(",")]

    return latlong[0] + "," + latlong[1]

def get_readable_location(coordinate_string):

    coord = [chunk.strip() for chunk in coordinate_string.split(",")]

    gmaps = googlemaps.Client(key=GMAPS_API_key)
    result = gmaps.reverse_geocode((coord[0], coord[1]))

    print(f"Gmap reverse geocode api result is : {result[0]}")
    return result[0]['formatted_address']

def get_availability_dictionary(event):

    availability = {}

    day_to_index = {
        1: "Monday",
        2: "Tuesday",
        3: "Wednesday",
        4: "Thursday",
        5: "Friday",
        6: "Saturday",
        0: "Sunday",
    }

    for i in range(7):
        availability[str(i)] = {
            "is_open": event[f"open{day_to_index[i]}"],
            "opening_time": event[f"opentime{day_to_index[i]}"],
            "closing_time": event[f"closetime{day_to_index[i]}"]
        }

    return availability

def addRecipient(event):
    assert 'recipientName' in event, "Recipient Name is required"
    assert 'contactNumber' in event, "Contact Number is required"
    assert 'recipientLocation' in event, "Recipient Location is required"

    key = "".join(random.choices(letters+digits, k=12))
    
    recipientObject = {
        "recipientName": event['recipientName'],
        "contactNumber": event['contactNumber'],
        "Key": key,
        "recipientLocation": remove_extra_spaces_from_coordinaes(event['recipientLocation']),
        "availability": get_availability_dictionary(event),
        "lastDonationDate": "01/01/2000",
        "readableRecipientLocation": get_readable_location(event['recipientLocation'])
    }

    #by default the last donation date for a new recipient is: 01/01/2020

    response = add_recipient(recipientObject)

    return {
        'statusCode': 200,
        'body': "Recipient Added Successfully"
    }

def editRecipient(event):
    if event['oldName'] == event['recipientName']:
        return addRecipient(event)
    else:
        dynamodb = boto3.resource('dynamodb')
    
        table = dynamodb.Table('Recipients')

        resp = table.delete_item(Key = {"recipientName": str(event['recipientName'])})

        resp2 = addRecipient(event)
        return {
        'statusCode': 200,
        'body': {"deleteResponse":resp,
                "addResponse":resp2}
    }

def lambda_handler(event, context):

    assert 'type' in event, "Edditing or Adding?"

    if event['type'] == "Add":
        return addRecipient(event)
    else:
        return editRecipient(event)
    
