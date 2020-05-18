from sense_hat import SenseHat
import os
import datetime as dt
import ephem
import math
from picamera import PiCamera
from logzero import logger, logfile
import csv
from time import sleep
from matplotlib import path

sh = SenseHat()

dir_path = os.path.dirname(os.path.realpath(__file__)) # directory per salvare i file
logfile(dir_path + "/MostlyHarmless2020.log")


# oggetto ISS
name = "ISS (ZARYA)"
line1 = "1 25544U 98067A   20014.55106447  .00001081  00000-0  27319-4 0  9995"
line2 = "2 25544  51.6449  33.6082 0005001 130.1836   8.0955 15.49563139208048"
iss = ephem.readtle(name, line1, line2)


# camera
cam = PiCamera()
cam.resolution = (1296,972)


# start time and actual time
start_time = dt.datetime.now()
now_time = dt.datetime.now()


def get_mag():
    
    '''
    Gets a reading of the magnetometer and calculates the magnetic field intensity.
    
    It returns axis x, y and z and tot magnetic field.
    '''
    
    mag = sh.get_compass_raw()

    x = round(mag['x'], 3)
    y = round(mag['y'], 3)
    z = round(mag['z'], 3)

    # magnetic field intensity
    tot_mag = math.sqrt(x*x + y*y + z*z)
    tot_mag = round(tot_mag, 3)
    
    return x, y, z, tot_mag


def get_latlon():
    
    '''
    Gets longitude and latitude of the ISS, converts them from DMS format to decimal, and write them to
    EXIF data (in DMS) for pictures taken by the Pi Camera.
    
    It returns longitude and latitude in degrees. 
    '''
    
    iss.compute() # Get the lat/long values from ephem

    long_value = [float(i) for i in str(iss.sublong).split(":")]
    # get long in degrees
    longitude = math.degrees(float(iss.sublong))
    longitude = round(longitude, 2)

    # store long to EXIF data
    if long_value[0] < 0:

        long_value[0] = abs(long_value[0])
        cam.exif_tags['GPS.GPSLongitudeRef'] = "W"
    else:
        cam.exif_tags['GPS.GPSLongitudeRef'] = "E"
    
    cam.exif_tags['GPS.GPSLongitude'] = '%d/1,%d/1,%d/10' % (long_value[0], long_value[1], long_value[2]*10)


    lat_value = [float(i) for i in str(iss.sublat).split(":")]
    # get lat in degrees
    latitude = math.degrees(float(iss.sublat))
    latitude = round(latitude, 2)

    # store lat to EXIF data
    if lat_value[0] < 0:

        lat_value[0] = abs(lat_value[0])
        cam.exif_tags['GPS.GPSLatitudeRef'] = "S"
    else:
        cam.exif_tags['GPS.GPSLatitudeRef'] = "N"

    cam.exif_tags['GPS.GPSLatitude'] = '%d/1,%d/1,%d/10' % (lat_value[0], lat_value[1], lat_value[2]*10)
    
    
    return latitude, longitude


def sort_land_ocean(lon, lat):
    
    '''
    Defines some polygons from the oceans coordinates and check whether the point tested is in
    either of them. If so, then the point is in ocean, else it is in land.
    
    It takes longitude and latitude as arguments and return the status (ocean or land)
    of the point.
    '''
    
    # oceans polygons coordinates (longitude, latitude)
    atlanticOcean = [(-24.6,68.5), (25.3,69.8), (5.7,61.4), (4.6,52.2), (-6.3,48.4),
                (-9.45,43.5), (-9.63,37.6), (-6.3,35.5), (-10.5,31.1), (-10.5,28.4),
                (-16.1,24.5), (-17.2,14.7), (-8.2,4.1), (6.3,3.6), (9.9,3.4),
                (9,-1.7), (13.8,-12.6), (11.7,-16.5), (14.5,-22.3), (16.1,-28.67),
                (18.9,-34.5), (18.9,-55.7), (-66,-55.7), (-68.5,-50.4), (-58.6,-39.3), (-48.1,-28.2),
                (-48.1,-25.7), (-41.6,-22.7), (-38.7,-17.4), (-39.5,-13.7), (-36.9,-12.5),
                (-34.9,-10.4), (-35.0,-5.5), (-50,-0.1), (-53,5.5), (-57.2,6.1),
                (-62.8,10.9), (-67.8,10.9), (-74.2,10.8), (-76.9,8.5), (-81.6,9.4),
                (-82.7,14), (-87.4,16.1), (-86.3,21.6), (-90.2,21.7), (-91.2,19.2),
                (-95.7,18.8), (-97.1,25.5), (-91.0,28.9), (-84,29.7), (-82.9,27.3),
                (-80.9,24.9), (-79.3,26.7), (-81.1,31.3), (-75.4,35.2), (-73.8,40.3),
                (-69.6,41.4), (-65.1,43.5), (-60,45.8), (-52.2,47.1), (-54.9,52.9),
                (-44.5,60.1), (-38.8,65.1)]
    
    indianOcean =  [(21.40,-34.15), (27.37,-33.71), (40.03,-15.61), (39.68,-3.50), (51.80,10.16), 
                    (58.84,22.26), (65.69,25.18), (71.32,19.83), (77.47,6.86), (80.24,12.53),
                    (80.90,15.85), (89.05,22.12), (91.38,22.08), (94.54,17.74), (94.02,16.02),
                    (97.00,16.82), (98.19,8.33), (100.78,3.18), (94.98,6.29), (105.0,-6.52),
                    (118.16,-9.26), (123.52,-11.25), (129.93,-11.08), (128.62,-14.51), (125.89,-3.57),
                     (118.51,-20.37), (113.06,-22.18), (115.26,-34.44), (123.52,-34.88), (130.99,-32.09),
                    (137.23,-36.59), (137.50,-66.47), (102.26,-65.79), (85.65,-66.22), (75.01,-69.50),
                    (69.04,-67.67), (54.18,-65.76), (37.48,-68.65)]

    # pacific ocean covers the two sides of a map, successive points have -179 and 179 as the longitude
    # we split it in East and West to evitate it being badly represented in xy plane
    pacificEast = [(149.9,-37.8),(153.9,-28.5),(143.2,-11.5),(152.1,-0.9),(127.9,5.7),
                    (122.9,23.8),(123.4,31),(128.9,33.7),(129.8,29.4),(141.6,35),
                    (142.8,41),(148,43.3),(144.6,45.5),(146.2,49.3),(144.9,54.2),
                    (136.8,55.2),(143.1,59.1),(153.7,59.2),(159.4,61.6),(160.3,60.5),
                    (161.4,60.3),(155.4,57),(156.6,50.3),(160.8,52.8),(164.1,55.8),
                    (163.8,58.1),(167.3,60.1),(170.7,59.8), (179.9,-77.1),
                    (166.4,-77.1), (173.8,-71.8), (142.9,-66.8), (146.9,-44.8)]

    pacificWest = [(-179.9,62.2),(-179.7,64.7),
                    (-177.3,65.3),(-173.6,63.4),(-166,62.2),(-165.8,60.9),(-168.4,60.4),
                    (-166.6,58.9),(-158.5,57.8),(-153.1,57),(-144.8,59.9),(-136.1,56.9),
                    (-131.7,51.9),(-125.2,48.4),(-124.5,44.6),(-124.4,40.7),(-117.6,32.7),
                    (-110.7,23.2),(-105.8,19.7),(-96.1,15.3),(-87.9,12.4),(-83.7,7.3),
                    (-78.7,6.1),(-80.2,0.9),(-82.2,-0.6),(-81.2,-6.3),(-76.7,-14.4),
                    (-70.4,-18.9),(-73.7,-36.7),(-76,-46.2),(-75.1,-53),(-73.4,-55.1),
                    (-66.6,-56.3),(-64.6,-55),(-59.6,-63.4),(-68.4,-65.7),(-75.8,-72.2),
                    (-98.6,-71.8),(-126.8,-73.2),(-146.8,-75.7),(-162.6,-78.4),(-179.9,-77.1)]

    p1 = path.Path(atlanticOcean)
    p2 = path.Path(indianOcean)
    p3 = path.Path(pacificEast)
    p4 = path.Path(pacificWest)
    
    lon = float(lon)
    lat = float(lat)
    
    target = [(lon, lat)]  # DO NOT change order, the points were taken as (lon, lat)
    
    result1 = p1.contains_points(target)
    result2 = p2.contains_points(target)
    result3 = p3.contains_points(target)
    result4 = p4.contains_points(target)
    
    # if target is in one of the polygons, it is in ocean
    if result1==True or result2==True or result3==True or result4==True: 
        return "Ocean"     
    else:
        return "Land"
    
    

# logging functions
def create_csv_file(data_file):
    
    "Create a new CSV file and add the header row."
    
    with open(data_file, 'w') as f:
        writer = csv.writer(f)
        header = ("Date/Time", "Lat", "Lon", "Status", "m_X", "m_Y", "m_Z", "m_TOT", "N Photo")
        writer.writerow(header)

def add_csv_data(data_file, data):
    
    "Add a row of data to the data_file CSV"
    
    with open(data_file, 'a') as f:
        writer = csv.writer(f)
        writer.writerow(data)
        
    
# initialise the CSV file
data_file = dir_path + "/data.csv"
create_csv_file(data_file) 

photo_counter = 0

# loop di -- tre ore
while (now_time < start_time + dt.timedelta(minutes=178)):
    try:
        #print("Facendo cose")
        
        logger.info("{} iteration {}".format(dt.datetime.now(), photo_counter))
        
        # take pictures and save them numembered with three digits
        img_name = "photo_"+ str(photo_counter).zfill(3)+".jpg"
        cam.capture(dir_path+"/"+img_name)
        
        
        # get remaining data
        x, y, z, tot_mag = get_mag()
        lat, lon = get_latlon()
        status = sort_land_ocean(lon, lat)
        
        # log data
        data = (dt.datetime.now(), lat, lon, status, x, y, z, tot_mag, photo_counter)
        add_csv_data(data_file, data)
        
        # update current time
        now_time = dt.datetime.now()
        # update counter
        photo_counter += 1
        
        sleep(10)
    
    except Exception as e:
        logger.error('{}: {})'.format(e.__class__.__name__, e))
        
#print("Finito!")


