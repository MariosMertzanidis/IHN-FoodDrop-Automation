import requests
import pytz
import googlemaps
from twilio.rest import Client
from datetime import datetime, timedelta

#Gmaps API key
GMAPS_API_key = '-'

DELTA_TIME_BUCKETING_CONSTANT = 30

#Twilio Config data
twilio_account_sid = "-"
twilio_auth_token = "-"
twilio_API_phone_number = "-"

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
    print("Converting Time for "+ str(local_city_name) + " and time " + str(local_time)+ " to "+str((dest_latitude, dest_longitude)))
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
    year = local_time.year
    month = local_time.month
    day = local_time.day
    hour = local_time.hour
    minute = local_time.minute
    local_time = datetime(year=year, month = month, day = day, hour = hour, minute = minute)
    # Convert UTC time to destination timezone
    dest_time = local_timezone.localize(local_time).astimezone(dest_timezone)

    print(f"Conversion of Time: local city = {local_city_name}, local time = {local_time}, destination lat-long = {dest_latitude}{dest_longitude}, dest_time = {dest_time}")

    return dest_time


def compute_time_delta_minutes(currentLocation, finalLocation, transitLocation):

    time_delta_seconds = commute_time_seconds(currentLocation, transitLocation) + commute_time_seconds(transitLocation, finalLocation) - commute_time_seconds(currentLocation, finalLocation)

    #division performed to convert seconds to minutes

    print(f"computing delta time for {currentLocation} --> {transitLocation} --> {finalLocation}: delta time = {time_delta_seconds/60.0}")

    return time_delta_seconds/60.0


def commute_time_seconds(A, B):
    try:
        print(A)
        print(B)
        # call google map distance matrix API for transit time

        gmaps = googlemaps.Client(key=GMAPS_API_key)

        #add exception handling
        result = gmaps.distance_matrix(A, B, mode = 'driving')

        gmaps_api_transit_time = int(result['rows'][0]['elements'][0]['duration']['value'])

        return gmaps_api_transit_time
    except:
        return 2500000



def send_text_message(phone_number, recipient_name, sms_body):

    print("sending SMS: ", phone_number, recipient_name, sms_body)

    #sending the message
    client = Client(twilio_account_sid, twilio_auth_token)

    client.messages.create(
        to = phone_number,
        from_ = twilio_API_phone_number,
        body = sms_body
    )
