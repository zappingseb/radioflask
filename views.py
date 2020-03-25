"""
Flask App for Universum Internet Radio

author: Sebastian Wolf
description: This is the view file generating the substantial
    view from the index.html File. The App rendered will show
    4 overall views:

Views:
    1. **Currently Playing**: shows the song currently playing and
    a refresh button to check if a new song is playing

    2. **Radio Channels**: shows an input field to add a radio
    channel, and for each channel already in a deactivated
    input field where the channel can be removed

    3. **Last.fm**: This view can be used to setup the last.fm
    connection settings for the radio to scrobble all songs
    playing to last.fm

    2/3. **Reload/Save**: The settings are written to disk. With
    the reload and save buttons the disk interaction is triggered.
    Additionally, the save button restarts the radio itself

    4. **Error Log**: The error log of the current session gets
    shown

"""
__author__ = "Sebastian Wolf"
__copyright__ = "Copyright 2020, Universum Internet Radio"
__license__ = "https://www.apache.org/licenses/LICENSE-2.0"
__version__ = "0.0.1"
__maintainer__ = "Sebastian Wolf"
__email__ = "sebastian@mail-wolf.de"
__status__ = "Production"


from datetime import datetime
from flask import Flask, render_template, request, session
from flask_fontawesome import FontAwesome
import numpy as np
import os
import json
from flask_wtf import FlaskForm, CsrfProtect
from wtforms import StringField, validators, PasswordField
from pylast import md5
import re
from werkzeug.datastructures import MultiDict
from ky40 import KyoRadio


class Channel(FlaskForm):
    """
    Channel - Input Field

    Input Field to manager a channel

    Attributes:
        channel_name: String Input for the name of the channel
        stream_url: String Input for the mp3 URL
        online_radio_box: String Input for the Onlineradiobox link

    """
    channel_name = StringField("Channel Name", validators=[validators.InputRequired(message="Cannot be empty")])
    stream_url = StringField("Url of the radio",
                             validators=[validators.regexp("^http[s]{0,1}\\:.*", message="Please enter a valid URL")])
    online_radio_box = StringField("Url for Online Radio Box",
                                   validators=[
                                       validators.regexp("^http[s]{0,1}\\:.*", message="Please enter a valid URL")]
                                   )


class LastFMForm(FlaskForm):
    """
    Last.Fm User Data input Field

    """
    user = StringField("User", validators=[validators.InputRequired(message="Cannot be empty")])
    api = StringField("API Key", validators=[validators.InputRequired(message="Cannot be empty")])
    api_secret = StringField("API secret", validators=[validators.InputRequired(message="Cannot be empty")])
    password = PasswordField("Password (never shown)", validators=[validators.InputRequired(message="Cannot be empty")])


class RemoveChannel(object):
    """Channel storage class

    Attributes:
        channel_name: The name of the channel
        stream_url: The mp3 url of the song
        online_radio_box: The onlineradio box link
        id: The `channel_id` of this channel

    Methods:
        to_dict: return as a dictionary to write it to json
    """
    def __init__(self, channel_name, stream_url, channel_online_radio_box, id=1):
        """

        :param channel_name:
        :param stream_url:
        :param channel_online_radio_box:
        :param id:
        """
        self.channel_name = channel_name
        self.stream_url = stream_url
        self.online_radio_box = channel_online_radio_box
        self.id = id

    def to_dict(self):
        return ({
            'name': self.channel_name,
            'stream': self.stream_url,
            'onlineradiobox': self.online_radio_box,
            'id': self.id
        })


class ChannelList(object):
    """List of all channels in the radio

    Attributes:
        json_file: Location of the json file to represent this class
        list: List of RemoveChannel objects
        read_json: whether the json file was already read

    """
    def __init__(self, list_of_remove_channel=None, json_file='', was_post=False):
        """constructor

        :param list_of_remove_channel: A dictionary of the channel that should be removed
        :param json_file: Location where this class is stored / read
        :param was_post: Whether this class was constructed by a POST request
        """
        if list_of_remove_channel is None:
            list_of_remove_channel = list()
        self.json_file = json_file
        for channel in list_of_remove_channel:
            if not isinstance(channel, RemoveChannel):
                TypeError()
        self.list = list_of_remove_channel
        if list_of_remove_channel.__len__() > 0 or was_post:
            self.read_json = True
        else:
            self.read_json = False

    def append(self, remove_channel):
        """Add a channel to the list

        :param remove_channel: Dictionary of the RemoveChannel to be added
        """
        if isinstance(remove_channel, RemoveChannel):
            all_ids = np.asarray([val.id for i, val in enumerate(self.list)])
            if (len(all_ids) > 0):
                remove_channel.id = 'channel_id' + str(max(
                    [int(re.search("\d+", val.id).group()) for i, val in enumerate(self.list)]
                ) + 1)
            else:
                remove_channel.id = 'channel_id' + str(len(self.list) + 1)
            self.list.append(remove_channel)
        else:
            print("Not of type RemoveChannel")

    def from_json(self):
        """Add channels to this class from a JSON file

        """
        print("Reading Channellist from hard drive")
        with open(self.json_file, 'r') as f:
            for channel_entry in json.load(f):
                self.append(RemoveChannel(channel_entry["name"],
                                          channel_entry["stream"],
                                          channel_entry["onlineradiobox"]))
        self.read_json = True

    def to_json(self):
        """Write this class to json file

        :return: Nothing, will be written to self.json_file
        """
        with open(self.json_file, 'w') as f:
            json.dump([val.to_dict() for i, val in enumerate(self.list)], f)

    def as_json(self):
        """Reconstruct this class as a JSON dictionary

        :return: A dictionary containing most of the attributes of this class
        """
        return ({
            'list': [val.to_dict() for i, val in enumerate(self.list)],
            'read_json': self.read_json,
            'json_file': self.json_file
        })

    def remove(self, channel_id):
        """Remove a channel from this self.list

        :param channel_id: Unique Identifier of a channel
        :return: Nothing, just remove Channel
        """
        indexes = np.asarray([i if val.id == channel_id else -1 for i, val in enumerate(self.list)])
        indexes = indexes[indexes >= 0]
        if len(indexes) > 0:
            del self.list[indexes[0]]


class ModelEncoder(json.JSONEncoder):
    """Function to write objects to flask session

    Inside flask sessions only json objects are allowed. This function enables to
    decode ChannelList objects as json

    """
    def default(self, obj):
        if isinstance(obj, ChannelList):
            return obj.as_json()
        if isinstance(obj, CurrentlyPlaying):
            return obj.as_json()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def channel_list_to_json(json_object):
    """Create a channel (RemoveChannel) or a list of channels (ChannelList) from a dictionary

    :param json_object: Any kind of json dictionary
    :return: RemoveChannel or ChannelList object
    """
    if 'name' in json_object:
        return RemoveChannel(json_object['name'], json_object['stream'], json_object['onlineradiobox'],
                             json_object['id'])
    else:
        return ChannelList(list_of_remove_channel=json_object.get('list'), json_file=json_object.get('json_file'))


class CurrentlyPlaying(object):
    """Simple representation of a currently playing channel

    Attributes:
        id: Unique identifier of the channel
        radio: Name of the currently playing channel
        song: Song name playing on the current channel

    Methods:
        as_json: Store this object inside the flask session
    """
    def __init__(self, channel_name=None, song=None, channel_id=1):
        self.id = channel_id
        self.radio = channel_name
        self.song = song

    def as_json(self):
        return ({
            'id': self.id,
            'radio': self.radio,
            'song': self.song
        })


# -------------------------------------- APP --------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "!SSH"

# Use Fontawesome inside the App
fa = FontAwesome(app)

# Generate a token for this Flask App and all Input fields
csrf = CsrfProtect()

print("App start at: ")
print(str(datetime.now().today().isoformat()))

# ----------------------------------------- Location settings -------------------------------------------------
app_dir = '/home/pi/share/radioflask'
logfile = os.path.join(app_dir, 'static/tests/errorlog.txt')
lastfm_json = os.path.join(app_dir, 'static/tests/lastfm.json')
current_json = os.path.join(app_dir, 'static/tests/current.json')
channel_list_json = os.path.join(app_dir, 'static/tests/channellist.json')

# ----------------------------------------- Radio -------------------------------------------------

x = KyoRadio()
x.start(channeldict=channel_list_json, errorlog=logfile, lastfm_json=lastfm_json, current_channel_json=current_json)


# ----------------------------------------- App -------------------------------------------------
@app.route('/', methods=['post', 'get'])
def home():
    save_message = False

    # Check if the session needs to be restarted - Every time this app is started fresh
    # or the "clear" or "refresh" button was clicked
    anything_send = request.form.get('user') or \
                    request.args.__len__() != 0 or \
                    request.form.get('channel_name') or \
                    request.form.get('removechannel') or \
                    request.form.get('save')

    if request.form.get('clear') or not anything_send:
        try:
            session.pop('current_channels')
            session.pop('lastfm')
            session.pop('currently_playing')
        except KeyError as e:
            print(e)

    # -------------- Read in settings from JSON or session -------------------------
    # -------------- Construct filled out forms            -------------------------
    # Read in the ChannelList object
    if 'current_channels' not in session:
        channel_temp = ChannelList(json_file=channel_list_json,
                                   was_post=request.method == 'POST', list_of_remove_channel=list())
        channel_temp.from_json()
        session['current_channels'] = ModelEncoder().encode(channel_temp)
        print("read channels from Harddrive")

    # Read in the last.fm data
    if 'lastfm' not in session:
        # Create form content from json file
        with open(lastfm_json) as f:
            form_data = json.load(f)
            print("read lastfm from Harddrive")
            lastfm_form = LastFMForm(MultiDict(form_data))
            session['lastfm'] = form_data
    else:
        # If User changed the data, add the new from data
        if request.form.get('user'):
            lastfm_form = LastFMForm(request.form)
            if lastfm_form.validate_on_submit():
                lastfm_form = LastFMForm(request.form)
                session['lastfm'] = {
                    'user': request.form.get('user'),
                    'api': request.form.get('api'),
                    'api_secret': request.form.get('api_secret'),
                    'password': md5(request.form.get('password'))
                }
                save_message = True
        # If nothing was done, reload from flask session
        else:
            lastfm_form = LastFMForm(MultiDict(session['lastfm']))

    # Read in Currently Playing from session
    if 'currently_playing' not in session:
        with open(current_json) as f:
            currently_playing = json.load(f)
            currently_playing = CurrentlyPlaying(channel_name=currently_playing['radio'],
                                                 song=currently_playing['song'],
                                                 channel_id=currently_playing['id'])
            session['currently_playing'] = ModelEncoder().encode(currently_playing)
    else:
        currently_playing = CurrentlyPlaying(
            channel_name=json.loads(session['currently_playing'])['radio'],
            song=json.loads(session['currently_playing'])['song'],
            channel_id=json.loads(session['currently_playing'])['id']
        )

    # Read / Write Log Data
    if 'error_log_data' not in session:
        with open(logfile) as f:
            error_log_data = f.read()
            session['error_log_data'] = error_log_data
    else:
        error_log_data = session['error_log_data']

    # Try to read current_channels from session
    current_channels = json.JSONDecoder(object_hook=channel_list_to_json).decode(session["current_channels"])
    # If not yet read from disk, read from disk
    if not current_channels.read_json:
        current_channels.from_json()

    # Construct empty Channel Form
    channelform = Channel(request.form)

    # ------------------- Interact with the stored files upon POST ------------------------------
    if request.method == 'POST':

        # new channel was submitted? - Add it if form was filled out correctly
        if request.form.get('channel_name'):
            if channelform.validate_on_submit():
                current_channels.append(RemoveChannel(
                    channel_name=request.form.get('channel_name', None),
                    stream_url=request.form.get('stream_url', None),
                    channel_online_radio_box=request.form.get('online_radio_box')
                ))
                save_message = True

        # channel should be removed?
        remove_channel_form = request.form.get('removechannel', None)
        if remove_channel_form:
            current_channels.remove(remove_channel_form)
            save_message = True

        # Settings should be stored
        if request.form.get('save', '') == 'save':

            # SAVE the settings
            current_channels.to_json()
            with open(lastfm_json, 'w') as f:
                json.dump(session['lastfm'], f)

            # Restart the radio
            x.stop()
            x.start(errorlog=logfile,
                    lastfm_json=lastfm_json,
                    channeldict=json.load(open(current_channels.json_file)))

        # Refresh button was clicked - Show currently playing and update
        # errorlog
        refresh_info = request.form.get('refresh', None)
        if refresh_info:
            with open(current_json) as f:
                currently_playing = json.load(f)
                currently_playing = CurrentlyPlaying(channel_name=currently_playing['radio'],
                                                     song=currently_playing['song'],
                                                     channel_id=currently_playing['id'])
                session['currently_playing'] = ModelEncoder().encode(currently_playing)
            with open(logfile) as f:
                error_log_data = f.read()
                session['error_log_data'] = error_log_data

    """Renders the Universum Internetradio - ."""
    session["current_channels"] = ModelEncoder().encode(current_channels)
    return render_template(
        'index.html',
        title='Universum Internetradio - ',
        year=datetime.now().year,
        channelform=channelform,
        remove_channelform=current_channels,
        lastfm_form=lastfm_form,
        playinfo=currently_playing,
        save_message=save_message,
        logdata=error_log_data
    )
