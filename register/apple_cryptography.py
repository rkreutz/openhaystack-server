#!/usr/bin/env python

import hashlib
import json
import logging
import os
import struct
import sys
import config

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher

from .pypush_gsa_icloud import icloud_login_mobileme

logger = logging.getLogger()


def sha256(data):
    digest = hashlib.new("sha256")
    digest.update(data)
    return digest.digest()


def decrypt(enc_data, algorithm_dkey, mode):
    decryptor = Cipher(algorithm_dkey, mode, default_backend()).decryptor()
    return decryptor.update(enc_data) + decryptor.finalize()


def decode_tag(data):
    latitude = struct.unpack(">i", data[0:4])[0] / 10000000.0
    longitude = struct.unpack(">i", data[4:8])[0] / 10000000.0
    confidence = int.from_bytes(data[8:9])
    status = int.from_bytes(data[9:10])
    return {'lat': latitude, 'lon': longitude, 'conf': confidence, 'status': status}


def getAuth(regenerate=False):
    if config.getAuth() and not regenerate:
        j = config.getAuth()
    else:
        logger.info('Trying to login')
        mobileme = icloud_login_mobileme(
            username=config.getUser(), password=config.getPass())

        logger.debug('Answer from icloud login')
        logger.debug(mobileme)
        status = mobileme['delegates']['com.apple.mobileme']['status']
        if status == 0:
            j = {'dsid': mobileme['dsid'], 'searchPartyToken': mobileme['delegates']
                 ['com.apple.mobileme']['service-data']['tokens']['searchPartyToken']}
            config.setAuth(j)

        else:
            msg = mobileme['delegates']['com.apple.mobileme']['status-message']
            logger.error('Invalid status: ' + str(status))
            logger.error('Error message: ' + msg)
            if 'blocking' in msg:
                logger.error(
                    'It seems your account score is not high enough. Log in to https://appleid.apple.com/ and add your credit card (nothing will be charged) or additional data to increase it.')
            logger.error('Unable to proceed, program will be terminated.')

            sys.exit()
    if 'searchPartyToken' in j:
        return (j['dsid'], j['searchPartyToken'])
    else:
        return (j['dsid'], j['searchpartytoken'])


def registerDevice():

    logger.info(f'Trying to register new device.')
    getAuth(regenerate=True)