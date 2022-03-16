# civl-nowplaying.py 0.3 - watches text file uploaded from SAM using inotify, then POSTs to Icecast API to update now playing metadata, and sends to NOVIA 272 via Telnet for RDS
# written by Emma Hones and Anastasia Mayer

import inotify.adapters
import requests
import time
from threading import Thread
import random
import telnetlib

# settings

dir = '/var/lib/broadcasting' # directory where file is uploaded
file = 'nowplaying.txt' # filename to watch
# Icecast
switch_time = 10 # Seconds in-between Branding and Filename Switch
mountpoint = 'live.mp3' # Icecast mount to update - no slash
branding = "101.7 CIVL Radio" # text to append after artist/title
generic = [
"UFV Campus and Community Radio",
"Canada's Original #1 Campus Radio Station",
"Serving Abbotsford, Mission, Chilliwack, and Langley"
] # text to alternate with now playing - remember to escape #'s
user = 'source' # for Icecast auth, from icecast.xml on server
pw = '88point5' # see above
# telnet
host = 'civl-tx.duckdns.org' # hostname where 272 is located
port = 10171 # port for Telnet
psprefix = 'DPS=' # prefix for PS
rtprefix = 'TEXT=' # prefix for RT
psbranding = "CIVL Radio" # branding for scrolling PS
rtbranding = "101.7 CIVL Radio" # branding for RT

# initialise some variables

np = ''
run = True

# replace various characters to sanitise for the API URL. this is a really, really cursed way to do it, but ...

def _make_URL_ready(text):
    return text.replace('%', '%25').replace('$', '%24').replace('&', '%26').replace('+', '%2B').replace(',', '%2C').replace('/', '%2F').replace(':', '%eA').replace(';', '%3B').replace('=', '%3D').replace('?', '%3F').replace('@', '%40').replace(' ', '%20').replace('"', '%22').replace('<', '%3C').replace('>', '%3E').replace('#', '%23').replace('{', '%7B').replace('}', '%7D').replace('|', '%7C').replace('\\', '%5C').replace('^', '%5E').replace('~', '%7E').replace('[', '%5B').replace(']', '%5D').replace('`', '%60')

# handling data

def _send_data_thread():
    global run
    while run:
        try:
            time.sleep(switch_time)
            # assemble and send request
            if np == '':
                print("nowplaying.py [WARN]: NOW PLAYING is not defined!")
            else:
                print("nowplaying.py [LOG]: Sending NOW PLAYING Data...")
                response = requests.get(f"https://live.civl.ca:8000/admin/metadata?mount=/{mountpoint}&mode=updinfo&song={_make_URL_ready(f'{np} / {branding}')}", auth=(user, pw))
                print("nowplaying.py [REQUEST]: " + response.request.url)
                print("nowplaying.py [RESPONSE]: " + str(response.status_code))
                time.sleep(switch_time)
            # assemble and send request
            print("nowplaying.py [LOG]: Sending STATION BRANDING Data...")
            thingy = random.choice(generic) # Choose a rando Generic Branding Thingy
            response = requests.get(f"https://live.civl.ca:8000/admin/metadata?mount=/{mountpoint}&mode=updinfo&song={_make_URL_ready(f'{thingy} / {branding}')}", auth=(user, pw))
            print("nowplaying.py [REQUEST]: " + response.request.url)
            print("nowplaying.py [RESPONSE]: " + str(response.status_code))
        except KeyboardInterrupt:
            run=False
            return
        except Exception as E:
            print(E)
            return
    return

# RDS

def _send_rds_thread():
    try:
        if np == '':
            print("nowplaying.py [WARN]: NOW PLAYING is not defined!")
        else:
            print("nowplaying.py [LOG]: Sending RDS data ...")
            # assemble PS and RT
            pstext = psprefix + '{} {}'.format(psbranding, np.rstrip('\n')) + "\r"
            rttext = rtprefix + '{} / {}'.format(np.rstrip('\n'), rtbranding) + "\r"
            # open telnet and start sending
            with telnetlib.Telnet(host, port) as tn:
                print("nowplaying.py [RDS]: " + pstext)
                tn.write(pstext.encode('ascii'))
                tn.read_until(b'[OK]')
                print("nowplaying.py [RDS]: Received [OK] for PS")
                print("nowplaying.py [RDS]: " + rttext)
                tn.write(rttext.encode('ascii'))
                tn.read_until(b'[OK]')
                print("nowplaying.py [RDS]: Received [OK] for RT")
    except KeyboardInterrupt:
        run=False
        return
    except Exception as E:
        print(E)
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
                    print("nowplaying.py [INOTIFY]: NP UPDATED: " + np)
                    # fire the RDS thread
                    print("nowplaying.py [INOTIFY]: Triggering RDS update")
                    rds_thread = Thread(target=_send_rds_thread, daemon=True)
                    rds_thread.start()
    except KeyboardInterrupt:
        run=False
        return
    except Exception as E:
        print(E)
        return


if __name__ == '__main__':
    try:
        # data_thread = Thread(target=_send_data_thread, daemon=True)
        # data_thread.start()
        # rds_thread = Thread(target=_send_rds_thread, daemon=True)
        # rds_thread.start()
        _main()
    except KeyboardInterrupt:
        run = False
        exit(0)
    except Exception as E:
        print(E)
        exit(1)
