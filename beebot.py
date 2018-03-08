#!/usr/bin/env python

import datetime
import errno
import os
import re
import time
import socket
import sqlite3 as db
import subprocess
import sys
import websocket
from docopt import docopt
from slackclient import SlackClient

# TODO: add logging mechanism
# TODO: exclude all bots (slackbot, beebot, etc..) from stats

token = os.environ.get('SLACK_BOT_TOKEN')
users, channels, ims, emojis = {}, {}, {}, {}
rev_parse_head = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip()
time_started = str(datetime.datetime.now())
con_retry = 0


# add timestamp to all print statements
old_out = sys.stdout
class timestamped:
    nl = True
    def flush(self):
        pass

    def write(self, x):
        # overload write()
        if x == '\n':
            old_out.write(x)
            self.nl = True
        elif self.nl:
            dtstamp = datetime.datetime.strftime(datetime.datetime.now(), "%Y%m%d %H%M%S")
            old_out.write('[%s] %s' % (dtstamp, x))
            self.nl = False
        else:
            old_out.write(x)

help_message = """
Usage:
    beebot.py -m [channel|dm|quiet]
    beebot.py [-hd]

Options:
    -h           Show this screen.
    -d           Print debug messages.
    -m  Choose mode.

Modes:
    channel  Reply in the channel/dm where the request was received.
    dm       Send replies via direct message just to the requestor. default
    quiet    Don't reply to "showme" requests.
"""

class Beebot(object):
    def __init__(self, **kwargs):
        pass

    def help_message(self):
        return help_message

# create db table if none exists
def create_db():
    try:
        con = db.connect(FILE_DB)
        cur = con.cursor()
        cur.execute('DROP TABLE IF EXISTS reactions')
        cur.executescript("""
            CREATE TABLE reactions(
                from_user TEXT,
                to_user TEXT,
                reaction TEXT,
                counter INTEGER
            );""")
        con.commit()
    except db.Error as e:
        if con:
            con.rollback()
        print("Error %s:" % e.args[0])
        sys.exit(1)
    finally:
        if con:
            con.close()


# insert reaction into db table
def db_insert(from_user, to_user, reaction, counter):
    if os.path.isfile(FILE_DB):
        con = db.connect(FILE_DB)
        cur = con.cursor()
        cur.execute('INSERT INTO reactions VALUES(?,?,?,?)', \
            (from_user, to_user, reaction, counter));
        con.commit()
    else:
        print("Can't find the database.\n")
        sys.exit(2)


# parse slack events for reactions / commands
def parse_event(event):
    if args.get("debug"):
        print(str(event) + '\n')
    if event and len(event) > 0:

        # process reactions
        data = event[0]
        if all(x in data for x in ['user', 'item_user', 'reaction']):
            reaction = data['reaction'].split(':')[0] # strip skin-tones
            from_user = data['user']
            to_user = data['item_user']
            try:
                exists = users[to_user]
                exists = users[from_user]
            except:
                print("user not found, reloading channel info")
                get_info()
            if data['type'] == 'reaction_added' and from_user != to_user:
                print("%s reacted with '%s' to %s" % (users.get(from_user, "unknown"), reaction, users.get(to_user, "unknown")))
                counter = '1'
                db_insert(from_user, to_user, reaction, counter)
            elif data['type'] == 'reaction_removed' and from_user != to_user:
                print("%s withdrew their reaction of '%s' from %s" % (users.get(from_user, "unknown"), reaction, users.get(to_user, "unknown")))
                counter = '-1'
                db_insert(from_user, to_user, reaction, counter)
            return reaction, from_user, to_user

        # answer commands
        if 'text' in data:
            channel_id = data['channel']
            if runmode == "quiet":
                return None, None, None
            elif runmode == "channel":
                pass
            else:
                if 'user' in data:
                    channel_id = data['user']
            mode = None
            if data['text'].lower().startswith('showme'):
                if len(data['text'].split()) > 1:
                    mode = data['text'].lower().split()[1]
                    if mode == 'version':
                        print("%s requested to see bot version" % (users.get(data['user'])))
                        bot_version(channel_id)
                        return None, None, None
                    elif mode == 'received':
                        print_received(channel_id)
                        return None, None, None
                    elif mode == 'given':
                        print_given(channel_id)
                        return None, None, None
                    elif mode == 'reactions':
                        print_reactions(channel_id)
                        return None, None, None
                if len(data['text'].split()) > 2:
                    reaction = data['text'].lower().split()[2]
                    if re.match(r'^[A-Za-z0-9_+-]+$', reaction):
                        from_user = data['user']
                        if channel_id in channels:
                            print("%s requested to see %s %s in #%s" % (users.get(from_user), mode, reaction, channels[channel_id]))
                        else:
                            print("%s requested to see %s %s via IM" % (users.get(from_user), mode, reaction))
                        if reaction in emojis:
                            reaction = emojis[reaction]
                        print_top(reaction, channel_id, mode)
                    else:
                        bot_usage(channel_id)
                else:
                    bot_usage(channel_id)
    return None, None, None


# send a message with the correct way to use the bot
def bot_usage(channel_id):
    text = '''```
usage:
    {:{w}} {:{w}}
    {:{w}} {:{w}}
    {:{w}} {:{w}}
```'''.format(
        'showme', '[top|all|clicked] <reaction>',
        'showme', '[given|received|reactions]',
        'showme', '[version]',
        w=7,
    )
    sc.api_call("chat.postMessage", channel=channel_id, text=text, as_user=True)


# report code version (git HEAD rev), start time, etc
def bot_version(channel_id):
    text = '''```
{:{w}} {:{w}}
{:{w}} {!s:{w}}
```'''.format(
    'started:', time_started,
    'head:', rev_parse_head.decode('utf-8'),
    w=14,
    )
    sc.api_call("chat.postMessage", channel=channel_id, text=text, as_user=True)


# print top recipients of a reaction
def print_top(reaction, channel_id, mode):
    if os.path.isfile(FILE_DB):
        con = db.connect(FILE_DB)
        with con:
            cur = con.cursor()
            sql = "SELECT to_user, sum(counter) as count from reactions where reaction=? group by to_user order by count desc"
            if mode == 'top':
                sql += " limit 5"
            elif mode == 'all':
                pass
            elif mode == 'clicked':
                sql = "SELECT from_user, sum(counter) as count from reactions where reaction=? group by from_user order by count desc"
            else:
                bot_usage(channel_id)
                return
            cur.execute(sql, [reaction])
            con.commit()
            rows = cur.fetchall()
            column_width = len(max([users[row[0]] for row in rows], key=len)) + 1
            print("Showing %s %s" % (mode, reaction))
            response = "```"
            if len(rows) > 0:
                for row in rows:
                    output = f"{users[row[0]]:{column_width}} {row[1]}"
                    print(output)
                    response += f"{output}\n"
            else:
                response += "no '"+reaction+"' reactions found"
                print("none found")
            response += "```"
            sc.api_call("chat.postMessage", channel=channel_id, text=response, as_user=True)
    else:
        print("Can't find the database.\n")
        sys.exit(2)


# print received reactions
def print_received(channel_id, user=None):
    if os.path.isfile(FILE_DB):
        con = db.connect(FILE_DB)
        with con:
            cur = con.cursor()
            sql = "SELECT to_user, sum(counter) as count from reactions group by to_user order by count desc"
            cur.execute(sql)
            con.commit()
            rows = cur.fetchall()
            column_width = len(max([row[0] for row in rows], key=len)) + 1
            if user is None:
                print("Showing number of received reactions per user:")
                response = "```"
                if len(rows) > 0:
                    for row in rows:
                        output = f"{users[row[0]]:{column_width}} {row[1]}"
                        print(output)
                        response += f"{output}\n"
                else:
                    response += "no reactions found"
                    print("none found")
                response += "```"
                sc.api_call("chat.postMessage", channel=channel_id, text=response, as_user=True)
            #else:
                # print top 20 received reactions for a specific user in descending order
    else:
        print("Can't find the database.\n")
        sys.exit(2)

# print given reactions
def print_given(channel_id, user=None):
    if os.path.isfile(FILE_DB):
        con = db.connect(FILE_DB)
        with con:
            cur = con.cursor()
            sql = "SELECT from_user, sum(counter) as count from reactions group by from_user order by count desc"
            cur.execute(sql)
            con.commit()
            rows = cur.fetchall()
            column_width = len(max([row[0] for row in rows], key=len)) + 1
            if user is None:
                print("Showing number of given reactions per user:")
                response = "```"
                if len(rows) > 0:
                    for row in rows:
                        output = f"{users[row[0]]:{column_width}} {row[1]}"
                        print(output)
                        response += f"{output}\n"

                else:
                    response += "no reactions found"
                    print("none found")
                response += "```"
                sc.api_call("chat.postMessage", channel=channel_id, text=response, as_user=True)
            #else:
                # print top 20 given reactions for a specific user in descending order
    else:
        print("Can't find the database.\n")
        sys.exit(2)

def print_reactions(channel_id, user=None):
    """ show the top 10 reactions """
    if not os.path.isfile(FILE_DB):
        print("Can't find the database.\n")
        sys.exit(2)
    con = db.connect(FILE_DB)
    with con:
        cur = con.cursor()
        sql = "SELECT reaction, sum(counter) AS COUNT FROM reactions GROUP BY reaction ORDER BY count DESC LIMIT 10"
        cur.execute(sql)
        rows = cur.fetchall()
        column_width = len(max([row[0] for row in rows], key=len)) + 1
        if user is None:
            print("Showing number of reactions:")
            response = "```"
            if len(rows) > 0:
                for row in rows:
                    output = f"{row[0]:{column_width}} {row[1]}"
                    print(output)
                    response += f"{output}\n"
            else:
                output = "no reactions found"
                response += output
                print(output)
            response += "```"
            sc.api_call("chat.postMessage", channel=channel_id, text=response, as_user=True)

# get slack team info such as users, channels, and ims for later use
def get_info():
    # get user data
    user_data = sc.api_call('users.list')
    for user in user_data['members']:
        print('id: %s, name: %s' % (user['id'], user['name']))
        users[user['id']] = user['name']
    # get channel data
    chan_data = sc.api_call('channels.list')
    for chan in chan_data['channels']:
        print('chan: %s, name: %s' % (chan['id'], chan['name']))
        channels[chan['id']] = chan['name']
    # get im data
    im_data = sc.api_call('im.list')
    for im in im_data['ims']:
        print('im: %s, user: %s' % (im['id'], users[im['user']]))
        ims[im['id']] = users[im['user']]
    # get emoji data
    emoji_data = sc.api_call('emoji.list')
    for entry in emoji_data['emoji']:
        if 'alias:' in emoji_data['emoji'][entry]:
            print('alias: ' + entry + ' ==> '+ emoji_data['emoji'][entry].split(':')[1])
            emojis[entry] = emoji_data['emoji'][entry].split(':')[1]


# open connection to slack
def sl_connect(retry):
    try:
        if sc.rtm_connect():
            print('INFO: Bot connected and running in [ ' + runmode + ' ] mode!')
            global con_retry
            con_retry = 0
            get_info()
            while True:
                try:
                    reaction, from_user, to_user = parse_event(sc.rtm_read())
                    time.sleep(1)
                except socket.error as e:
                    if isinstance(e.args, tuple):
                        print("ERROR: errno is %d" % e[0])
                        if e[0] == errno.EPIPE:
                            # remote peer disconnected
                            print("ERROR: Detected remote disconnect")
                            sl_con_retry()
                        else:
                            # some different error
                            print("ERROR: socket error: ", e)
                            sl_con_retry()
                    else:
                        print("ERROR: socket error: ", e)
                        sl_con_retry()
                        break
                except IOError as e:
                    print("ERROR: IOError: ", e)
                    sl_con_retry()
                    break
        else:
            print('ERROR: Connection failed. Token or network issue.')
            sl_con_retry()
    except websocket._exceptions.WebSocketConnectionClosedException:
        print('ERROR: Connection closed. Did someone disable the bot integration?')
        sl_con_retry()


def sl_con_retry():
    global con_retry
    time_sleep = con_retry * 2
    print("INFO: Connection retry #%d sleeping for %d seconds..." % (con_retry, time_sleep))
    time.sleep(time_sleep)
    con_retry += 1
    sl_connect(con_retry)


# main
if __name__ == '__main__':
    sys.stdout = timestamped()
    FILE_DB = "reactions.db"
    args = docopt(help_message)
    runmode = None
    if args.get("quiet"):
        runmode = "quiet"
    elif args.get("channel"):
        runmode = "channel"
    else:
        runmode = "dm"
    # initialize db if it doesn't exist
    if os.path.exists(FILE_DB) == False:
        create_db()
    # connect to slack
    sc = SlackClient(token)
    sl_connect(con_retry)
