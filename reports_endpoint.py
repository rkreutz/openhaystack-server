#!/usr/bin/env python3

import json
import requests
import config

from http.server import BaseHTTPRequestHandler, HTTPServer

import logging
logger = logging.getLogger()


class ServerHandler(BaseHTTPRequestHandler):
    
    def addCORSHeaders(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Headers", "Authorization")

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.addCORSHeaders()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.addCORSHeaders()
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Nothing to see here")

    def do_POST(self):
        if hasattr(self.headers, 'getheader'):
            content_len = int(self.headers.getheader('content-length', 0))
        else:
            content_len = int(self.headers.get('content-length'))

        post_body = self.rfile.read(content_len)
        logger.debug('Getting with post: ' + str(post_body))

        try:
            r = requests.post("https://gateway.icloud.com/acsnservice/fetch",  auth=getAuth(),
                              headers=config.getAnisetteHeaders(),
                              json=json.loads(post_body))
            logger.debug('Return from fetch service:')
            logger.debug(r.content.decode())
            result = json.loads(r.content.decode())
            self.send_response(200)
            # send response headers
            self.addCORSHeaders()
            self.end_headers()

            # send the body of the response
            responseBody = json.dumps(result)
            self.wfile.write(responseBody.encode())
        except Exception as e:
            logger.error("Unknown error occured {e}", exc_info=True)
            self.send_response(501)

def getAuth(second_factor='sms'):
    j = config.getAuth()
    return (j['dsid'], j.get('searchpartytoken', j.get('searchPartyToken', '')))


if __name__ == "__main__":
    Handler = ServerHandler
    httpd = HTTPServer(('0.0.0.0', config.getPort()), Handler)
    logger.info("serving at port " + str(config.getPort()))
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        logger.info('Server stopped')
