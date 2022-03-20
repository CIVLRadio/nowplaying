# civl-nowplaying.py 0.4 - watches text file uploaded from SAM using inotify, then POSTs to Icecast API to update now playing metadata, and sends to NOVIA 272 via Telnet for RDS
# written by Emma Hones and Anastasia Mayer

# Copyright (c) 2022 Emma Hones and Anastasia Mayer
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

try:
    import inotify.adapters
    import requests
    import time
    from threading import Thread
    import random
    import telnetlib
    from configparser import ConfigParser
except ImportError:
    print('''
    nowplaying.py [FATAL]: Loading required modules failed!
    nowplaying.py [FATAL]: Ensure that the following are installed:
    nowplaying.py [FATAL]: inotify, requests, time, threading, random, telnetlib, configparser
    ''')
    exit(1)
except Exception:
    print("nowplaying.py [FATAL]: An unknown exception was raised while loading required modules!")
    exit(1)

# initialise variables and read arguments + settings

config = ConfigParser()
config.read('nowplaying.cfg')
debug = config.getboolean('Misc', 'verbose')
if debug == True:
    import traceback

# input
dir = config.get('Input', 'directory')
file = config.get('Input', 'file')
# Icecast
icecast_enable = config.getboolean('Icecast', 'enable')
switch_time = config.getint('Branding', 'taglines_switch_time')
mountpoint = config.get('Icecast', 'mountpoint')
branding = config.get('Branding', 'long_branding')
generic = config.get('Branding', 'taglines').splitlines()
# because the pretty config includes a blank line for readability
generic = list(filter(None, generic))
user = config.get('Icecast', 'user')
pw = config.get('Icecast', 'password')
server = config.get('Icecast', 'server')
iceport = config.getint('Icecast', 'port')
# telnet
telnet_enable = config.getboolean('RDS', 'enable')
telnet_host = config.get('RDS', 'host')
telnet_port = config.getint('RDS', 'port')
ps_prefix = config.get('RDS', 'ps_prefix') # prefix for PS
rt_prefix = config.get('RDS', 'rt_prefix') # prefix for RT
ps_branding = config.get('Branding', 'ps_branding') # branding for scrolling PS
rt_branding = config.get('Branding', 'rt_branding') # branding for RT

# initialise some variables

np = ''
run = True

# replace various characters to sanitise for the API URL. this is a really, really cursed way to do it, but ...

def _make_URL_ready(text):
    return text.replace('%', '%25').replace('$', '%24').replace('&', '%26').replace('+', '%2B').replace(',', '%2C').replace('/', '%2F').replace(':', '%eA').replace(';', '%3B').replace('=', '%3D').replace('?', '%3F').replace('@', '%40').replace(' ', '%20').replace('"', '%22').replace('<', '%3C').replace('>', '%3E').replace('#', '%23').replace('{', '%7B').replace('}', '%7D').replace('|', '%7C').replace('\\', '%5C').replace('^', '%5E').replace('~', '%7E').replace('[', '%5B').replace(']', '%5D').replace('`', '%60')

# handling data

def _send_icecast_thread():
    global run
    while run:
        try:
            time.sleep(switch_time)
            # assemble and send request
            if np == '':
                print("nowplaying.py [WARN]: NOW PLAYING is not defined!")
            else:
                print("nowplaying.py [INFO]: Sending NOW PLAYING Data...")
                response = requests.get(f"https://{server}:8000/admin/metadata?mount=/{mountpoint}&mode=updinfo&song={_make_URL_ready(f'{np} / {branding}')}", auth=(user, pw))
                if debug == True:
                    print("nowplaying.py [DEBUG]: Request: " + response.request.url)
                    print("nowplaying.py [DEBUG]: Response: " + str(response.status_code))
                time.sleep(switch_time)
            # assemble and send request
            print("nowplaying.py [LOG]: Sending STATION BRANDING Data...")
            thingy = random.choice(generic) # Choose a rando Generic Branding Thingy
            response = requests.get(f"https://{server}:8000/admin/metadata?mount=/{mountpoint}&mode=updinfo&song={_make_URL_ready(f'{thingy} / {branding}')}", auth=(user, pw))
            if debug == True:
                print("nowplaying.py [DEBUG]: Request: " + response.request.url)
                print("nowplaying.py [DEBUG]: Response: " + str(response.status_code))
        except KeyboardInterrupt:
            print("nowplaying.py [FATAL]: Ctrl-C or other KeyboardInterrupt received in Icecast thread ...")
            run=False
            return
        except Exception as e:
            print("nowplaying.py [FATAL]: Exception raised: " + e)
            return
    return

# RDS

def _send_rds_thread():
    try:
        if np == '':
            print("nowplaying.py [WARN]: NOW PLAYING is not defined!")
        else:
            print("nowplaying.py [INFO]: Sending RDS data ...")
            # assemble PS and RT
            ps_text = ps_prefix + '{} {}'.format(ps_branding, np.rstrip('\n')) + "\r"
            rt_text = rt_prefix + '{} / {}'.format(np.rstrip('\n'), rt_branding) + "\r"
            # open telnet and start sending
            with telnetlib.Telnet(telnet_host, telnet_port) as tn:
                if debug == True:
                    print("nowplaying.py [DEBUG]: PS: " + ps_text)
                tn.write(ps_text.encode('ascii'))
                tn.read_until(b'[OK]')
                if debug == True:
                    print("nowplaying.py [DEBUG]: RDS received [OK] for PS")
                    print("nowplaying.py [DEBUG]: RT: " + rt_text)
                tn.write(rt_text.encode('ascii'))
                tn.read_until(b'[OK]')
                if debug == True:
                    print("nowplaying.py [DEBUG]: Received [OK] for RT")
    except KeyboardInterrupt:
        print("nowplaying.py [FATAL]: Ctrl-C or other KeyboardInterrupt received in RDS thread ...")
        run=False
        return
    except Exception as e:
        print("nowplaying.py [FATAL]: Exception raised: " + e)
        return
    return
    return

# main loop
def _main():
    try:
        global np
        global run
        i = inotify.adapters.Inotify()

        i.add_watch(dir)

        for event in i.event_gen(yield_nones=False):
            (_, type_names, path, filename) = event
            if not 'IN_CLOSE_WRITE' in event[1]:
                # useless to us
                pass
            else:
                if filename == file:
                    # bingo, this is what we want
                    with open(path + "/" + filename, 'r') as f:
                        np = f.read()
                    print("nowplaying.py [INFO]: NP UPDATED: " + np)
                    # fire the RDS thread
                    if telnet_enable == True: 
                        if debug == True:                       
                            print("nowplaying.py [DEBUG]: Triggering RDS update")
                        rds_thread = Thread(target=_send_rds_thread, daemon=True)
                        rds_thread.start()    
                    else:
                        if debug == True:
                            print("nowplaying.py [DEBUG]: RDS not enabled, skipping update")                    
    except KeyboardInterrupt:
        print("nowplaying.py [FATAL]: Ctrl-C or other KeyboardInterrupt received in main thread ...")
        run=False
        return
    except Exception as e:
        print("nowplaying.py [FATAL]: Exception raised: " + e)
        return

if __name__ == '__main__':
    try:
        if icecast_enable == True:
            icecast_thread = Thread(target=_send_icecast_thread, daemon=True)
            icecast_thread.start()
        elif telnet_enable == False:
            print("nowplaying.py [FATAL]: Neither Icecast nor Telnet enabled in config. Is this *really* what you want?")
            exit(1)
        _main()
    except KeyboardInterrupt:
        print("nowplaying.py [FATAL]: Ctrl-C or other KeyboardInterrupt received in initial thread ...")
        run=False
        exit(0)
    except Exception as e:
        print("nowplaying.py [FATAL]: Exception raised: " + e)
        exit(1)