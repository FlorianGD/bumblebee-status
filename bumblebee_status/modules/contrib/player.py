"""Displays the current song being played and allows pausing, skipping ahead, and
skipping back.

Requires the following library:
    * python-dbus

Parameters:
    * player.format:   Format string (defaults to '{artist} - {title}')
      Available values are: {album}, {title}, {artist}, {trackNumber}
    * player.layout:   Comma-separated list to change order of widgets (defaultés to
      song, previous, pause, next)
      Widget names are: player.song, player.prev, player.pause, player.next.
    * player.concise_controls: When enabled, allows player to be controlled from just
      the player.song widget.
      Concise controls are: Left Click: Toggle Pause; Wheel Up: Next; Wheel Down;
      Previous.

contributed by `FlorianGD <https://github.com/FlorianGD>`_ - many thanks!
"""

import logging
import sys
import dbus

import core.module
import core.widget
import core.input
import core.decorators
import util.format

log = logging.getLogger(__name__)


class Module(core.module.Module):
    def __init__(self, config, theme):
        super().__init__(config, theme, [])

        self.background = True

        self.__layout = util.format.aslist(
            self.parameter(
                "layout",
                "player.song,player.prev,player.pause,player.next",
            )
        )

        self.__bus = dbus.SessionBus()
        self.__song = ""
        self.__format = self.parameter("format", "{artist} - {title}")
        self.__name = ""
        self.__cmd_template = "dbus-send --session --type=method_call --dest={player} \
                /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player."
        self.set_cmd()

    def set_cmd(self):
        self.find_player()
        self.__cmd = self.__cmd_template.format(player=self.__name)
        self.add_widgets()

    def find_player(self):
        try:
            bus = dbus.SessionBus()
            names = [x for x in bus.list_names() if "MediaPlayer2" in x]
        except (dbus.exceptions.DBusException):
            names = []
        if names:
            self.__name = str(max(names, key=len))

    def add_widgets(self):
        widget_map = {}
        for widget_name in self.__layout:
            widget = self.add_widget(name=widget_name)
            if widget_name == "player.prev":
                widget_map[widget] = {
                    "button": core.input.LEFT_MOUSE,
                    "cmd": self.__cmd + "Previous",
                }
                widget.set("state", "prev")
            elif widget_name == "player.pause":
                widget_map[widget] = {
                    "button": core.input.LEFT_MOUSE,
                    "cmd": self.__cmd + "PlayPause",
                }
            elif widget_name == "player.next":
                widget_map[widget] = {
                    "button": core.input.LEFT_MOUSE,
                    "cmd": self.__cmd + "Next",
                }
                widget.set("state", "next")
            elif widget_name == "player.song":
                if util.format.asbool(self.parameter("concise_controls", "false")):
                    widget_map[widget] = [
                        {
                            "button": core.input.LEFT_MOUSE,
                            "cmd": self.__cmd + "PlayPause",
                        },
                        {
                            "button": core.input.WHEEL_UP,
                            "cmd": self.__cmd + "Next",
                        },
                        {
                            "button": core.input.WHEEL_DOWN,
                            "cmd": self.__cmd + "Previous",
                        },
                    ]
            else:
                raise KeyError(
                    "The player module does not have a {widget_name!r} widget".format(
                        widget_name=widget_name
                    )
                )
        # is there any reason the inputs can't be directly registered above?
        for widget, callback_options in widget_map.items():
            if isinstance(callback_options, dict):
                core.input.register(widget, **callback_options)

            elif isinstance(callback_options, list):  # used by concise_controls
                for opts in callback_options:
                    core.input.register(widget, **opts)

    def hidden(self):
        return self.string_song == ""

    def __get_song(self):
        bus = self.__bus
        player = bus.get_object(self.__name, "/org/mpris/MediaPlayer2")
        player_iface = dbus.Interface(player, "org.freedesktop.DBus.Properties")
        props = player_iface.Get("org.mpris.MediaPlayer2.Player", "Metadata")
        self.__song = self.__format.format(
            album=str(props.get("xesam:album")),
            title=str(props.get("xesam:title")),
            artist=",".join(props.get("xesam:artist")),
            trackNumber=str(props.get("xesam:trackNumber")),
        )

    def update(self):
        if not self.__name:
            self.__init__(self.__config, self.theme)
        try:
            self.__get_song()
            bus = self.__bus.get_object(self.__name, "/org/mpris/MediaPlayer2")

            for widget in self.widgets():
                if widget.name == "player.pause":
                    playback_status = str(
                        dbus.Interface(
                            bus,
                            "org.freedesktop.DBus.Properties",
                        ).Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus")
                    )
                    if playback_status == "Playing":
                        widget.set("state", "playing")
                    else:
                        widget.set("state", "paused")
                elif widget.name == "player.song":
                    widget.set("state", "song")
                    widget.full_text(self.__song)

        except Exception as e:
            log.error(str(e))
            self.__song = ""

    @property
    def string_song(self):
        if sys.version_info.major < 3:
            return unicode(self.__song)
        return str(self.__song)
