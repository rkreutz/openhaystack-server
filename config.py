import logging
import os
import configparser
import json

config = configparser.ConfigParser()

def getConfigPath():
    script_path = os.path.abspath(__file__)
    return os.path.dirname(script_path) + '/config'

read = config.read(getConfigPath() + '/config.ini')
if not read:
    config['Settings'] = {
        'anisette_url': os.getenv('ANISETTE_URL', 'http://anisette:6969'),
        'appleid_email': os.getenv('APPLEID_EMAIL', ''),
        'appleid_pwd': os.getenv('APPLEID_PWD', ''),
        'loglevel': os.getenv('LOG_LEVEL', 'INFO')
    }
    config['Auth'] = {}

    try:
        os.mkdir(getConfigPath())
    except:
        pass
    finally:
        with open(getConfigPath() + '/config.ini', 'w') as configfile:
            config.write(configfile)

def getAnisetteServer():
    return config.get('Settings', 'anisette_url', fallback='http://anisette:6969')

def getPort():
    return 6176

def getUser():
    return config.get('Settings', 'appleid_email', fallback='')

def getPass():
    return config.get('Settings', 'appleid_pwd', fallback='')

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