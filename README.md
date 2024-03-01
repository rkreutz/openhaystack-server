# OpenHaystack Server

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-Info-blue)](https://hub.docker.com/r/rkreutz/ohs)
[![Docker Pulls](https://img.shields.io/docker/pulls/rkreutz/ohs)](https://hub.docker.com/r/rkreutz/ohs)

This project is a modification of [macless-haystack](https://github.com/dchristl/macless-haystack)'s server implementation, for easier setup and compatibility with [openhaystack](https://github.com/seemoo-lab/openhaystack) macOS app.

## Table of Contents

- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Docker Network](#docker-network)
  - [Anisette Server](#anisette-server)
  - [Reports Server](#reports-server)
- [FAQ](#faq)
- [Acknowledgements](#acknowledgements)

# Setup

In this section, you will find a step-by-step guide on how to set up the OpenHaystack Server.

## Prerequisites

- [Docker](https://www.docker.com/) installed
- Apple-ID with 2FA (mobile or sms) enabled, preferrably NOT your main account.

## Docker Network

First we'll start creating a Docker network for our services to communicate between each other:

```bash
docker network create ohs-network
```

## Anisette Server

This project uses [Dadoum/anisette-v3-server](https://github.com/Dadoum/anisette-v3-server).

First we need to run it skipping HTTP binding, so that we can validate that initial configuration has worked:

```bash
docker run --volume anisette-v3_data:/home/Alcoholic/.config/anisette-v3 dadoum/anisette-v3-server --skip-server-startup
```

Once that step is successful we can proceed and actually start the anisette server:

```bash
docker run -d --restart always --name anisette -p :6969 --volume anisette-v3_data:/home/Alcoholic/.config/anisette-v3 --network ohs-network dadoum/anisette-v3-server
```

To test it out you may try running `curl` from another container in the network:

```bash
docker run -it --network ohs-network --entrypoint bash ubuntu

$ apt-get update && apt-get install -y curl            # installs curl in the newly created container
$ curl http://anisette:6969                            # makes a curl request to the anisette server, should return some JSON with anisette data
```

## Reports Server

To start and set up the reports server run the following command:

```bash
docker run -it --restart unless-stopped --name ohs -p 6176:6176 --network ohs-network rkreutz/ohs
```

You may additionally specify some ENV vars:
- `-e ANISETTE_URL=<url>`: overrides which anisette server to use (defaults to the one configured previously at `http://anisete:6969`)
- `-e APPLEID_EMAIL=<email>`: if provided, will be used for authentication with Apple (Apple ID account email).
- `-e APPLEID_PWD=<password>`: if provided, will be used for authentication with Apple (Apple ID account password).
- `-e LOG_LEVEL=<loglevel>`: log level of the reports server, defaults to `INFO`.

This will prompt you to login with your Apple ID (if credentials not provided) and input 2FA code.

Once 2FA is successful, server will start listening on port `6176`, to test it out you can use `curl` on a separate terminal window:

```bash
curl 0.0.0.0:6176 # ouputs: Nothing to see here
```

If everything is working as expected, terminate the interactive docker container and restart it:

```bash
docker restart ohs
```

Server should be up and running again on the same port.

We can now try fetching some records from it:

```bash
curl -X POST 0.0.0.0:6176 -d '{"search":[{"ids":["<key ID>"],"startDate":"<unix timestamp milliseconds>","endDate":"<unix timestamp milliseconds>"}]}' # returns a list of reported locations for the provided key ID
```

# FAQ

#### Where and what data is stored on the container?

The container stores the authentication headers from iCloud authentication (`dsid` and `searchPartyToken`) under `/app/config/config.ini` and Apple ID credentials if provided as env variables.

#### How can I see the logs?

You can check out the logs with:

```bash
docker logs -f ohs
```

or restart docker in interactive mode:

```bash
docker stop ohs
docker start -ai ohs
```

#### What is the config.ini used for?

Authentication related headers are stored here along with initial settings when passing environment variables (like anisette server URL, Apple ID credentials and log level).

#### Error during registration

During the registration, an error occurs, for example:

```text
It seems your account score is not high enough. Log in to https://appleid.apple.com/ and add your credit card (nothing will be charged) or additional data to increase it.
```

This can happen with new accounts that have not provided any data and/or devices. A solution might be to add a payment method (i.e. credit card), register your account with a real Apple device and/or add some more data to the account at [Apple](https://appleid.apple.com/).

There are indications that accounts newly registered through [Apple Music](https://play.google.com/store/apps/details?id=com.apple.android.music) do not have this issue.

Unfortunately, there is no general solution as Apple changes the mechanism. After the data has been added, the registration can be restarted:

```bash
docker stop ohs
docker start -ai ohs
```

#### How do I update the Docker container

The old container can be deleted and a new one pulled with:

```bash
docker rm -f ohs
docker rmi rkreutz/ohs
docker run -it -d --restart unless-stopped --name ohs -p 6176:6176 --network ohs-network rkreutz/ohs
```

A new registration will be necessary.

#### Restart the registration/change account

Just deleting the old container and starting a new one should start a new registration flow.

```bash
docker rm -f ohs
docker run -it -d --restart unless-stopped --name ohs -p 6176:6176 --network ohs-network rkreutz/ohs
```

#### How can I reset everything and start over? How can i completely uninstall OpenHaystack Server?

You can start completely from scratch by deleting the container and the data. After that, you can begin the guide from the beginning:

```bash
docker rm -f ohs
docker rmi rkreutz/ohs
docker rm -f anisette
docker rmi dadoum/anisette-v3-server
docker volume rm anisette-v3_data
docker volume prune
docker network rm ohs-network
docker network prune
```

#### How can I access a running container with a shell

You can always access the shell of the container with:

```bash
docker exec -it ohs /bin/bash -c "export TERM=xterm; exec bash"
```

#### Should I restrict access to my server? How?

You should definitely restrict access. Use nginx or another reliable proxy server for that.

#### How do I set up TLS/SSL on my server?

Use nginx or another reliable proxy server.

# Acknowledgements

Included projects are (Credits goes to them for the hard work):

- [macless-haystack](https://github.com/dchristl/macless-haystack), which this project is forked from.
- The original [Openhaystack](https://github.com/seemoo-lab/openhaystack)
  - Stripped down to the mobile application (Android) and ESP32 firmware. ESP32 firmware combined with FindYou project and optimizations in power usage.
  - Android application
  - ESP32 firmware
- [Biemster's FindMy](https://github.com/biemster/FindMy)
  - Customization in keypair generator to output an array for the ESP32 firmware and a json for import in the Android application.
  - The standalone python webserver for fetching the FindMy reports
- [Positive security's Find you](https://github.com/positive-security/find-you)
  - ESP32 firmware customization for battery optimization
- [acalatrava's OpenHaystack-Fimware alternative](https://github.com/acalatrava/openhaystack-firmware)
  - NRF5x firmware customization for battery optimization
