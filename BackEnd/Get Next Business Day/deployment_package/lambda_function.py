import json
import boto3
import holidays
from datetime import datetime, timedelta
import pytz

indi_tz = pytz.timezone("America/Indianapolis")


def fetch_recipients():
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('Recipients')

    resp = table.scan()['Items']

    return resp

def lambda_handler(event, context):
    # TODO implement
    
    print(event)
    
    
    recipients = fetch_recipients()

    timestamp_now = datetime.now(indi_tz)

    my_year = int(timestamp_now.strftime("%Y"))

    us_holidays = holidays.US(state = "IN", years = my_year)

    possible_date = timestamp_now

    for i in range(7):
        possible_date = possible_date + timedelta(days=1)
        
        if possible_date.strftime("%d-%m-%Y") not in us_holidays:

            possible_day = possible_date.strftime("%w")

            for food_bank in recipients:

                if food_bank["availability"][possible_day]["is_open"]:
                    return {
                        'statusCode': 200,
                        'headers': {
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'OPTIONS,POST,PUT,DELETE'
                        },
                        'body': possible_date.strftime("(%m/%d)")
                        }


    
    return {
        'statusCode': 200,
        'headers': {
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,PUT,DELETE'
                },
        'body': "Oups"
    }