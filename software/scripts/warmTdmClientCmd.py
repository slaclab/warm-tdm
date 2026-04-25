#!/usr/bin/env python3
import argparse
import logging

import pyrogue
import pyrogue.pydm
import pyrogue.interfaces
import rogue

import os
# If WARM_TDM_PATH is not set, default to the repository root relative to this script
script_dir = os.path.dirname(os.path.abspath(__file__))
default_warm_tdm_path = os.path.join(script_dir, "..")
warm_tdm_path = os.path.abspath(
    os.path.expanduser(os.environ.get("WARM_TDM_PATH", default_warm_tdm_path))
)
pyrogue.addLibraryPath(os.path.join(warm_tdm_path, 'software/python/'))
pyrogue.addLibraryPath(os.path.join(warm_tdm_path, 'firmware/python/'))
pyrogue.addLibraryPath(os.path.join(warm_tdm_path, 'firmware/submodules/surf/python'))

import warm_tdm_api

#rogue.Logging.setFilter('pyrogue.memory.block', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#logging.getLogger('pyrogue.Device').setLevel(logging.DEBUG)
#logging.getLogger('pyrogue.Variable').setLevel(logging.DEBUG)

parser = argparse.ArgumentParser()

parser.add_argument(
    "--host",
    type     = str,
    required = False,
    default = 'localhost')

parser.add_argument(
    "--port",
    type     = int,
    required = False,
    default = 9099)


args = parser.parse_known_args()[0]


client = pyrogue.interfaces.VirtualClient(args.host, args.port)
#group = client.root.Group


def setSaFb(channel, value):
    group.SaFbForce.set(value=value, index=channel)

def setSaBias(channel, value):
    group.SaBias.set(value=value, index=channel)

def getSaOut(channel=-1):
    print(group.SaOut.get(index=channel))

def getSaOutAdc(channel=-1):
    print(group.SaOutAdc.get(index=channel))
    
