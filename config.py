import logging
import os
import configparser
import json
from datetime import datetime
import locale

config = configparser.ConfigParser()

def getConfigPath():
    script_path = os.path.abspath(__file__)
    return os.path.dirname(script_path) + '/config'

read = config.read(getConfigPath() + '/config.ini')
if not read:
    config['Settings'] = {
        'anisette_url': os.getenv('ANISETTE_URL', 'http://anisette:6969'),
        'loglevel': os.getenv('LOG_LEVEL', 'INFO')
    }
    config['Auth'] = {}
    config['Anisette'] = {}

    try:
        os.mkdir(getConfigPath())
    except:
        pass
    finally:
        with open(getConfigPath() + '/config.ini', 'w') as configfile:
            config.write(configfile)

def getAnisetteServer():
    return config.get('Settings', 'anisette_url', fallback='http://anisette:6969')

def getAnisetteHeaders():
    headers = dict(config.items['Anisette'])
    if headers:
        headers["X-Apple-I-Client-Time"] = datetime.now(datetime.UTC).replace(microsecond=0).isoformat() + "Z"
        headers["X-Apple-I-TimeZone"] = str(datetime.now(datetime.UTC).astimezone().tzinfo)
        headers["loc"] = locale.getdefaultlocale()[0] or "en_US"
        headers["X-Apple-Locale"] = locale.getdefaultlocale()[0] or "en_US"
        return headers
    else:
        return headers

def getPort():
    return 6176

def getLogLevel():
    logLevel = config.get('Settings', 'loglevel', fallback='INFO')
    return logging.getLevelName(logLevel)

def getAuth():
    return dict(config.items('Auth'))

def setAuth(auth: dict):
    config['Auth'] = auth
    with open(getConfigPath() + '/config.ini', 'w') as configfile:
            config.write(configfile)

logging.basicConfig(level=getLogLevel(),
                    format='%(asctime)s - %(levelname)s - %(message)s')

logging.debug('Config => ' + str({section: dict(config[section]) for section in config.sections()}))