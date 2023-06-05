# nowplaying.py 0.5 - watches text file uploaded from SAM using inotify, then POSTs to Icecast API to update now playing metadata, and sends to NOVIA 272 via Telnet for RDS
# written by Emma Hones and Anastasia Mayer

# Copyright (c) 2022-2023 Emma Hones and Anastasia Mayer
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

# startup name + version check
import sys, os, civl_util
logger = civl_util.logger_initialise()
logger.info('nowplaying.py v0.5')
if not sys.version_info >= (3, 6):
    logger.critical('This script requires Python 3.6 or newer. You are running this script on Python %s.%s. Please upgrade and try again.' % (sys.version_info.major, sys.version_info.minor))
    sys.exit(1)

# we're good, continuing on ...

try:
    import time, random
    import argparse
    import configparser
    from threading import Thread
    import requests
    from inotify_simple import INotify, flags
    from Exscript.protocols import Telnet
except ImportError as e:
    logger.critical('Loading required module %s failed!' % e.name)
    logger.critical('Ensure that it is installed through your system package manager or pip.')
    exit(1)
except Exception as e:
    logger.critical('An unknown exception was raised while loading required modules: %s' % e)
    exit(1)

# initialise everything and read arguments + settings

parser = argparse.ArgumentParser(
    description='Now playing metadata daemon supporting Icecast and RDS.',
    epilog='Originally developed for CIVL Radio in Abbotsford, British Columbia - online at civl.ca.')
parser.add_argument('-c', '--config', default='nowplaying.cfg', help='path to config file')
parser.add_argument('-v', '--verbose', action='store_true', help='be more talkative about what\'s happening ... useful for debugging')
args = parser.parse_args()

config = configparser.ConfigParser()
try:
    with open(args.config) as f:
        config.read_file(f)
        logger.info('Reading config file %s ...' % args.config)
except OSError as e:
        # uh-oh, someone yeeted our config
        logger.critical('Failed to open config file %s: %s' % (args.config, e.strerror))
        logger.critical('Check that the file exists and is sane.')
        sys.exit(1)
except Exception as e:
    logger.critical('An unknown error occurred while opening config file. This is almost certainly a bug.')

if args.verbose == True:
    logger.setLevel('DEBUG')

try:
    # input
    dir = config.get('Input', 'directory')
    file = config.get('Input', 'file')
    rm_file = config.getboolean('Input', 'delete_file') # delete file after reading?
    # general
    branding = config.get('Branding', 'long_branding')
    generic = config.get('Branding', 'taglines').splitlines()
    # because the pretty config includes a blank line for readability
    generic = list(filter(None, generic))
    # Icecast
    icecast_enable = config.getboolean('Icecast', 'enable') # do we use Icecast?
    switch_time = config.getint('Branding', 'taglines_switch_time') # how often to cycle between branding and now playing
    icecast_mountpoint = config.get('Icecast', 'mountpoint') # mountpoint to send to
    icecast_user = config.get('Icecast', 'user') # username for Icecast
    icecast_pw = config.get('Icecast', 'password') # password for Icecast
    icecast_server = config.get('Icecast', 'server') # host for Icecast
    if icecast_enable == True and config.getboolean('Icecast', 'ssl') == False: # use SSL?
        logger.warning('Not using SSL to connect to Icecast server. This is *not* recommended.')
        icecast_protocol = 'http'
    else:
        icecast_protocol = 'https'
    icecast_port = config.getint('Icecast', 'port') # port for Icecast
    # telnet
    telnet_enable = config.getboolean('RDS', 'enable') # do we use Telnet?
    telnet_host = config.get('RDS', 'host') # host for Telnet
    telnet_port = config.getint('RDS', 'port') # port for Telnet
    ps_prefix = config.get('RDS', 'ps_prefix') # prefix for PS
    rt_prefix = config.get('RDS', 'rt_prefix') # prefix for RT
    ps_branding = config.get('Branding', 'ps_branding') # branding for scrolling PS
    rt_branding = config.get('Branding', 'rt_branding') # branding for RT
    strip_separators = config.getboolean('RDS', 'strip_separators') # strip separators (e.g. " - ") from PS data
    separator = config.get('RDS', 'separator').replace('\'', '') # separator to strip
except configparser.Error as e:
        logger.critical('Failed to read config file %s: %s' % (args.config, e))
        logger.critical('Check the syntax and try again.')
        sys.exit(1)

# initialise some variables

try:
    # read initial NP data
    with open(dir + "/" + file, 'r') as f:
        np = f.read()
        logger.debug('Found now playing file: %s/%s' % (dir, file))
        logger.info('NP UPDATED: %s' % np)
        # delete file if needed
        if rm_file == True:
            logger.debug('Deleting %s/%s' % (dir, file))
            os.remove(dir + "/" + file)
except FileNotFoundError:
    # not ideal but not fatal
    logger.error('Could not open now playing file at %s/%s for reading. Check that it exists and is accessible.' % (dir,file))
    np = ''
run = True

# replace various characters to sanitise for the API URL. this is a really, really cursed way to do it, but ...

def _make_URL_ready(text):
    return text.replace('%', '%25').replace('$', '%24').replace('&', '%26').replace('+', '%2B').replace(',', '%2C').replace('/', '%2F').replace(':', '%eA').replace(';', '%3B').replace('=', '%3D').replace('?', '%3F').replace('@', '%40').replace(' ', '%20').replace('"', '%22').replace('<', '%3C').replace('>', '%3E').replace('#', '%23').replace('{', '%7B').replace('}', '%7D').replace('|', '%7C').replace('\\', '%5C').replace('^', '%5E').replace('~', '%7E').replace('[', '%5B').replace(']', '%5D').replace('`', '%60')

# handling data

def _send_icecast_thread():
    logger.debug('Icecast thread is here')
    global run

    while run:
        try:
            time.sleep(switch_time)
            # assemble and send request
            if np == '':
                logger.warning('NOW PLAYING is not defined!')
            else:
                logger.info('Sending NOW PLAYING data ...')
                response = requests.get(f"{icecast_protocol}://{icecast_server}:{icecast_port}/admin/metadata?mount=/{icecast_mountpoint}&mode=updinfo&song={_make_URL_ready(f'{np} / {branding}')}", auth=(icecast_user, icecast_pw))
                logger.debug('Request: %s' % response.request.url)
                logger.debug('Response: %s' % response.status_code)
                response.raise_for_status()
                time.sleep(switch_time)

            # assemble and send request
            logger.info('Sending STATION BRANDING data ...')
            thingy = random.choice(generic) # Choose a rando Generic Branding Thingy
            response = requests.get(f"{icecast_protocol}://{icecast_server}:{icecast_port}/admin/metadata?mount=/{icecast_mountpoint}&mode=updinfo&song={_make_URL_ready(f'{thingy} / {branding}')}", auth=(icecast_user, icecast_pw))
            logger.debug('Request: %s' % response.request.url)
            logger.debug('Response: %s' % response.status_code)
            response.raise_for_status()
        
        except requests.exceptions.ConnectionError as e:
            logger.error('Error sending data to %s port %s: %s' % (icecast_server, icecast_port, e.args[0].reason))
        except requests.exceptions.HTTPError as e:
            logger.error('Error sending data to %s port %s: %s' % (icecast_server, icecast_port, e))
        except Exception as e:
            logger.critical('Exception raised in Icecast thread: %s' % e)
    return

# RDS

def _send_rds_thread():
    logger.debug('RDS thread is here')
    try:
        if np == '':
            logger.warning('NOW PLAYING is not defined!')
        else:
            logger.info('Sending RDS data ...')
            # assemble PS and RT
            print(separator)
            ps_text = ps_prefix + '{} {}'.format(ps_branding, np.replace(separator, ' ').rstrip('\n')) + "\r" if strip_separators == True else ps_prefix + '{} {}'.format(ps_branding, np.rstrip('\n')) + "\r"
            rt_text = rt_prefix + '{} / {}'.format(np.rstrip('\n'), rt_branding) + "\r"
            # open telnet and start sending
            logger.debug('Opening Telnet connection ...')
            conn = Telnet()
            conn.connect(telnet_host, telnet_port)
            conn.set_prompt('[OK]')
            logger.debug('Telnet connection opened')
            logger.debug('PS: %s' % ps_text)
            conn.execute(ps_text)
            logger.debug('RDS received [OK] for PS')
            logger.debug('RT: %s' % rt_text)
            conn.execute(rt_text)
            logger.debug('RDS received [OK] for RT')
            logger.debug('Closing Telnet connection ...')
            conn.close()
            logger.debug('Telnet connection closed')

    except Exception as e:
            logger.critical('Exception raised in RDS thread: %s' % e)
    return

# main loop
def _main():
    try:
        logger.debug('main thread is here')
        global np
        global run
        i = INotify()
        try:
            logger.debug('Adding inotify watch for %s' % dir)
            i.add_watch(dir, flags.CREATE | flags.MODIFY)
        except Exception as e:
            logger.critical('Unable to add inotify watch for directory %s: %s' % (dir, e))
            sys.exit(1)
        
        while run:
            i.read()
            for event in i.read():
                if event.name == file:
                    # bingo, this is what we want
                    with open(dir + "/" + file, 'r') as f:
                        np = f.read()
                    logger.info('NP UPDATED: %s' % np)
                    # delete file if enabled
                    if rm_file == True:
                        logger.debug('Deleting %s/%s' % (dir, file))
                        os.remove(dir + "/" + file)
                    # fire the RDS thread
                    if telnet_enable == True:                  
                        logger.debug('Triggering RDS update')
                        rds_thread = Thread(target=_send_rds_thread, daemon=True)
                        rds_thread.start()
                    else:
                        logger.debug('RDS not enabled, skipping update')

    except KeyboardInterrupt:
        logger.critical('Ctrl-C or other KeyboardInterrupt received, exiting ...')
        run=False
        return
    except Exception as e:
            logger.critical('Exception raised in main thread: %s' % e)
            sys.exit(1)

    logger.debug('run = false, exiting')

if __name__ == '__main__':
    logger.debug('init thread is here')
    try:
        if icecast_enable == True:
            logger.debug('Icecast is enabled, starting thread')
            icecast_thread = Thread(target=_send_icecast_thread, daemon=True)
            icecast_thread.start()
        elif telnet_enable == False:
            raise Exception('Neither Icecast nor Telnet enabled in config. Is this *really* what you want?')

        _main()

    except Exception as e:
            logger.critical('Exception raised in init thread: %s' % e)
            sys.exit(1)

logger.debug('run = false, quitting')
