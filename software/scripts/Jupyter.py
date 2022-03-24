#!/usr/bin/env python3
import multiprocessing
import os
import argparse
import logging
import time 

import pyrogue
import pyrogue.pydm
import pyrogue.interfaces
import rogue

pyrogue.addLibraryPath(f'../python/')
pyrogue.addLibraryPath(f'../../firmware/python/')
pyrogue.addLibraryPath(f'../../firmware/submodules/surf/python')

import warm_tdm_api
import warm_tdm

#rogue.Logging.setFilter('pyrogue.memory.block', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.stream.TcpCore', rogue.Logging.Debug)
#rogue.Logging.setFilter('pyrogue.SrpV3', rogue.Logging.Debug)
#logging.getLogger('pyrogue.Device').setLevel(logging.DEBUG)
#logging.getLogger('pyrogue.Variable').setLevel(logging.DEBUG)

parser = argparse.ArgumentParser()

parser.add_argument(
    "--sim",
    action = 'store_true',
    default = False)

parser.add_argument(
    "--emulate",
    action = 'store_true',
    default = False)


parser.add_argument(
    "--ip",
    type     = str,
    required = False,
    default = '192.168.3.11',
    help     = "IP address")

parser.add_argument(
    "--rows",
    type     = int,
    default = 0,
    help     = "Number of row modules")

parser.add_argument(
    "--cols",
    type     = int,
    default = 1,
    help     = "Number of column modules")

# parser.add_argument(
#     "--plots",
#     action = 'store_true',
#     default = False)

# parser.add_argument(
#     "--docs",
#     type     = str,
#     required = False,
#     default = '',
#     help     = "Path To Store Docs")



# parser.add_argument(
#     "--host",
#     type     = str,
#     required = False,
#     default = 'localhost')

# parser.add_argument(
#     "--port",
#     type     = int,
#     required = False,
#     default = 9099)




args = parser.parse_known_args()[0]

groups = [{
    'host': args.ip,
    'colBoards': args.cols,
    'rowBoards': args.rows}]


config = warm_tdm_api.GroupConfig(rowBoards=groups[0]['rowBoards'],
                                  columnBoards=groups[0]['colBoards'],
                                  host=groups[0]['host'],
                                  rowOrder=None)

def run_server():

    with warm_tdm_api.GroupRoot(groupConfig=config, simulation=args.sim, emulate=args.emulate, plots=False, serverPort=9099) as root:
        print("Started Root and GUI")
        #pyrogue.pydm.runPyDM(root=root,title='Warm TDM',sizeX=2000,sizeY=2000,ui=warm_tdm_api.pydmUi)        
        pyrogue.waitCntrlC()

#multiprocessing.Process(target=run_server).start()

#time.sleep(2.0)

client = pyrogue.interfaces.VirtualClient('localhost', 9099)
group = client.root.Group
print("Created client")


def setSaFb(channel, value):
    group.SaFbForce.set(value=value, index=channel)

def setSaBias(channel, value):
    group.SaBias.set(value=value, index=channel)

def getSaOut(channel=-1):
    print(group.SaOut.get(index=channel))

def getSaOutAdc(channel=-1):
    print(group.SaOutAdc.get(index=channel))

def test(biasHigh, biasLow, biasSteps):
    print('Capturing Waveforms')
    wc = group.HardwareGroup.ColumnBoard[0].DataPath.WaveformCapture
    wcr = group.HardwareGroup.WaveformCaptureReceiver
    wc.AllChannels.set(True)
    wc.SelectedChannel.set(0)
    wc.CaptureWaveform()
    time.sleep(2)

    print('Running Offset Sweep')
    group.SaOffsetSweepProcess.Start()
    time.sleep(1)
    while group.SaOffsetSweepProcess.Running.get():
        time.sleep(1)

    print('Running SA Tune')
    group.SaTuneProcess.SaBiasLowOffset.set(biasLow)
    group.SaTuneProcess.SaBiasHighOffset.set(biasHigh)
    group.SaTuneProcess.SaBiasNumSteps.set(biasSteps)
    group.SaTuneProcess.Start()

    time.sleep(1)
    while group.SaTuneProcess.Running.get():
        time.sleep(1)

    wcr.HistogramPlot.get()
    wcr.PeriodogramPlot.get()
    group.SaOffsetSweepProcess.Plot.get()
    group.SaTuneProcess.Plot.get()
    
#os.system("python -m pyrogue gui --server='localhost:9099' &")

