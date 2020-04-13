"""
Python Radio control for Universum Python Radio

Please find the following external controls in these classes:

ChannelSwitch: KY040
Volume: VolumeControl
LED: Blinker
SoundPlayer: Player

KY040 Python Class
Martin O'Hanlon
stuffaboutcode.com
Additional code added by Conrad Storz 2015 and 2016
"""
import threading
import RPi.GPIO as GPIO
from time import sleep
import random
from subprocess import Popen, call, check_output
import re
import os
import signal
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import json
import requests
import datetime
from lxml import html
import pylast
from pylast import NetworkError, WSError, MalformedResponseError
import calendar
from pytz import timezone


class LastFMRadioScrobble():
    """ A class to derive basic connectivities with
    the last.fm API
    On init it connects to the last.fm API with a session key
    Without a session key it will cause a WSError

    Attributes:
        network: `pylast.LastFMNetwork` connection
        error: `string` to describe the errors

    :param network:  `pylast.LastFMNetwork` connection
    :param doc: Dictionary containing `api`, `api_secret`, `user`, `password` to connect with last.fm API
    """

    def __init__(self, network=None, doc=None):

        if network is None:
            try:
                self.network = pylast.LastFMNetwork(api_key=doc['api'], api_secret=doc['api_secret'],
                                                    username=doc['user'], password_hash=doc['password'])
                self.error = None
            except WSError as e:
                self.network = None
                self.error = "LastFM Connection: " + str(e) + "\n"
        else:
            self.network = network

    def scrobble_from_json(self, in_dict=None, indeces=None, has_timestamp=True):
        """From a json of Songs and a list of indeces scrobble songs to the last.fm API

        This uses pylast.scrobble_many to simply scrobbe a list of songs from a jsonstring
        that contains these songs and a list of indeces which songs to take from that list

        :param jsonstring: A json put into a string. the json was compiled by a Songgetter.get_tracklist function

        :param indeces: A list of integers telling which elements to take from the songlist and scrobble them

        :return: The list of songs as "Artist - Title - Timestamp" to be displayed in the app
        """
        if in_dict is None:
            in_dict = [{
                "artist": "No Artist",
                "title": "No Title"
            }]
        if indeces is None:
            indeces = list()

        if self.network is not None:
            data_list = in_dict

            try:
                data_list[indeces[0]]["timestamp"]
            except (KeyError, TypeError):
                has_timestamp = False

            if has_timestamp:
                tracklist = [{"title": data_list[index]["title"],
                              "artist": data_list[index]["artist"],
                              "timestamp": data_list[index]["timestamp"]}
                             for index in indeces]
            else:
                tracklist = [{"title": data_list[index]["title"],
                              "artist": data_list[index]["artist"],
                              "timestamp": datetime.datetime.now()}
                             for index in indeces]
            try:
                self.network.scrobble_many(tracks=tracklist)

                if has_timestamp:
                    scrobbling_list = [" - ".join([
                        data_list[index]["artist"],
                        data_list[index]["title"],
                        datetime.datetime.fromtimestamp(int(
                            data_list[index]["timestamp"])
                        ).strftime('%Y-%m-%d %H:%M')
                    ]) for index in indeces]
                else:
                    scrobbling_list = [" - ".join([
                        data_list[index]["artist"],
                        data_list[index]["title"]]) for index in indeces]
            except (WSError, NetworkError, KeyError, MalformedResponseError, TypeError) as d:
                self.error = "LastFM Scrobble Error:" + str(d)
                scrobbling_list = False

            return scrobbling_list

    def has_error(self):
        return self.error is not None


class CurrentChannel:
    """Class for currently playing channel

    Attributes:
        id: `string` describing the channel ID
        radio: `string` giving the radio channel name
        song: `string` describing the currently playing song
        json_file: `string` where to dump this information to

    """

    def __init__(self, radio=None, song=None, id=1, json_file=''):
        self.id = id
        self.radio = radio
        self.song = song
        self.json_file = json_file

    def write_json(self):
        """ Dump the information to drive

        Returns: nth

        """
        with open(self.json_file, 'w') as f:
            json.dump({
                'id': self.id,
                'radio': self.radio,
                'song': self.song
            }, f)

    def set_song(self, song):
        """ Setter for `song` attribute

        Args:
            song: `string` describing the currently playing song

        Returns:

        """
        self.song = song


class SongGetter:
    """Class to handle songs from channels

    Attributes:
        url: OnlineRadioBox Url to find out which song is playing - needs to be of type playlist
        stationname: Any `String` describing the name of the currently playing radio station. This
          will only be used in case no song was detected.
        tracklist: Array of tracks derived from OnlineRadioBox
        error: Any kind of error should be stored as a `string`

    """

    def __init__(self, url="", stationname="none"):
        self.url = url
        self.stationname = stationname
        self.tracklist = []
        self.error = None

    def get_tracklist(self):
        """ Derive tracklist from URL

        This function gets the HTML content of the OnlineRadioBox URL and crawls it
        for the currently playing song. The song will be handed over to an
        array with one dict element.

        The array gets stored into `self.tracklist`. There the dictionary needs to contain
        `title`, `artist`, `timestamp` where the timestamp is given as
        `((datetime.datetime.now()) - datetime.datetime(1970, 1, 1)).total_seconds()`

        Returns:

        """
        self.error = None
        now = (datetime.datetime.now()) - datetime.datetime(1970, 1, 1)

        try:
            page = requests.get(self.url)
            webpage = html.fromstring(page.content)

            string = webpage.xpath('//table[@class="tablelist-schedule"]//tbody//tr[1]//td[2]//text()')[0].split(
                ' - ', 1)
            if len(string) == 1:
                string = webpage.xpath('//table[@class="tablelist-schedule"]//tbody//tr[1]//td[2]//text()')[
                    0].split(' von ', 1)
                if len(string) == 1:
                    artist = self.stationname
                    track = string
                    if isinstance(track, list):
                        track = track[0]
                else:
                    artist = string[1][0]
                    track = string[0][0]
            else:
                artist = string[0]
                track = string[1]

            self.tracklist = [{"title": track,
                               "artist": artist,
                               "timestamp": now.total_seconds()}]
        except:
            self.error = "OnlineRadioBox Link does not work: " + self.url
            self.tracklist = [{"title": "try",
                               "artist": "catch",
                               "timestamp": now.total_seconds()}]


class ChannelWriter:
    """Log class for current channel

    This class upon being started will check the last song for the current channel
    by the SongGetter class
    The song gets written into the `current_channel_json`
    If a song was received, it will get scrobbled to last.fm.
    In case of any error during this process, the error will be written into the `logfile`

    Attributes:
        channel_dict: Dictionary of current channel containing the `onlineradiobox` attribute to
           receive the song
        last_fm_doc: Dictionary with the fields 'api', 'api_secret', 'user', 'password'
        _running: True/False whether this is started already and checks for new song every 15 sec
        logfile: .txt file to log errors
        song: string containg the last played song
        sleep_count: Check if 15 sec are over
        last_fm_scrobbler: LastFMRadioScrobble object - scrobble song
        songgetter: SongGetter object - receive song
        channel: CurrentChannel object - write song to disk
        current_channel_json: `json` file on disk to store current channel
    """

    def __init__(self, channel_dict=None, last_fm_doc=None, logfile="", current_channel_json=''):
        if last_fm_doc is None:
            last_fm_doc = {}
        self.channel_dict = channel_dict
        self.last_fm_doc = last_fm_doc
        self._running = False
        self.song = "try"
        self.logfile = logfile
        self.sleep_count = 0
        self.last_fm_scrobbler = None
        self.songgetter = None
        self.channel = None
        self.current_channel_json = current_channel_json

    def start(self):
        """
        Run a loop to update channel info and scrobble songs

        Returns: A While loop that tries every 20 seconds to derive the currently playing song. If there
        is a song, the song will be sent to last.fm. In case the channel was changed by the user, the
        information will be updated in the `self.channel` item.

        """
        self.last_fm_scrobbler = LastFMRadioScrobble(doc=self.last_fm_doc)
        self.songgetter = SongGetter(url=self.channel_dict['onlineradiobox'],
                                     stationname=self.channel_dict['name'])
        self.channel = CurrentChannel(
            radio=self.channel_dict['name'],
            id=self.channel_dict['id'],
            song="",
            json_file=self.current_channel_json
        )
        self.channel.write_json()
        while self._running:
            sleep(0.05)
            if self.sleep_count > 300:
                self.scrobble()
                self.channel.write_json()
                self.sleep_count = 0
            self.sleep_count = self.sleep_count + 1

    def set_running(self):
        sleep(0.02)
        self._running = True

    def is_running(self):
        return self._running

    def stop(self):
        self._running = False

    def scrobble(self):
        """
        Scrobble the song using a LastFMRadioScrobble class

        this function derives the current song from the Songgetter. `self.songgetter`
        Afterwards, it tries to scrobble this song to last.fm using a LastFMRadioScrobble class item
        that is stored in `self.last_fm_scrobbler`.

        Returns: In case of a successful scrobble it prints the song into the console. Else it writes
        whatever error occured into the `self.errorlog`

        """
        self.songgetter.get_tracklist()
        if self.songgetter.error is None:
            if self.songgetter.tracklist[0]["title"] != self.song and self.songgetter.tracklist[0]["title"] != "try":
                self.song = self.songgetter.tracklist[0]["title"]
                try:
                    song_playing = self.songgetter.tracklist[0]["artist"] + ' - ' + self.songgetter.tracklist[0][
                        "title"]
                    self.channel.set_song(song_playing)
                except TypeError as e:
                    with open(self.logfile, 'a') as f:
                        f.write('OnlineRadioBox Error:' + str(e))
                        for item in self.songgetter.tracklist:
                            f.write("%s\n" % item)
                        f.write("\n")

                scrobble_info = self.last_fm_scrobbler.scrobble_from_json(in_dict=self.songgetter.tracklist,
                                                                          indeces=[0],
                                                                          has_timestamp=True)

                if self.last_fm_scrobbler.has_error():
                    with open(self.logfile, 'a') as f:
                        f.write(self.last_fm_scrobbler.error)
                        f.write("\n")
                else:
                    print(scrobble_info)
        else:
            with open(self.logfile, 'a') as f:
                f.write(self.songgetter.error)
                f.write("\n")


class VolumeControl:
    """Potentionmeter controller

    Tutorial found at:
      https://learn.adafruit.com/reading-a-analog-in-and-controlling-audio-volume-with-the-raspberry-pi?view=all

    This class takes a SCK-MISO-MOSI controller from adafruit to digitalize a potentionmeter via a MCP3008 chip

    The setup was performed excalty as written in the tutorial, except the 3.3v and GRND pins

    Instead of controlling the volume directly, alsa-mixer is used

    Attributes:
        _running: Whether loop is started
        last_read: Last read value
        tolerance: to keep from being jittery we'll only change
        mcp: MCP3008 controller
        chan0: Analog Converter
    """

    def __init__(self, last_read=0, tolerance=250):
        self._running = False
        self.last_read = last_read  # this keeps track of the last potentiometer value
        self.tolerance = 250  # to keep from being jittery we'll only change
        spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

        # create the cs (chip select)
        cs = digitalio.DigitalInOut(board.D22)

        # create the mcp object
        self.mcp = MCP.MCP3008(spi, cs)

        # create an analog input channel on pin 0
        self.chan0 = AnalogIn(self.mcp, MCP.P0)

    def remap_range(self, value, left_min, left_max, right_min, right_max):
        """
        this remaps a value from original (left) range to new (right) range
        Figure out how 'wide' each range is

        :param value: input val
        :param left_min: old min
        :param left_max: old max
        :param right_min: new min
        :param right_max: new max
        :return:
        """
        left_span = left_max - left_min
        right_span = right_max - right_min

        # Convert the left range into a 0-1 range (int)
        valueScaled = int(value - left_min) / int(left_span)

        # Convert the 0-1 range into a value in the right range.
        return int(right_min + (valueScaled * right_span))

    def start(self):
        """set volume

        controls the `sudo amixer sset "Digital" {volume}% > /dev/null'` command
        and sets the volume to the SCP reader's current value

        :return:
        """
        while self._running:
            # we'll assume that the pot didn't move
            trim_pot_changed = False

            # read the analog pin
            trim_pot = self.chan0.value

            # how much has it changed since the last read?
            pot_adjust = abs(trim_pot - self.last_read)

            if pot_adjust > self.tolerance:
                trim_pot_changed = True

            if trim_pot_changed:
                # convert 16bit adc0 (0-65535) trim pot read into 0-100 volume level
                set_volume = self.remap_range(trim_pot, 0, 65535, 0, 112)

                # set OS volume playback volume
                # print('Volume = {volume}%'.format(volume=set_volume))
                set_vol_cmd = 'sudo amixer sset "Digital" {volume}% > /dev/null' \
                    .format(volume=set_volume)
                os.system(set_vol_cmd)

                # save the potentiometer reading for the next loop
                self.last_read = trim_pot
            sleep(0.025)

    def is_running(self):
        return self._running

    def set_running(self):
        self._running = True

    def stop(self):
        self._running = False


class Player:
    """Play MP3s

    This class hosts a `process` that runs `omxplayer` with the
    desired .mp3 file upon start.

    On stop it will kill the process

    Attributes:
        process: subprocess.Popen process object
        mp3: string with the link of the mp3
        _running: True/False whether it was started
        errorlog: .txt file to write any occuring errors to

    """

    def __init__(self, mp3, errorlog="/tmp/log.txt"):
        self.process = None
        self.mp3 = mp3
        self._running = False
        self.errorlog = errorlog

    def start(self):
        self.set_running()
        try:
            self.process = Popen(['omxplayer', "-o", "alsa", self.mp3], preexec_fn=os.setsid)
        except Exception as e:
            print('Player not started')
            with open(self.errorlog, 'a') as f:
                f.write('Player Start Error: ' + self.mp3)
                f.write(str(e))
                f.write("\n")

    def stop(self):
        """Kill current player

        :return:
        """
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except:
            with open(self.errorlog, 'a') as f:
                f.write('Player Stop Error: ' + self.mp3)
            print("Killing of a Player not succesful")
        self._running = False

    def is_running(self):
        return self._running

    def set_running(self):
        self._running = True


class NoisePlayer(Player):
    """Player attached to fixed MP3

    Uses `01-White-Noise-10min` or `03-White-Noise-10min` from directory
    `/home/pi/share/radioflask/` to play noise in between channels
    """

    def __init__(self):
        noise = random.randrange(1, 3, 2)
        super().__init__(mp3='/home/pi/share/radioflask/0' + str(noise) + '-White-Noise-10min.mp3')

    def stop(self):
        super().stop()


class Blinker:
    """ LED Blinking

    This does 2 things:
        1: upon start it lets an LED blink by switching ON/OFF
        2. upon start a NoisePlayer object is started in a separate thread

    Attributes:
            ledpin: the GPIO Pin ID of the LED
            noise: A NoisePlayer object to play Noise
            t1: Thread for the NoisePlayer
            _running: whether the start was activated
    """

    def __init__(self, ledpin):
        self.ledpin = ledpin
        GPIO.setup(ledpin, GPIO.OUT)
        self.noise = NoisePlayer()
        self.t1 = None
        self._running = False

    def start(self):
        # Start NoisePlayer in separate thread
        if not self.noise.is_running():
            if self.t1 is not None:
                if not self.t1.is_alive():
                    self.t1 = threading.Thread(target=self.noise.start)
                    self.t1.start()
            else:
                self.t1 = threading.Thread(target=self.noise.start)
                self.t1.start()

        # Let the LED blink
        while self._running:
            sleep(0.05)
            self.on()
            sleep(0.05)
            self.off()

    def set_running(self):
        sleep(0.02)
        self._running = True

    def is_running(self):
        return self._running

    def stop(self):
        if self.noise is not None:
            self.noise.stop()
        if self.t1 is not None:
            self.t1.join()
        self._running = False

    def on(self):
        GPIO.output(self.ledpin, False)

    def off(self):
        GPIO.output(self.ledpin, True)


class KY040:
    """Rotary switch and Radio Management class

    Attributes:
        lastfm_dict: Dictionary with the fields 'api', 'api_secret', 'user', 'password'
        clockPin: GPIO number of clk pin of the Rotary switch
        dataPin: GPIO number of the dt pin of the Rotary switch
        switchPin: GPIO number of the switch of the Rotary switch
        ledpin: GPIO number of the LED

        rotaryCallback: Function to handle messages upon pin change
        switchCallback: Function to handle button press
        errorlog: file location of a `txt` file containing the error log
        current_channel_json: location of a `json` file containing the current channel and song

        absolute: Position of the Rotary switch (not exakt, just relative)
        channels: list/array of positions where channels can be located
        channel_dicts: array of channel dictionaries

        led: Blinker object
        t1: threading.Thread object to handle the led

        radio: A Player object that should run the current radio channel contained in
          `self.channel_dicts[self.absolute]['stream']`
        t2: threading.Thread object to handle the `start` method of the radio

        volume: A VolumeControl object
        t_volumne: A threading.Thread object where the Volume controller can run in parallel

        channel_writer: A ChannelWriter object to write current channel infos to disk
        t_writer: A threading.Thread object to handle the start of the channel_writer

    """
    CLOCKWISE = 0
    ANTICLOCKWISE = 1
    DEBOUNCE = 200

    def __init__(self, clockPin, dataPin, switchPin, ledpin, rotaryCallback, switchCallback, channeldict,
                 errorlog="/home/pi/share/radioflask/static/test/errorlog.txt",
                 lastfm_dict=None,
                 current_channel_json=''
                 ):

        # Start Error LOG by moving old log
        nowtime = str(datetime.datetime.now().today().isoformat())
        try:
            os.rename(errorlog, errorlog.replace("errorlog",
                                                 "old_errorlog" + nowtime[0:10] + "-" + nowtime[11:13] + nowtime[
                                                                                                         14:16] + nowtime[
                                                                                                                  17:19]))
        except:
            print("no new errorlog")
        with open(errorlog, "w") as f:
            f.write("start: ")
            f.write(nowtime)
            f.write("\n")

        # persist values
        if lastfm_dict is None:
            lastfm_dict = {}
        self.lastfm_dict = lastfm_dict
        self.clockPin = clockPin
        self.dataPin = dataPin
        self.switchPin = switchPin
        self.rotaryCallback = rotaryCallback
        self.switchCallback = switchCallback
        self.errorlog = errorlog
        self.current_channel_json = current_channel_json

        # Read last played channel
        with open(self.current_channel_json) as f:
            current_id = json.load(f)

        # Build up a like random list of channels
        self.absolute = 4
        self.channels = [4, 8, 12, 20, 25, 30, 35, 38]
        self.channel_dicts = list(range(0, 38))
        for channel_id in range(channeldict.__len__()):

            if channel_id < self.channels.__len__():
                # Add into the channel_dicts at the position "POS" the radio channel needed
                pos = self.channels[channel_id]
                self.channel_dicts[pos] = channeldict[channel_id]
                if channeldict[channel_id]['id'] == current_id['id']:
                    self.absolute = pos
            else:
                with open(errorlog, "a") as f:
                    f.write('This channel could not be used:')
                    f.write(channeldict[channel_id])
        # Shorten the channels
        self.channels = self.channels[:channeldict.__len__()]

        # ------------------ Pins
        # setup pins for Rotary Switch and LED
        GPIO.setup(clockPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(dataPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(switchPin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.ledid = ledpin
        self.led = Blinker(ledpin=self.ledid)

        # ------------------ Radio Player:
        self.t2 = None
        #    Start an MP3 Player with the stream url of the current channel
        self.radio = Player(self.channel_dicts[self.absolute]['stream'], self.errorlog)

        # Start the radio in a separate thread
        if not self.radio.is_running():
            self.t2 = threading.Thread(target=self.radio.start)
            self.t2.start()

        self.radio_on = True

        # ------------------ Volume Controller
        # Define and start the VolumneControl in a separate thread
        self.volume = VolumeControl()
        self.volume.set_running()
        self.t_volume = threading.Thread(target=self.volume.start)
        self.t_volume.start()

        # ------------------ Channel / last.fm control
        # Define the channel writer
        self.channel_writer = ChannelWriter(self.channel_dicts[self.absolute], last_fm_doc=self.lastfm_dict,
                                            logfile=self.errorlog, current_channel_json=self.current_channel_json)
        self.channel_writer.set_running()
        # start it in a separate thread
        self.t_writer = threading.Thread(target=self.channel_writer.start)
        self.t_writer.start()

    def start(self):
        # Start detecting changes of the Rotary switch
        GPIO.add_event_detect(self.clockPin, GPIO.FALLING, callback=self._clockCallback, bouncetime=self.DEBOUNCE)
        GPIO.add_event_detect(self.switchPin, GPIO.FALLING, callback=self.switchCallback, bouncetime=self.DEBOUNCE)

    def stop(self):
        GPIO.remove_event_detect(self.clockPin)
        GPIO.remove_event_detect(self.switchPin)

        if hasattr(self, 't1'):
            try:
                self.led.stop()
                self.t1.join()
            except:
                print("NO LED running")

        if self.t2 is not None and self.radio_on:
            self.radio.stop()
            self.channel_writer.stop()
            self.t2.join()
            self.t_writer.join()
            self.radio_on = False

        self.volume.stop()
        self.t_volume.join()

    def _clockCallback(self, pin):
        """ Most difficult function, defining the start/end of a radio channel

        This function basically controls all interactions with the radio except the
        volumne Controls like this:

        Moving the rotary Switch:
            Value is inside the channel array:
                Play the according radio channel
                Start a channel_writer
                Stop LED Blinker
                LED on
            Value is not inside
                Stop the Radio Player
                Stop the Channel Writer
                Start LED Blinker
        :return:
        """
        if GPIO.input(self.clockPin) == 0:
            # Change self.absolute according to where the wheel was turned
            # At the maximum, jump to zero
            if GPIO.input(self.dataPin) == 0:
                if self.absolute <= max(self.channels):
                    self.absolute = self.absolute + 1
                elif self.absolute == (max(self.channels) + 1):
                    self.absolute = 0

            # At the zero, jump to maximum
            elif GPIO.input(self.dataPin) == 1:
                if self.absolute > 0:
                    self.absolute = self.absolute - 1
                elif self.absolute == 0:
                    self.absolute = max(self.channels)
            print("SWITCH:")
            print(self.absolute)

            # NO CHANNEL : BLINK the LED, stop Radio
            if self.absolute not in self.channels:

                # Let the LED blink
                if not self.led.is_running():
                    self.led.set_running()
                    if hasattr(self, 't1'):
                        if not self.t1.is_alive():
                            self.t1 = threading.Thread(target=self.led.start)
                            self.t1.start()
                    else:
                        self.t1 = threading.Thread(target=self.led.start)
                        self.t1.start()

                # Stop the radio
                if self.t2 is not None and self.radio_on:
                    self.radio.stop()
                    self.channel_writer.stop()
                    self.t2.join()
                    self.t_writer.join()
                    self.radio_on = False

            # Radio Channel found
            else:
                # Stop LED from blinking
                self.led.stop()
                if hasattr(self, 't1'):
                    self.t1.join()
                # set LED to ON
                self.led.on()
                # Start a Radio + a Channel Writer
                if not self.radio.is_running():
                    self.radio = Player(self.channel_dicts[self.absolute]['stream'], self.errorlog)
                    self.t2 = threading.Thread(target=self.radio.start)
                    self.t2.start()
                    self.channel_writer = ChannelWriter(self.channel_dicts[self.absolute],
                                                        last_fm_doc=self.lastfm_dict,
                                                        logfile=self.errorlog,
                                                        current_channel_json=self.current_channel_json)
                    self.t_writer = threading.Thread(target=self.channel_writer.start)
                    self.channel_writer.set_running()
                    self.t_writer.start()
                    self.radio_on = True

            self.rotaryCallback(self.absolute)

    def _switchCallback(self, pin):
        """
        if GPIO.input(self.switchPin) == 0:
            self.switchCallback()
        """
        self.switchCallback()


class KyoRadio:
    """Wrapper for a radio with start/stop

    Attributes.
        CLOCKPIN: GPIO Number of the clk pin of the Rotary switch
        DATAPIN: GPIO Number of the dt pin of the Rotary switch
        SWITCHPIN: GPIO Number of the switch pin of the Rotary switch
        LEDPIN: GPIO Number where an LED is put to let the radio blink on channel changes
        ky040: Upon start will be filled with a KY040 class object

    """

    def __init__(self):
        print('Program start.')

        self.CLOCKPIN = 5
        self.DATAPIN = 6
        self.SWITCHPIN = 13
        self.LEDPIN = 17
        self.ky040 = None

        GPIO.setmode(GPIO.BCM)
        self._running = False

    def start(self,
              channeldict='/home/share/radioflask/static/tests/channellist.json',
              errorlog="/home/pi/share/radioflask/static/tests/errorlog.txt",
              lastfm_json="/home/pi/share/radioflask/static/tests/lastfm.json",
              current_channel_json="/home/pi/share/radioflask/static/tests/current.json"
              ):
        """

        :param channeldict: Location of the channels to run in the radio as a json file
        :param errorlog: location of a txt file to store the error log in
        :param lastfm_json: location of the last.fm connection API / API_SECRET / PASSWORD(MD5) / USER
        :param current_channel_json: Location where the currently playing channel should be written
        """
        def rotaryChange(direction):
            print("turned - " + str(direction))

        def switchPressed(pin):
            print("button connected to pin:{} pressed".format(pin))

        with open(channeldict) as f:
            channeldict = json.load(f)

        with open(lastfm_json) as f:
            lastfm_dict = json.load(f)

        # Start a KYO40 Rotary Switch controlled radio
        self.ky040 = KY040(self.CLOCKPIN, self.DATAPIN, self.SWITCHPIN, self.LEDPIN, rotaryChange, switchPressed,
                           channeldict, errorlog, lastfm_dict, current_channel_json=current_channel_json
                           )
        self.t1 = threading.Thread(target=self.ky040.start)
        print('Launch switch monitor class.')
        self.t1.start()
        self._running = True

    def stop(self):
        self.ky040.stop()
        self.t1.join()
        self._running = False


# test the radio for 10 seconds
if __name__ == "__main__":
    x = KyoRadio()
    x.start()
    sleep(10)
    x.stop()
    exit()
