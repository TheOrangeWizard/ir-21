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


output_widget = urwid.Text("ir-21")
input_widget = urwid.Edit("~> ")
frame_widget = urwid.Frame(footer=input_widget, body=urwid.Filler(output_widget, valign='top'), focus_part='footer')


def print(*args):
    date = datetime.datetime.utcnow()
    with open("log-{:%d-%m-%y}".format(date), "a") as log:
        log.write(" ".join(args) + "\n")
    output_widget.set_text(output_widget.text + " ".join(args) + "\n")


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
        if config.snitch_hook is not None:
            requests.post(config.snitch_hook, data={"content": text})
    except Exception as e:
        print(dtstring(), "snitch error", type(e), e)


def handle_exit():
    print(dtstring(), "disconnected from", connection.host)
    print(dtstring(), "reconnecting in 60 seconds")
    time.sleep(60)
    print(dtstring(), "reconnecting...")
    connection.connect()


def handle_error(exc):
    print(exc)
    if not connection.connected:
        print(dtstring(), "connection lost")
    else:
        print(dtstring(), "connection not lost")


def send_chat(message):
    sm = message.split(" ")
    print(dtstring(), "sending:", message)
    packet = packets.serverbound.play.ChatPacket()
    packet.message = message
    connection.write_packet(packet)


auth_token = authentication.AuthenticationToken()
connection = Connection(config.host, config.port,
                        auth_token=auth_token,
                        handle_exception=handle_error,
                        handle_exit=handle_exit)


def background():
    print(dtstring(), "background thread started")
    a = time.time()
    while True:
        time.sleep(1)
        if time.time() - a > 600:
            print(dtstring(), connection.connected, type(connection.reactor))
            a = time.time()
        if time.time() - a > 120:
            if not connection.connected:
                print(dtstring(), "disconnected from", connection.host)
                print(dtstring(), "reconnecting...")
                connection.auth_token.authenticate(config.username, config.password)
                connection.connect()
            a = time.time()


def parse_commands(key):
    if key == "enter":
        i = input_widget.edit_text
        cmd = i.split(" ")[0]
        txt = " ".join(i.split(" ")[1:])
        try:
            commands[cmd](txt)
        except Exception as e:
            print(str(type(e)) + ": " + str(e))


commands = {}


def command(cmd):
    commands[cmd.__name__] = cmd


@command
def run(txt):
    try:
        exec(txt)
    except Exception as e:
        print(str(type(e)) + ": " + str(e))


@command
def say(txt):
    try:
        send_chat(txt)
    except Exception as e:
        print(type(e) + ": " + str(e))


@command
def status(txt):
    print(dtstring(), "ir-21 status:")
    print("account name:", connection.auth_token.profile.name)
    print("server address:", connection.address, connection.port)
    print("connection active:", connection.connected)
    print("spawned:", connection.spawned)
    print("reactor type:", type(connection.reactor))


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
def exit(txt):
    raise SystemExit


@connection.listener(packets.clientbound.play.JoinGamePacket)
def on_join_game(join_game_packet):
    print(dtstring(), "connected to", connection.address, "as", auth_token.profile.name)
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
    print(dtstring(), "starting up")
    a = time.time()
    connection.auth_token.authenticate(config.username, config.password)
    connectionThread = threading.Thread(connection.connect())
    connectionThread.start()
    #backgroundThread = threading.Thread(background())
    #backgroundThread.start()
    loop = urwid.MainLoop(frame_widget, unhandled_input=parse_commands)
    loop.run()
