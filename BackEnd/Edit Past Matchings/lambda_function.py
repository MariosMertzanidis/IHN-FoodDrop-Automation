import json
import boto3
from datetime import datetime


def compute_matching_ID(name, number):

    eventIdentifier = f"{name}:{number}:{datetime.now().strftime('%m-%d-%Y:%H-%M')}"

    matchingID = str(hash(eventIdentifier))

    return matchingID
    
    

def delete_donation(matchingID):
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('PastMatchings')
    
    print("Deleting:", str(matchingID))
    
    print("Get:", table.get_item(Key = {"matchingID": str(matchingID)}))

    resp = table.delete_item(Key = {"matchingID": str(matchingID)})
    
    print("Delete:", resp)

    return json.dumps(resp)
    
    
    
def create_donation(data):

    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('PastMatchings')
    
    matchingContext ={}
    
    driversName = data["driversName"]
    
    driversNumber = data["driversNumber"]
    
    matchingContext["matchingID"] = compute_matching_ID(driversName, driversNumber)
    
    matchingContext["driverDetails"] = {}
    
    matchingContext["driverDetails"]["companyName"] = ""
    
    matchingContext["driverDetails"]["currentCity"] = data["initialLocation"]
    
    matchingContext["driverDetails"]["destinationCity"] = data["destination"]
    
    matchingContext["driverDetails"]["name"] = driversName
    
    matchingContext["driverDetails"]["phoneNumber"] = driversNumber
    
    matchingContext["foodDetails"] = {}
    
    matchingContext["foodDetails"]["additionalInfo"] = data["otherInfo"]
    
    matchingContext["foodDetails"]["foodAmount"] = data["foodAmount"]
    
    matchingContext["foodDetails"]["foodType"] = data["foodItem"]
    
    matchingContext["foodDetails"]["rejectionReason"] = data["rejectionReason"]
    
    matchingContext["foodDetails"]["bulkOrPackaged"] = data["foodPackage"]
    
    matchingContext["foodDetails"]["refigeratedFrozenStable"] = data["foodStatus"]
    matchingContext["index"] = "0"
    
    matchingContext["requestEndTime"] = datetime.now().strftime('%m-%d-%Y:%H-%M')
    
    matchingContext["requestStartTime"] = matchingContext["requestEndTime"]
    
    matchingContext["responseStatus"] = ["yes"]
    
    matchingContext["totalProcessingTime"] = "0:00:00"
    
    matchingContext["finalRecipient"] = data["finalRecipient"]
    
    matchingContext["recipientsOrder"] = []
    
    if(data["finalRecipient"] != "Nobody Accepted"):
    
        recipientsTable = dynamodb.Table('Recipients')
        
        recipientInfo = recipientsTable.get_item(Key = {"recipientName": data["finalRecipient"]})["Item"]
                
        matchingContext["recipientsOrder"].append(recipientInfo)
        
        matchingContext["finalRecipientContactNumber"] = recipientInfo["contactNumber"]
    
    response = table.put_item(Item=matchingContext)
    
    return response

def update_donation(data):
    
    dynamodb = boto3.resource('dynamodb')
    
    table = dynamodb.Table('PastMatchings')
    
    matchingContext = table.get_item(Key = {"matchingID": data['matchingID']})["Item"]
    
    matchingContext["driverDetails"]["currentCity"] = data["initialLocation"]
    
    matchingContext["driverDetails"]["destinationCity"] = data["destination"]
    
    matchingContext["driverDetails"]["name"] = data["driversName"]
    
    matchingContext["driverDetails"]["phoneNumber"] = data["driversNumber"]
    
    matchingContext["foodDetails"]["foodAmount"] = data["foodAmount"]
    
    matchingContext["foodDetails"]["foodType"] = data["foodItem"]
    
    matchingContext["foodDetails"]["rejectionReason"] = data["rejectionReason"]
    
    matchingContext["foodDetails"]["bulkOrPackaged"] = data["foodPackage"]
    
    matchingContext["foodDetails"]["refigeratedFrozenStable"] = data["foodStatus"]
    
    if data['otherInfo'] != "":
    
        matchingContext["foodDetails"]["additionalInfo"] = data["otherInfo"]
        
    finalRecipient = data['finalRecipient']
    
    if finalRecipient != matchingContext["finalRecipient"]:
    
        matchingContext["finalRecipient"] = finalRecipient
        
        recipientIndex = -1
        
        if finalRecipient != "Nobody Accepted":
            
            for index, recipient in enumerate(matchingContext["recipientsOrder"]):
                
                if recipient["recipientName"] == finalRecipient:
                    recipientIndex = index
                    break
            
            if recipientIndex == -1:
                recipientsTable = dynamodb.Table('Recipients')
        
                recipientInfo = recipientsTable.get_item(Key = {"recipientName": finalRecipient})["Item"]
                
                matchingContext["recipientsOrder"].append(recipientInfo)
                
                for i in range(len(matchingContext["responseStatus"])):
                    
                    if matchingContext["responseStatus"][i] == "yes":
                        matchingContext["responseStatus"][i] = "no"
                        
                
                matchingContext["responseStatus"].append("yes")
                matchingContext["index"] = str(len(matchingContext["responseStatus"])-1)
                
            else:
                matchingContext["index"] = str(recipientIndex)
            
                matchingContext["finalRecipientContactNumber"] = matchingContext["recipientsOrder"][recipientIndex]["contactNumber"]
                
                for i in range(len(matchingContext["responseStatus"])):
                    
                    if matchingContext["responseStatus"][i] == "yes":
                        matchingContext["responseStatus"][i] = "no"
                
                matchingContext["responseStatus"][recipientIndex] = "yes"
        else:
            matchingContext["finalRecipientContactNumber"] = ""
                
            for i in range(len(matchingContext["responseStatus"])):
                if matchingContext["responseStatus"][i] == "yes":
                    matchingContext["responseStatus"][i] = "no"
            
    print("Updating item:", matchingContext)
            
    respons = table.put_item(Item = matchingContext)
    
    return respons

def lambda_handler(event, context):
    
    
    resp = "Hello"
    print(event)

    if(event["method"] == "DELETE"):
        print("Deleting")
        resp = delete_donation(event["matchingID"])
        
    elif(event["method"] == "POST"):
        print("Updating")
        resp = update_donation(event)
        
    elif(event["method"] == "PUT"):
        print("Adding")
        resp = create_donation(event)
    
    print("Sending:", resp)
    
    return {
        'statusCode': 200,
        'headers': {
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST,PUT,DELETE'
                },
        'body': resp
    }