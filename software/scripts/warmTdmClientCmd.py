#!/usr/bin/env python3
import argparse
import logging

import pyrogue
import pyrogue.pydm
import pyrogue.interfaces
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

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
    
