import time

import urllib3
from getpass import getpass
import plistlib as plist
import json
import uuid
import pbkdf2
import requests
import hashlib
import hmac
import base64
import locale
import logging
import re
from datetime import datetime, timezone
import srp._pysrp as srp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from Crypto.Hash import SHA256
import config

# Created here so that it is consistent
USER_ID = uuid.uuid4()
DEVICE_ID = uuid.uuid4()

# Configure SRP library for compatibility with Apple's implementation
srp.rfc5054_enable()
srp.no_username_in_x()

# Disable SSL Warning
urllib3.disable_warnings()

logger = logging.getLogger()


def icloud_login_mobileme(username='', password=''):
    print("")  # Sometimes no output
    if not username:
        username = input('Apple ID: ')
    if not password:
        password = getpass('Password: ')

    g = gsa_authenticate(username, password)
    pet = g["t"]["com.apple.gs.idms.pet"]["token"]
    adsid = g["adsid"]

    data = {
        "apple-id": username,
        "delegates": {"com.apple.mobileme": {}},
        "password": pet,
        "client-id": str(USER_ID),
    }
    data = plist.dumps(data)
    headers = {
        "X-Apple-ADSID": adsid,
        "User-Agent": "com.apple.iCloudHelper/282 CFNetwork/1408.0.4 Darwin/22.5.0",
        "X-Mme-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.accountsd/113)>'
    }
    headers.update(generate_anisette_headers())

    logger.info("Registering device after login")
    with requests.post(
            "https://setup.icloud.com/setup/iosbuddy/loginDelegates",
            auth=(username, pet),
            data=data,
            headers=headers,
            verify=False,
    ) as resp:
        resp.raise_for_status()
    response = f"HTTP-Code: {resp.status_code}\n{resp.text}"
    logger.debug(response)
    return plist.loads(resp.content)


def gsa_authenticate(username, password):
    # Password is None as we'll provide it later
    usr = srp.User(username, bytes(), hash_alg=srp.SHA256, ng_type=srp.NG_2048)
    _, a = usr.start_authentication()
    logger.info("Authentication request initialization")
    r = gsa_authenticated_request(
        {"A2k": a, "ps": ["s2k", "s2k_fo"], "u": username, "o": "init"})

    if r["sp"] not in ["s2k", "s2k_fo"]:
        logger.warning(f"This implementation only supports s2k and sk2_fo. Server returned {r['sp']}")
        return

    # Change the password out from under the SRP library, as we couldn't calculate it without the salt.
    usr.p = encrypt_password(password, r["s"], r["i"], r["sp"])

    m = usr.process_challenge(r["s"], r["B"])

    # Make sure we processed the challenge correctly
    if m is None:
        logger.error("Failed to process challenge")
        return
    logger.info("Authentication request completion")
    resp = gsa_authenticated_request(
        {"c": r["c"], "M1": m, "u": username, "o": "complete"})

    # Make sure that the server's session key matches our session key (and thus that they are not an imposter)
    if "M2" not in resp:
        logger.error("Error on authentication")
        logger.error(resp)
        return
    usr.verify_session(resp["M2"])
    if not usr.authenticated():
        logger.error("Failed to verify session")
        return

    spd = decrypt_cbc(usr, resp["spd"])
    # For some reason plistlib doesn't accept it without the header...
    PLISTHEADER = b"""\
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE plist PUBLIC '-//Apple//DTD PLIST 1.0//EN' 'http://www.apple.com/DTDs/PropertyList-1.0.dtd'>
"""
    spd = plist.loads(PLISTHEADER + spd)

    if "au" in resp["Status"] and resp["Status"]["au"] in ["trustedDeviceSecondaryAuth", "secondaryAuth"]:
        logger.info("2FA required, requesting SMS code. (No other 2FA-code will work!)")
        # Replace bytes with strings
        for k, v in spd.items():
            if isinstance(v, bytes):
                spd[k] = base64.b64encode(v).decode()
        sms_second_factor(spd["adsid"], spd["GsIdmsToken"])

        return gsa_authenticate(username, password)
    elif "au" in resp["Status"]:
        logger.error(f"Unknown auth value {r['Status']['au']}")
        return
    else:
        return spd


def gsa_authenticated_request(parameters):
    body = {
        "Header": {"Version": "1.0.1"},
        "Request": {"cpd": generate_cpd()},
    }
    body["Request"].update(parameters)

    headers = {
        "Content-Type": "text/x-xml-plist",
        "Accept": "*/*",
        "User-Agent": "akd/1.0 CFNetwork/978.0.7 Darwin/18.7.0",
        "X-MMe-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)>'
    }

    with  requests.post(
            "https://gsa.apple.com/grandslam/GsService2",
            headers=headers,
            data=plist.dumps(body),
            verify=False,
            timeout=5,
    ) as resp:
        resp.raise_for_status()

    response = f"HTTP-Code: {resp.status_code}\n{resp.text}"
    logger.debug(response)

    return plist.loads(resp.content)["Response"]


def generate_cpd():
    cpd = {
        # Many of these values are not strictly necessary, but may be tracked by Apple
        "bootstrap": True,  # All implementations set this to true
        "icscrec": True,  # Only AltServer sets this to true
        "pbe": False,  # All implementations explicitly set this to false
        "prkgen": True,  # I've also seen ckgen
        "svct": "iCloud",  # In certian circumstances, this can be 'iTunes' or 'iCloud'
    }

    cpd.update(generate_anisette_headers())
    return cpd


def generate_anisette_headers():
    with requests.get(config.getAnisetteServer(), timeout=5) as response:
        response.raise_for_status()  # Hebt Fehler hervor (z. B. 404 oder 500)
        jsonResponse = response.json()
        a = {"X-Apple-I-MD": jsonResponse["X-Apple-I-MD"],
             "X-Apple-I-MD-M": jsonResponse["X-Apple-I-MD-M"]}
        a.update(generate_meta_headers(user_id=USER_ID, device_id=DEVICE_ID))
    return a


def generate_meta_headers(serial="0", user_id=uuid.uuid4(), device_id=uuid.uuid4()):
    return {
        "X-Apple-I-Client-Time": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
        "X-Apple-I-TimeZone": str(datetime.now(timezone.utc).astimezone().tzinfo),
        "loc": locale.getdefaultlocale()[0] or "en_US",
        "X-Apple-Locale": locale.getdefaultlocale()[0] or "en_US",
        "X-Apple-I-MD-RINFO": "17106176",  # either 17106176 or 50660608
        "X-Apple-I-MD-LU": base64.b64encode(str(user_id).upper().encode()).decode(),
        "X-Mme-Device-Id": str(device_id).upper(),
        "X-Apple-I-SRL-NO": serial,  # Serial number
    }


def encrypt_password(password, salt, iterations, protocol):
    assert protocol in ["s2k", "s2k_fo"]
    p = hashlib.sha256(password.encode("utf-8")).digest()
    if protocol == "s2k_fo":
        p = p.hex().encode("utf-8")
    return pbkdf2.PBKDF2(p, salt, iterations, SHA256).read(32)


def create_session_key(usr, name):
    k = usr.get_session_key()
    if k is None:
        raise Exception("No session key")
    return hmac.new(k, name.encode(), hashlib.sha256).digest()


def decrypt_cbc(usr, data):
    extra_data_key = create_session_key(usr, "extra data key:")
    extra_data_iv = create_session_key(usr, "extra data iv:")
    # Get only the first 16 bytes of the iv
    extra_data_iv = extra_data_iv[:16]

    # Decrypt with AES CBC
    cipher = Cipher(algorithms.AES(extra_data_key), modes.CBC(extra_data_iv))
    decryptor = cipher.decryptor()
    data = decryptor.update(data) + decryptor.finalize()
    # Remove PKCS#7 padding
    padder = padding.PKCS7(128).unpadder()
    return padder.update(data) + padder.finalize()


WAITING_TIME = 60


def sms_second_factor(dsid, idms_token):
    identity_token = base64.b64encode(
        (dsid + ":" + idms_token).encode()).decode()

    headers = {
        "User-Agent": "Xcode",
        "Accept-Language": "en-us",
        "X-Apple-Identity-Token": identity_token,
        "X-Apple-App-Info": "com.apple.gs.xcode.auth",
        "X-Xcode-Version": "11.2 (11B41)",
        "X-Mme-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)>'
    }

    headers.update(generate_anisette_headers())

    # Extract the "boot_args" from the auth page to get the id of the trusted phone number
    pattern = r'<script.*class="boot_args">\s*(.*?)\s*</script>'
    with requests.get("https://gsa.apple.com/auth", headers=headers, verify=False) as auth:
        auth.raise_for_status()
        sms_id = 1
        match = re.search(pattern, auth.text, re.DOTALL)
        if match:
            boot_args = json.loads(match.group(1).strip())
            try:
                sms_id = boot_args["direct"]["phoneNumberVerification"]["trustedPhoneNumber"]["id"]
            except KeyError as e:
                logger.debug(match.group(1).strip())
                logger.error("Key for sms id not found. Using the first phone number")
        else:
            logger.debug(auth.text)
            logger.error("Script for sms id not found. Using the first phone number")

        logger.info(f"Using phone with id {sms_id} for SMS2FA")
        body = {"phoneNumber": {"id": sms_id}, "mode": "sms"}
        for handler in logger.handlers:
            handler.flush()
        # Prompt for the 2FA code. It's just a string like '123456', no dashes or spaces
        start_time = time.perf_counter()
        code = input(
            f"Enter SMS 2FA code (If you do not receive a code, wait {WAITING_TIME}s and press Enter. An attempt will be made to request the SMS in another way.): ")
        end_time = time.perf_counter()

    if code == "":
        elapsed_time = int(end_time - start_time)
        if elapsed_time < WAITING_TIME:
            waiting_time = WAITING_TIME - elapsed_time
            logger.info(
                f"You only waited {elapsed_time} seconds. The next request will be started in {waiting_time} seconds")
            time.sleep(waiting_time)
            code = input(f"Enter SMS 2FA code if you have received it in the meantime, otherwise press Enter: ")

            if code == "":
                code = request_code(headers)
        else:
            code = request_code(headers)

    body['securityCode'] = {'code': code}

    # Send the 2FA code to Apple
    with  requests.post(
            "https://gsa.apple.com/auth/verify/phone/securitycode",
            json=body,
            headers=headers,
            verify=False,
            timeout=5,
    ) as resp:
        resp.raise_for_status()

    response = f"HTTP-Code: {resp.status_code} with {len(resp.text)} bytes"
    logger.debug(response)
    header_string = "Headers:\n"
    for header, value in resp.headers.items():
        header_string += f"{header}: {value}\n"
    logger.debug(header_string)
    # Headers does not include Apple DSID, 2FA failed
    if resp.ok and "X-Apple-DSID" in resp.headers:
        logger.info("2FA successful")
    else:
        raise Exception(
            "2FA unsuccessful. Maybe wrong code or wrong number. Check your account details.")


def request_code(headers):
    # This will send the 2FA code to the user's phone over SMS
    # We don't care about the response, it's just some HTML with a form for entering the code
    # Easier to just use a text prompt
    body = {"phoneNumber": {"id": 1}, "mode": "sms"}
    with requests.put(
            "https://gsa.apple.com/auth/verify/phone/",
            json=body,
            headers=headers,
            verify=False,
            timeout=5
    ) as req:
        req.raise_for_status()
    code = input(f"Enter SMS 2FA code:")
    return code