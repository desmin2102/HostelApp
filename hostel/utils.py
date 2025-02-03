import requests

from ehostel import settings


def get_lat_long_from_address(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key=YOUR_GOOGLE_MAPS_API_KEY"
    response = requests.get(url)
    result = response.json()

    if result['status'] == 'OK':
        lat = result['results'][0]['geometry']['location']['lat']
        lng = result['results'][0]['geometry']['location']['lng']
        return lat, lng
    else:
        return None, None

def get_coordinates_from_address(address, city, district, ward):

    full_address = f"{address}, {ward.name}, {district.name}, {city.name}"
    url = "https://maps.gomaps.pro/maps/api/geocode/json"
    params = {'address': full_address, 'key': settings.GOMAPS_API_KEY}
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data.get('results'):
            latitude = data['results'][0]['geometry']['location']['lat']
            longitude = data['results'][0]['geometry']['location']['lng']
            return latitude, longitude
        else:
            raise ValueError("Không tìm thấy kết quả tọa độ từ Gomaps.")
    else:
        raise ValueError("Không thể lấy tọa độ từ Gomaps.pro.")