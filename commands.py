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
    print("server address:", connection.host, connection.port)
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
