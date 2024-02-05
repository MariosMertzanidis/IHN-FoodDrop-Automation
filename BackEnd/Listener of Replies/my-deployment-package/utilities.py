import googlemaps
from datetime import datetime
import requests
from twilio.rest import Client
import pytz

#Gmaps API key
GMAPS_API_key = '-'

#Twilio Config data
twilio_account_sid = "-"
twilio_auth_token = "-"
twilio_API_phone_number = "-"


def commute_time_seconds(A, B):

    print(A)
    print(B)
    # call google map distance matrix API for transit time

    gmaps = googlemaps.Client(key=GMAPS_API_key)

    #add exception handling
    result = gmaps.distance_matrix(A, B, mode = 'driving')

    gmaps_api_transit_time = int(result['rows'][0]['elements'][0]['duration']['value'])

    return gmaps_api_transit_time


def compute_total_processing_time(startTime, endTime):

    start_dateTime = datetime.strptime(startTime, '%m-%d-%Y:%H-%M')
    end_dateTime = datetime.strptime(endTime, '%m-%d-%Y:%H-%M')

    return str(end_dateTime - start_dateTime)




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
    #utc_time = local_timezone.localize(local_time).astimezone(pytz.utc)

    # Convert UTC time to destination timezone
    year = local_time.year
    month = local_time.month
    day = local_time.day
    hour = local_time.hour
    minute = local_time.minute
    local_time = datetime(year=year, month = month, day = day, hour = hour, minute = minute)
    dest_time = local_timezone.localize(local_time).astimezone(dest_timezone)

    print(f"Conversion of Time: local city = {local_city_name}, local time = {local_time}, destination lat-long = {dest_latitude}{dest_longitude}, dest_time = {dest_time}")

    return dest_time


def twiml_response_string(message):

    return f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"\
           "<Response><Message><Body>"+ message + "</Body></Message></Response>"


def send_SMS_using_twilio(sms_body, recipient_phone_number):

    client = Client(twilio_account_sid, twilio_auth_token)
    client.messages.create(
        to = recipient_phone_number,
        from_ = twilio_API_phone_number,
        body = sms_body
    )



# Get timezone of local city
# geolocator = Nominatim(user_agent="IHN-application")
# location = geolocator.geocode(local_city_name)

# timezone_name = location.raw['timezone']
# local_timezone = pytz.timezone(timezone_name)

# tf = TimezoneFinder()
# local_timezone = pytz.timezone(tf.timezone_at(lng=location.longitude, lat=location.latitude))

# Get timezone of destination city
# tf = TimezoneFinder()
# dest_timezone = pytz.timezone(tf.timezone_at(lng=dest_longitude, lat=dest_latitude))

# location = geolocator.reverse(Point(dest_latitude, dest_longitude))
# timezone_name = location.raw['timezone']
# dest_timezone = pytz.timezone(timezone_name)
