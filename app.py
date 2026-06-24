#################################################################
# Etch-a-Sketch app                                             #
# create an array of points                                     #
# points are added when GPS is more than 1-5 meters apart       #
# TO-DO                                                         #
# + add the ability to download the drawing as a bmp            #
# + be able to change the colour with the click of a button     #
# + add the option to not link a point to make a gap            #
# + create a function to export data in GPX format              #
# + add option to delete previous drawing                       #
#################################################################

import app
import math
import os

from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
from system.hexpansion.util import get_app_by_vid_pid

class GGA:
    def __init__(self):
        self.Message_ID = '$GPGGA'
        self.UTC_Time = 0.0
        self.Latitude = 0.0
        self.NS_Indicator = 'X'
        self.Longitude = 0.0
        self.EW_Indicator = 'X'
        self.Position_Fix_Indicator = 0
        self.Satellites_Used = 0
        self.HDOP = 0.0
        self.MSL_Altitude = 0.0
        self.MSL_Altitude_Units = 'X'
        self.Geoid_Separation = 0.0
        self.Geoid_Separation_Units = 'X'
        self.Age_Of_Diff_Corr = 0
        self.Diff_Ref_Station_ID = 0

class RMC:
    def __init__(self):
        self.Message_ID = '$GPRMC'
        self.UTC_Time = 0
        self.Status = 'V'
        self.Latitude = 0.0
        self.NS_Indicator = 'X'
        self.Longitude = 0.0
        self.EW_Indicator = 'X'
        self.Speed_Over_Ground = 0.0
        self.Course_Over_Ground = 0.0
        self.Date = 0
        self.Magnetic_Variation = 0
        self.Magnetic_Variation_EW_Indicator = 'X'
        self.Mode = 'X'

class GPSSketcher(app.App):
    def __init__(self):
        self.gps = get_app_by_vid_pid(0x7CAB, 0xBEAC)

        self.last_position = None

        if self.gps:
            eventbus.on(
                self.gps.GPSEvent,
                self.handle_gps_event,
                self
            )
        else:
            print("GPS Hexpansion NOT found")

        self.button_states = Buttons(self)
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        eventbus.on(ButtonUpEvent, self._handle_buttonup, self)
        self.track = []
        self.last_sentence = None
        self.gga = GGA()
        self.rmc = RMC()
        MIN_DISTANCE = 5      # metres
        MAX_HDOP = 2.5
        MIN_SATS = 5
        stat = os.statvfs("/")
        free_bytes = stat[0] * stat[3]
        print(free_bytes)
        self.display_points = []
        self.screen_points = []

    def on_resume(self):
        print("resumed")
    
    def on_pause(self):
        print("paused")
    
    def _handle_buttondown(self, event: ButtonDownEvent):
        if BUTTON_TYPES["LEFT"] in event.button:
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            self.button_states.clear()

        if BUTTON_TYPES["DOWN"] in event.button:
            self.button_states.clear()

        if BUTTON_TYPES["CANCEL"] in event.button:
            self.button_states.clear()
            self.minimise()
    
    def _handle_buttonup(self, event: ButtonUpEvent):
        if BUTTON_TYPES["LEFT"] in event.button:
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            self.button_states.clear()

    def handle_gps_event(self, event):
        self.last_position = event.position
    
    def update(self, delta):
        pass

    def background_update(self, delta):
        if not self.gps:
            return

        if not self.gps.sentences:
            return

        sentence = self.gps.sentences[-1]

        if sentence != self.last_sentence:
            self.last_sentence = sentence
            if (gga := self.parseGGA(self.last_sentence)) is not None:
                self.gga = gga
            if (rmc := self.parseRMC(self.last_sentence)) is not None:
                self.rmc = rmc
            #print(f"self.gga.UTC_Time:{self.gga.UTC_Time}, self.rmc.UTC_Time:{self.rmc.UTC_Time}")
            if self.gga.Latitude > 0 and self.rmc.Latitude > 0:
                if len(self.track) == 0:
                    self.track.append([
                        self.nmea_to_decimal(self.gga.Latitude, self.gga.NS_Indicator),
                        self.nmea_to_decimal(self.gga.Longitude, self.gga.EW_Indicator),
                        self.gga.UTC_Time,
                        self.rmc.Date,
                        self.gga.HDOP,
                        self.gga.Satellites_Used,
                        0,
                        0
                    ])
                    self.collect_points()
                    self.build_pixel_list()  
                if (
                    self.gga.Position_Fix_Indicator > 0 and
                    self.gga.Satellites_Used >= 6 and
                    self.gga.HDOP < 1.2
                ):
                    
                    x,y = self.latlon_to_xy(self.track[-1][0], self.track[-1][1], self.nmea_to_decimal(self.gga.Latitude, self.gga.NS_Indicator), self.nmea_to_decimal(self.gga.Longitude, self.gga.EW_Indicator))
                    if abs(x) > 1 or abs(y) > 1:
                        self.track.append([
                            self.nmea_to_decimal(self.gga.Latitude, self.gga.NS_Indicator),
                            self.nmea_to_decimal(self.gga.Longitude, self.gga.EW_Indicator),
                            self.gga.UTC_Time,
                            self.rmc.Date,
                            self.gga.HDOP,
                            self.gga.Satellites_Used,
                            y,
                            x
                        ])
                        self.display_points.append(
                            (
                                self.nmea_to_decimal(self.gga.Latitude, self.gga.NS_Indicator),
                                self.nmea_to_decimal(self.gga.Longitude, self.gga.EW_Indicator)
                            )
                        )
                        self.build_pixel_list()
                        #print(self.track)
                    #else:
                    #    print(f"x:{x}, y:{y}, PFI:{self.gga.Position_Fix_Indicator}, Sats:{self.gga.Satellites_Used}, HDOP:{self.gga.HDOP}")
                    
                if len(self.track) > 10:
                    try:
                        os.listdir('/data/GPSSketcher')
                    except:
                        print("no folder, creating a new one")
                        os.mkdir('/data/GPSSketcher')
                    if not f"GPSlog.csv" in os.listdir('/data/GPSSketcher'):
                        print("file not found, creating a new one")
                        file = open(f"/data/GPSSketcher/GPSlog.csv",'w')
                        file.write("Latitude,Longitude,Time,Date,HDOP,Satellites,DeltaX,DeltaY\n")
                        file.close()
                    file = open(f"/data/GPSSketcher/GPSlog.csv",'a')
                    for trackpoint in self.track[:-1]:
                        file.write(f"{trackpoint[0]},{trackpoint[1]},{trackpoint[2]},{trackpoint[3]},{trackpoint[4]},{trackpoint[5]},{trackpoint[6]},{trackpoint[7]}\n")
                    file.close()
                    if self.track:
                        self.track = self.track[-1:]
                    print("successfully stored values to flash and cleared the local track")

    def draw(self, ctx):
        ctx.rgb(0, 0.2, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(0, 1, 0)

        if not self.gps:
            ctx.move_to(-90, 10).text("GPS Not Found")
            return
        
        # add a startup feature to start a new drawing or continue with the old

        if not self.last_position:
            ctx.move_to(-110, 10).text("Waiting For Fix")
            return
        
        ctx.rgb(0, 1, 0).begin_path()

        for i in range(1, len(self.screen_points)):
            x1, y1 = self.screen_points[i - 1]
            x2, y2 = self.screen_points[i]

            ctx.move_to(x1,y1)
            ctx.line_to(x2,y2)
        
        ctx.stroke()

    def build_pixel_list(self):
        if len(self.display_points) > 1:
            origin_lat = self.display_points[0][0]
            origin_lon = self.display_points[0][1]
        else:
            #print(f"not enough data points, len(self.display_points):{len(self.display_points)}")
            return

        #print(f"display_points:{self.display_points}")
        screen_W = 128
        screen_H = 128

        xy_points = []
        for point in self.display_points:

            x, y = self.latlon_to_xy(
                origin_lat,
                origin_lon,
                point[0],
                point[1]
            )

            xy_points.append((x, y))
        #print(f"xy_points:{xy_points}")

        xs = [p[0] for p in xy_points]
        ys = [p[1] for p in xy_points]

        min_x = min(xs)
        max_x = max(xs)

        min_y = min(ys)
        max_y = max(ys)

        width = max_x - min_x
        height = max_y - min_y

        #print(f"origin_lat:{origin_lat}, origin_lon:{origin_lon}, min_x:{min_x}, max_x:{max_x}, min_y:{min_y}, max_y:{max_y}, len(xy_points):{len(xy_points)}")
    
        if width != 0:
            scale_x = 235 / width
        else:
            scale_x = 235
        if height != 0:
            scale_y = 235 / height
        else:
            scale_y = 235

        scale = min(scale_x, scale_y)

        centre_x = (min_x + max_x) / 2
        centre_y = (min_y + max_y) / 2     

        #print(f"width:{width}, height:{height}, scale_x:{scale_x}, scale_y:{scale_y}, scale:{scale}, centre_x:{centre_x}, centre_y:{centre_y}")

        self.screen_points = []

        for x, y in xy_points:

            sx = int((x - centre_x) * scale)
            sy = int((y - centre_y) * scale)

            self.screen_points.append((sx, sy))

        #print(f"screen_points:{self.screen_points}")

    def collect_points(self):
        if len(self.display_points) == 0:
            try:
                with open(f"/data/GPSSketcher/GPSlog.csv", "r") as f:
                    f.readline()
                    for line in f:
                        lat, lon, time, date, HDOP, sats, x, y = line.strip().split(",")
                        self.display_points.append(
                            (
                                float(lat),
                                float(lon)
                            )
                        )
            except:
                print("collect_points failed")
                return
               


    def latlon_to_xy(self, previousLat, previousLon, currentLat, currentLon):
        R = 111320  # meters per degree

        dlat = previousLat - currentLat
        dlon = previousLon - currentLon

        x = dlon * R * math.cos(math.radians(currentLat))   # East
        y = dlat * R                                        # North

        return x, y
    
    def nmea_to_decimal(self,coord,direction):
        degrees = int(coord / 100)
        minutes = coord - (degrees * 100)
        decimal = degrees + (minutes / 60)

        if direction in ("S", "W"):
            decimal = -decimal
        
        return decimal

    def parseGGA(self,last_sentence):
        
        if not last_sentence.startswith("$GPGGA"):
            return None
       
        fields = last_sentence.split(",")

        gga = GGA()
        try:
            gga.Message_ID = fields[0]
            gga.UTC_Time = float(fields[1]) if fields[1] else 0.0
            gga.Latitude = float(fields[2]) if fields[2] else 0.0
            gga.NS_Indicator = fields[3] if fields [3] else 'X'
            gga.Longitude = float(fields[4]) if fields[4] else 0.0
            gga.EW_Indicator = fields[5] if fields [5] else 'X'
            gga.Position_Fix_Indicator = int(fields[6]) if fields[6] else 0
            gga.Satellites_Used = int(fields[7]) if fields[7] else 0
            gga.HDOP = float(fields[8]) if fields[8] else 0.0
            gga.MSL_Altitude = float(fields[9]) if fields[9] else 0.0
            gga.MSL_Altitude_Units = fields[10] if fields[10] else 'X'
            gga.Geoid_Separation = float(fields[11]) if fields[11] else 0.0
            gga.Geoid_Separation_Units = fields[12] if fields[12] else 'X'
            gga.Age_Of_Diff_Corr = fields[13] if fields[13] else 0
            gga.Diff_Ref_Station_ID = fields[14] if fields[14] else 0
            return gga
        except:
            return None

    def parseRMC(self,last_sentence):
        
        if not last_sentence.startswith("$GPRMC"):
            return None
       
        fields = last_sentence.split(",")
        #print(fields)
        rmc = RMC()
        try:
            rmc.Message_ID = fields[0]
            rmc.UTC_Time = float(fields[1]) if fields[1] else 0.0
            rmc.Status = fields[2] if fields[2] else 'X'
            rmc.Latitude = float(fields[3]) if fields[3] else 0.0
            rmc.NS_Indicator = fields[4] if fields [4] else 'X'
            rmc.Longitude = float(fields[5]) if fields[5] else 0.0
            rmc.EW_Indicator = fields[6] if fields [6] else 'X'
            rmc.Speed_Over_Ground = float(fields[7]) if fields[7] else 0.0
            rmc.Course_Over_Ground = float(fields[8]) if fields[8] else 0.0
            rmc.Date = int(fields[9]) if fields[9] else 0
            rmc.Magnetic_Variation = float(fields[10]) if fields[10] else 0.0
            rmc.Magnetic_Variation_EW_Indicator = fields[11] if fields[11] else 'X'
            rmc.Mode = fields[12] if fields[12] else 'X'
            return rmc
        except:
            #print("rmc failed")
            return None

__app_export__ = GPSSketcher