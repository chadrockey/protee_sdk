import json
import os
import random
import re
import socket
import sys
import threading
import time

# Implements a Python interface to the Protee SDK
# https://csc.protee-united.com/hc/en-us/articles/216279108-ProTee-Golf-2-0-SDK-API-v1-0

# Must use the ProTee Golf Interface to communicate

class ProteeSDK:
    def __init__(self, server_ip=None, buffer_size=1024):
        self.stay_connected = True
        self.s = None
        self.server_ip = server_ip
        self.buffer_size = buffer_size
        self.received_data = None
        self.last_received_data_time = None
        self.ball_launch_counter = 1

        # Configuration
        self.config = {}
        self.read_config_file()

        if self.server_ip is None:
            self.server_ip = self.config.get('ip_address', 'localhost')

        # Data returned from TGC
        self._club = "DR"
        self._distance_to_flag = 0.0
        self._surface = "Tee"
        self._hand = "right"
        self._playername = ""
        self._coursename = ""
        self._tourname = ""

        self.recv_thread = threading.Thread(target=self.recv_data_thread, daemon=True).start()

    def __del__(self):
        if self.s:
            self.s.close()

    def is_connected(self):
        if self.s is None:
            return False
        if self.last_received_data_time is None:
            return False
        return True

    def disconnect(self):
        self.stay_connected = False

    @property
    def club(self):
        return self._club
    
    @property
    def distance_to_flag(self):
        return self._distance_to_flag

    @property
    def surface(self):
        return self._surface

    @property
    def hand(self):
        return self._hand
    
    @property
    def playername(self):
        return self._playername
    
    @property
    def coursename(self):
        return self._coursename
    
    @property
    def tourname(self):
        return self._tourname

    def read_config_file(self):
        default_config = f'''[TGC]
IP=localhost
Driver Boost=0
Wood Boost=0
Iron Boost=0
Wedge Boost=0
Putter Boost=0'''

        # Check if a config file already exists
        tgc_config_file_name = 'TGCConfig.txt'
        if os.path.isfile(tgc_config_file_name):
            with open(tgc_config_file_name, 'r') as config_file:
                for line in config_file:
                    if 'IP' in line:
                        self.config["ip_address"] = line[3:].rstrip()
                    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                    if len(numbers) == 1:
                        if "Driver" in line:
                            self.config["driver_boost"] = float(numbers[0])
                        elif "Wood" in line:
                            self.config["wood_boost"] = float(numbers[0])
                        elif "Iron" in line:
                            self.config["iron_boost"] = float(numbers[0])
                        elif "Wedge" in line:
                            self.config["wedge_boost"] = float(numbers[0])
                        elif "Putter" in line:
                            self.config["putter_boost"] = float(numbers[0])
        else:
            # Write a new configuration file, use default boosts
            with open(tgc_config_file_name, 'w') as config_file:
                config_file.write(default_config)

            self.config["driver_boost"] = 0.0
            self.config["wood_boost"] = 0.0
            self.config["iron_boost"] = 0.0
            self.config["wedge_boost"] = 0.0
            self.config["putter_boost"] = 0.0

    def get_current_drag_based_on_boost(self):
        default_drag = 1.0 # Default value

        current_boost_value = 0.0
        if 'DR' in self.club:
            current_boost_value = self.config.get("driver_boost", 0.0)
        elif len(self.club) > 0 and 'W' in self.club[0]:
            current_boost_value = self.config.get("wood_boost", 0.0)
        elif 'I' in self.club:
            current_boost_value = self.config.get("iron_boost", 0.0)
        elif len(self.club) > 1 and 'W' in self.club[1]:
            current_boost_value = self.config.get("wedge_boost", 0.0)
        elif 'PT' in self.club:
            current_boost_value = self.config.get("putter_boost", 0.0)

        desired_boost_value = default_drag - current_boost_value / 100.0
        clamped_boost_value = max(min(desired_boost_value, 2.0), 0.00)

        return clamped_boost_value

    def print_tgc_info(self):
        print("Club: " + self.club)
        print("Distance to Flag: " + str(self.distance_to_flag))
        print("Surface: " + self.surface)
        print("Hand: " + self.hand)
        print("Player Name: " + self.playername)
        print("Course Name: " + self.coursename)
        print("Tour Name: " + self.tourname)

    def parse_returned_data(self, ret_json):
        self._club = ret_json['data'].get('club_small', "DR")
        self._distance_to_flag = float(ret_json['data'].get('distance_to_flag', 0.0))
        self._surface = ret_json['data'].get('surface', "Tee")
        self._hand = ret_json['data'].get('handed_player', "right")
        self._playername = ret_json['data'].get('playerName', "")
        self._coursename = ret_json['data'].get('courseName', "")
        self._tourname = ret_json['data'].get('tourName', "")

    def recv_data_thread(self):
        # Outer loop keeps connection to ProTee interface alive
        while self.stay_connected:
            try:
                self.s = socket.create_connection((self.server_ip, 9090), timeout=1.0)

                # Set socket timeout
                self.s.settimeout(2.0)

                # Inner loop recieves game state data
                while self.stay_connected:
                    try:
                        if self.last_received_data_time is not None and time.time() - self.last_received_data_time > 2.5:
                            self.last_received_data_time = None
                            break # Data timeout, try reconnecting
                        if self.s:
                            data = self.s.recv(self.buffer_size)
                            if data:
                                data = data.decode('utf-8')
                                # Sometimes we get more than once sentence per return, they are split by \r\n
                                for d in data.splitlines():
                                    self.received_data = json.loads(d)
                                    self.parse_returned_data(self.received_data)
                                    self.last_received_data_time = time.time()

                    except json.decoder.JSONDecodeError:
                        print("Could not decode returned data")
                        print(str(data))
                    except (BlockingIOError, ConnectionAbortedError): # Broken socket
                        break

            except (socket.timeout, TimeoutError, ConnectionRefusedError, ConnectionResetError): # Connection not yet available
                print("Is ProTee Interface Open?")

            # Something went wrong or we're exiting.  Close the socket.
            self.s = None

    # Returns a json object for the game status
    def get_game_status(self):
        return self.received_data

    def launch_ball(self, ballspeed, ballpath, launchangle, backspin, sidespin,
                    clubspeed=None, clubface=None, clubpath=None, sweetspot=None, drag=None, carry=None, repeat=False):
        try:
            # Full example JSON from documentation
            #shot_json = json.loads('{"protocol":"PROTEE", "info":{"device":"EXT","units":"MPH"},"data":{"counter":"1", "shotnumber":"1","clubspeed":"126","clubface":"4.45", "clubpath":"-5.51", \
            #                         "sweetspot":"0","ballspeed":"11.26", "ballpath":"5.24","launchangle":"45.63","backspin":"1820", "sidespin":"-1993","drag":"0.09","carry":"3.65"}}')

            # Minimum JSON for interface.  Don't add optional fields unless specified
            shot_json = json.loads('{"protocol":"PROTEE", "info":{"device":"EXT","units":"MPH"},"data":{"counter":"0", "shotnumber":"0","ballspeed":"0.0", "ballpath":"0.0","launchangle":"0.0","backspin":"0", "sidespin":"0"}}')

            # Shot counts must increase
            if not repeat:
                self.ball_launch_counter += 1
            else:
                clubspeed = launchangle
                clubface = launchangle
            shot_json['data']['counter'] = str(self.ball_launch_counter)
            shot_json['data']['shotnumber'] = str(self.ball_launch_counter)

            # Required data
            shot_json['data']['ballspeed'] = str(ballspeed)
            shot_json['data']['ballpath'] = str(ballpath)
            shot_json['data']['launchangle'] = str(launchangle)
            shot_json['data']['backspin'] = str(backspin)
            shot_json['data']['sidespin'] = str(sidespin)

            # Optional data
            if clubspeed:
                shot_json['data']['clubspeed'] = str(clubspeed)
            if clubface:
                # Positive club face is closed "club face to ball path?"
                # Face relative to path is negative club face
                shot_json['data']['clubface'] = str(clubface)
            if clubpath:
                # Positive club path is "out to in" club path to target?
                shot_json['data']['clubpath'] = str(clubpath)
            if sweetspot:
                shot_json['data']['sweetspot'] = str(sweetspot)
            if drag is None:
                drag = self.get_current_drag_based_on_boost()
            shot_json['data']['drag'] = str(drag)
            if carry:
                shot_json['data']['carry'] = str(carry)

            # Send data, must remove whitespace
            if self.s:
                print(shot_json)
                self.s.send(json.dumps(shot_json, separators=(',', ':')).encode('utf-8'))
                return True
        except OSError:
            pass

        return False

# Main is a simple example that shows how to use the library and send random shots
if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Default aeguments
        psdk = ProteeSDK()
    elif len(sys.argv) == 2:
        # Specify ip
        psdk = ProteeSDK(server_ip=sys.argv[1])

    last_shot_time = 0.0
    print("Starting random launches")
    while True:
        time.sleep(0.1)

        dt = time.time() - last_shot_time
        if dt > 20.0:
            # Required values
            # launch_status = psdk.launch_ball(random.uniform(20, 180), random.uniform(-7, 7), random.uniform(3, 45), random.uniform(1500, 10000), random.uniform(-500, 500))

            # Some Optional values
            # Not sure if drag, carry, or sweetspot are ever really needed
            launch_status = psdk.launch_ball(random.uniform(20, 180), random.uniform(-7, 7), random.uniform(3, 45), random.uniform(1500, 10000), random.uniform(-2500, 2500),
                             clubspeed=random.uniform(20, 120), clubface=random.uniform(-7, 7), clubpath=random.uniform(-7, 7))

            if launch_status:
                print("New launch after " + str(dt) + " seconds.")
                last_shot_time = time.time()
