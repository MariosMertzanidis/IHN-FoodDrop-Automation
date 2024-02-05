from datetime import datetime, timedelta
import googlemaps
from twilio.rest import Client
import requests
import pytz

#Gmaps API key has been anonymized
GMAPS_API_key = GMAPS_KEY

#Twilio Config data
twilio_account_sid = TWILIO_SID
twilio_auth_token = TWILIO_AUTH_TOKEN
twilio_API_phone_number = PHONE_NUMBER
twilio_API_feedback_phone_number = PHONE_NUMBER

ALLOWED_MINUTES_TO_RESPOND_WEEKEND = 30
ALLOWED_MINUTES_TO_RESPOND_WEEKDAY = 15

def get_rejection_reason_from_code(rejection_code):

    if rejection_code[0] == "#":
        return rejection_code[1:]

    rejection_code_to_text = {
        "reason_mold": "of spoilage or mold",

        "reason_temp_high": "of high temperature",
        "reason_temp_low": "of low temperature",

        "reason_damage": "the items were damaged",
        "reason_damage_pallets": "the pallets were damaged",
        "reason_damage_items_some": "some of the items were damaged",
        "reason_damage_items_all": "all of the items were damaged",
        "reason_damage_packaging": "the packaging was damaged",

        "reason_mistake": "of an ordering mistake",
        "reason_mistake_items": "wrong items were delivered",
        "reason_mistake_size": "items delivered were of the wrong size",
        "reason_mistake_nolongerneeded": "items delivered are no longer needed",
        
        "reason_mistake_date_ripe": "produce is too ripe",
        "reason_mistake_date_expiration": "product is close to the expiration date",

        "reason_late": "the delivery didn't arrive on time",
        "reason_other": "of unknown reasons",
        "reason_overage": "of overage/overshipment",
        "reason_shifted": "the pallets shifted in the truck",
        "reason_cosmetic": "of cosmetic issues (spots, twisting, etc.)",
        "reason_mislabeled": "products were mislabeled or in wrong pallets",
        "reason_lateearly": "late or early delivery",
        "reason_specifications": "product does not meet specifications"
    }

    return rejection_code_to_text[rejection_code]


def compute_total_processing_time(startTime, endTime):
    
    start_dateTime = datetime.strptime(startTime, '%m-%d-%Y:%H-%M')
    end_dateTime = datetime.strptime(endTime, '%m-%d-%Y:%H-%M')

    return str(end_dateTime - start_dateTime)


def send_SMS_using_twilio(sms_body, recipient_phone_number):
    
    client = Client(twilio_account_sid, twilio_auth_token)

    print(f"sending this sms = {sms_body} to phone number = {recipient_phone_number}")
    client.messages.create(
        to = recipient_phone_number,
        from_ = twilio_API_phone_number,
        body = sms_body
    )


def send_feedback_SMS_using_twilio(sms_body, recipient_phone_number):

    client = Client(twilio_account_sid, twilio_auth_token)
    client.messages.create(
        to = recipient_phone_number,
        from_ = twilio_API_feedback_phone_number,
        body = sms_body
    )

def get_maximum_minutes_to_respond():
    
    # #for debug uncomment this:
    # return 3

    allowed_time_to_respond = 0
    
    if datetime.today().weekday() >= 5:
        allowed_time_to_respond = ALLOWED_MINUTES_TO_RESPOND_WEEKEND #minutes
    else:
        allowed_time_to_respond = ALLOWED_MINUTES_TO_RESPOND_WEEKDAY
    
    return allowed_time_to_respond

def reply_to_driver_with_a_negative(phoneNumber):
    
    #sending the message
    client = Client(twilio_account_sid, twilio_auth_token)
    
    client.messages.create(
        to = phoneNumber,
        from_ = twilio_API_phone_number,
        body = "Sorry no recipients accepted the order, we cannot complete your matching request."
    )

def get_timezone_by_city(city):
    url = f'https://maps.googleapis.com/maps/api/geocode/json?address={city}&key={GMAPS_API_key}'
    response = requests.get(url)
    data = response.json()
    if data['status'] == 'OK':
        lat = data['results'][0]['geometry']['location']['lat']
        lng = data['results'][0]['geometry']['location']['lng']
        timezone = get_timezone(lat, lng)
        return timezone
    else:
        return None

def get_timezone(lat, lng):
    url = f'https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp=0&key={GMAPS_API_key}'
    response = requests.get(url)
    data = response.json()
    if data['status'] == 'OK':
        timezone_id = data['timeZoneId']
        timezone = pytz.timezone(timezone_id)
        return timezone
    else:
        return None

def convert_time(local_city_name, local_time, dest_latitude, dest_longitude):

    # Get timezone of local city
    # geolocator = Nominatim(user_agent="IHN-application")
    # location = geolocator.geocode(local_city_name)

    # timezone_name = location.raw['timezone']
    # local_timezone = pytz.timezone(timezone_name)

    local_timezone = get_timezone_by_city(local_city_name)

    # tf = TimezoneFinder()
    # local_timezone = pytz.timezone(tf.timezone_at(lng=location.longitude, lat=location.latitude))

    # Get timezone of destination city
    # tf = TimezoneFinder()
    # dest_timezone = pytz.timezone(tf.timezone_at(lng=dest_longitude, lat=dest_latitude))

    # location = geolocator.reverse(Point(dest_latitude, dest_longitude))
    # timezone_name = location.raw['timezone']
    # dest_timezone = pytz.timezone(timezone_name)

    dest_timezone = get_timezone(dest_latitude, dest_longitude)


    # Convert time to UTC
    utc_time = local_timezone.localize(local_time).astimezone(pytz.utc)

    # Convert UTC time to destination timezone
    dest_time = utc_time.astimezone(dest_timezone)

    print(f"Conversion of Time: local city = {local_city_name}, local time = {local_time}, destination lat-long = {dest_latitude}{dest_longitude}, utc-time = {utc_time} dest_time = {dest_time}")

    return dest_time

def commute_time_seconds(A, B):
    
    print(A)
    print(B)
    # call google map distance matrix API for transit time
    
    gmaps = googlemaps.Client(key=GMAPS_API_key)
    
    #add exception handling
    result = gmaps.distance_matrix(A, B, mode = 'driving')

    gmaps_api_transit_time = int(result['rows'][0]['elements'][0]['duration']['value'])

    return gmaps_api_transit_time