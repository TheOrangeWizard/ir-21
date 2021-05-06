import config

import json
import time
import urwid
import datetime
import requests
import threading

from minecraft import authentication
from minecraft.exceptions import YggdrasilError
from minecraft.networking.connection import Connection
from minecraft.networking import packets


output_lines = []
output_pos = 0
output_widget = urwid.Text("ir-21\n")
input_widget = urwid.Edit(">> ")
frame_widget = urwid.Frame(footer=input_widget, body=urwid.Filler(output_widget, valign='top'), focus_part='footer')


def print(*args):
    date = datetime.datetime.utcnow()
    text = " ".join([str(arg).encode("ascii", "ignore").decode() for arg in args]) + "\n"
    with open("logs/log-{:%y-%m-%d}.txt".format(date), "a") as log:
        log.write(text)
    output_widget.set_text(output_widget.text + text)
    cols, rows = loop.screen.get_cols_rows()
    while output_widget.rows((cols,)) > rows:
        output_widget.set_text("\n".join(output_widget.text.split("\n")[1:]))
    try:
        loop.draw_screen()
    except AssertionError:
        pass
    except UnicodeEncodeError as e:
        pass
        # print(dtstring(), type(e).__name__ + ": adding details to log")
        # with open("logs/log-{:%d-%m-%y}.txt".format(date), "a") as log:
            # log.write(dtstring() + " " + type(e).__name__ + ": " + str(e))


def timestring():
    mtime = datetime.datetime.utcnow()
    return "[{:%H:%M:%S}]".format(mtime)


def datestring():
    mtime = datetime.datetime.utcnow()
    return "[{:%d/%m/%y}]".format(mtime)


def dtstring():
    mtime = datetime.datetime.utcnow()
    return datestring() + " " + timestring()


def parse(obj):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return "".join((parse(e) for e in obj))
    if isinstance(obj, dict):
        text = ""
        if "text" in obj:
            text += obj["text"]
        if "announcement" in obj:
            text += obj["announcement"]
        if "extra" in obj:
            text += parse(obj["extra"])
        return text


def clean(text):
    text = text.replace("_", "\_")
    text = text.replace("*", "\*")
    text = text.replace("~~", "\~~")
    return text


def parse_snitch(chat):
    try:
        split_chat = [i.strip() for i in chat.split("  ")]
        act = str(split_chat[0])
        if "Enter" in act:
            action = "Enter"
        elif "Login" in act:
            action = "Login"
        elif "Logout" in act:
            action = "Logout"
        else:
            action = act
        account = str(split_chat[1][2:])
        snitch_name = str(split_chat[2][2:])
        distance = str(split_chat[4].split(" ")[0][2:][:-1])
        direction = str(split_chat[4].split(" ")[1][1:][:-2])
        coords = [int(i) for i in split_chat[3][3:][:-1].split(" ")]
        text = "**" + account + "** " + action + " at **" + snitch_name + "** `" + str(coords) + "`"
        print(dtstring(), text)
        with open("blacklist.txt", "r") as blacklist_f:
            blacklist = [line.strip("\n") for line in blacklist_f.readlines()]
            if snitch_name not in blacklist and config.snitch_hook is not None:
                requests.post(config.snitch_hook, data={"content": text})
    except Exception as e:
        print(dtstring(), "snitch error", type(e), str(e))


def send_chat(message):
    sm = message.split(" ")
    print(dtstring(), "sending:", message)
    packet = packets.serverbound.play.ChatPacket()
    packet.message = message
    connection.write_packet(packet)


auth_token = authentication.AuthenticationToken()
connection = Connection(config.host, config.port, auth_token=auth_token)
reconnect_delay = 60
paused = False


def check_online(loop, data):
    global reconnect_delay, paused
    # print(dtstring(), "check online event")
    try:
        if (not connection.connected or not connection.spawned) and not paused:
            print(dtstring(), "disconnected from", connection.options.address)
            print(dtstring(), "reconnecting...")
            connection.disconnect()
            connection.auth_token.authenticate(config.username, config.password)
            connection.connect()
        else:
            pass
    except Exception as e:
        print(dtstring(), type(e).__name__ + ":", e)
    loop.set_alarm_in(reconnect_delay, check_online)


def parse_commands(key):
    if key == "enter":
        i = input_widget.edit_text
        input_widget.edit_text = ""
        cmd = i.split(" ")[0]
        txt = " ".join(i.split(" ")[1:])
        try:
            commands[cmd](txt)
        except KeyError:
            print("command", cmd, "not found")
        except Exception as e:
            print(type(e).__name__ + ": " + str(e))


commands = {}


def command(cmd):
    commands[cmd.__name__] = cmd


@command
def help(txt):
    cmds = "valid commands: "
    for cmd in commands.keys():
        cmds += "\n"
        cmds += cmd
    print(cmds)


@command
def run(txt):
    try:
        exec(txt)
    except Exception as e:
        print(type(e).__name__ + ": " + str(e))


@command
def say(txt):
    try:
        send_chat(txt)
    except Exception as e:
        print(type(e).__name__ + ": " + str(e))


@command
def status(txt):
    print(dtstring(), "ir-21 status:")
    print("account name:", connection.auth_token.profile.name)
    print("server address:", connection.options.address, connection.options.port)
    print("connection active:", connection.connected)
    print("spawned:", connection.spawned)
    print("reactor type:", type(connection.reactor).__name__)


@command
def players(txt):
    content = []
    n = "0"
    for uuid in connection.player_list.players_by_uuid.keys():
        name = str(connection.player_list.players_by_uuid[uuid].name)
        content.append(name)
    n = str(len(content))
    print(dtstring(), n, "players online:")
    print("\n".join(sorted(content, key=str.casefold)))


@command
def pause(txt):
    global paused
    if paused:
        paused = False
        print("unpaused auto reconnect")
    else:
        paused = True
        print("paused auto reconnect")


@command
def login(txt):
    connection.connect()


@command
def logout(txt):
    if txt in ["now", "force", "f"]:
        connection.disconnect()
    else:
        send_chat("/logout")


@command
def set_delay(txt):
    try:
        global reconnect_delay
        reconnect_delay = int(txt)
        print("reconnect delay set to", txt)
    except ValueError:
        print("value error")


@command
def blacklist(txt):
    if txt == "":
        with open("blacklist.txt", "r") as blacklist_f:
            print("snitch relay blacklist:")
            print("".join(blacklist_f.readlines()))
    else:
        with open("blacklist.txt", "a") as blacklist_f:
            blacklist_f.write(txt + "\n")
            print(txt, "added to relay blacklist")


@command
def exit(txt):
    raise SystemExit


@connection.listener(packets.clientbound.play.JoinGamePacket)
def on_join_game(join_game_packet):
    print(dtstring(), "connected to", connection.options.address, "as", auth_token.profile.name)
    connection.__setattr__("player_list", packets.clientbound.play.PlayerListItemPacket.PlayerList())


@connection.listener(packets.clientbound.play.ChatMessagePacket)
def on_chat(chat_packet):
    source = chat_packet.field_string('position')
    raw_chat = json.loads(str(chat_packet.json_data))
    chat = parse(raw_chat)
    words = chat.split(" ")
    if not source == "GAME_INFO":
        if chat[:2] == "§6":
            parse_snitch(chat)
        else:
            print(dtstring(), source, chat)


@connection.listener(packets.clientbound.play.PlayerListItemPacket)
def on_player_list_item(player_list_item_packet):
    try:
        player_list_item_packet.apply(connection.player_list)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    loop = urwid.MainLoop(frame_widget, unhandled_input=parse_commands)
    print(dtstring(), "starting up")
    a = time.time()
    connection.auth_token.authenticate(config.username, config.password)
    connection.connect()
    loop.set_alarm_in(60, check_online)
    loop.run()
