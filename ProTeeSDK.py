import json
import random
import socket
import sys
import threading
import time

# Implements a Python interface to the Protee SDK
# https://csc.protee-united.com/hc/en-us/articles/216279108-ProTee-Golf-2-0-SDK-API-v1-0

# Must use the ProTee Golf Interface to communicate

class ProteeSDK:
    def __init__(self, server_ip='127.0.0.1', buffer_size=1024):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((server_ip, 9090))
        self.buffer_size = buffer_size

        self.received_data = None
        self.recv_thread = threading.Thread(target=self.recv_data_thread, daemon=True).start()

        self.ball_launch_counter = 1

    def __del__(self):
        self.s.close()

    def recv_data_thread(self):
        while True:
            data = self.s.recv(self.buffer_size)
            self.received_data = json.loads(data)

    # Returns a json object for the game status
    def get_game_status(self):
        return self.received_data

    def launch_ball(self, ballspeed, ballpath, launchangle, backspin, sidespin,
                    clubspeed=None, clubface=None, clubpath=None, sweetspot=None, drag=None, carry=None):
        # Full example JSON from documentation
        #shot_json = json.loads('{"protocol":"PROTEE", "info":{"device":"EXT","units":"MPH"},"data":{"counter":"1", "shotnumber":"1","clubspeed":"126","clubface":"4.45", "clubpath":"-5.51", \
        #                         "sweetspot":"0","ballspeed":"11.26", "ballpath":"5.24","launchangle":"45.63","backspin":"1820", "sidespin":"-1993","drag":"0.09","carry":"3.65"}}')

        # Minimum JSON for interface.  Don't add optional fields unless specified
        shot_json = json.loads('{"protocol":"PROTEE", "info":{"device":"EXT","units":"MPH"},"data":{"counter":"0", "shotnumber":"0","ballspeed":"0.0", "ballpath":"0.0","launchangle":"0.0","backspin":"0", "sidespin":"0"}}')

        # Shot counts must increase
        shot_json['data']['counter'] = str(self.ball_launch_counter)
        shot_json['data']['shotnumber'] = str(self.ball_launch_counter)
        self.ball_launch_counter += 1

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
            shot_json['data']['clubface'] = str(clubface)
        if clubpath:
            shot_json['data']['clubpath'] = str(clubpath)
        if sweetspot:
            shot_json['data']['sweetspot'] = str(sweetspot)
        if drag:
            shot_json['data']['drag'] = str(drag)
        if carry:
            shot_json['data']['carry'] = str(carry)

        # Send data, must remove whitespace
        self.s.send(json.dumps(shot_json, separators=(',', ':')).encode('utf-8'))

# Main is a simple example that shows how to use the library and send random shots
if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Default aeguments
        psdk = ProteeSDK()
    elif len(sys.argv) == 2:
        # Specify ip
        psdk = ProteeSDK(server_ip=sys.argv[1])

    last_shot_time = 0.0
    while True:
        if time.time() - last_shot_time > 10.0:
            last_shot_time = time.time()
            # Required values
            #psdk.launch_ball(random.uniform(20, 180), random.uniform(-7, 7), random.uniform(3, 45), random.uniform(1500, 10000), random.uniform(-500, 500))

            # Some Optional values
            # Not sure if drag, carry, or sweetspot are ever really needed
            psdk.launch_ball(random.uniform(20, 180), random.uniform(-7, 7), random.uniform(3, 45), random.uniform(1500, 10000), random.uniform(-500, 500),
                             clubspeed=random.uniform(20, 120), clubface=random.uniform(-7, 7), clubpath=random.uniform(-7, 7))
