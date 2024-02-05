import json
import boto3
from datetime import datetime
from functools import cmp_to_key


def compare(item1, item2):
    
    start_datetime1_str = item1['requestEndTime']
    start_datetime2_str = item2['requestEndTime']
    print("Comparing:", start_datetime1_str, start_datetime2_str)
    matching_initiation_datetime1 = datetime.strptime(start_datetime1_str, "%m-%d-%Y:%H-%M")
    matching_initiation_datetime2 = datetime.strptime(start_datetime2_str, "%m-%d-%Y:%H-%M")
    
    if matching_initiation_datetime1 < matching_initiation_datetime2:
        return -1
    elif matching_initiation_datetime1 > matching_initiation_datetime2:
        return 1
    else:
        return 0


def fetch_past_matchings(start, end):
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('PastMatchings')

    resp = table.scan()['Items']
    
    resp = [i for i in resp if (compare(i,{'requestEndTime': start})==1 and compare(i,{'requestEndTime': end})==-1)]
    
    
    resp = sorted(resp, key=cmp_to_key(compare))
    
    print("Respones:", resp)
    
    return json.dumps(resp)

def lambda_handler(event, context):
    # TODO implement
    
    print("Event: ", event, context)
    
    startDate, endDate = event["queryStringParameters"]["dateRange"].split(' - ')
    
    startDate, endDate = startDate.replace('/','-')+":00-01", endDate.replace('/','-')+":23-59"
    
    print((startDate, endDate))
    
    past_matchings = fetch_past_matchings(startDate, endDate)
    
    return {
        'statusCode': 200,
        'headers': {
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,PUT,DELETE'
                },
        'body': past_matchings
    }