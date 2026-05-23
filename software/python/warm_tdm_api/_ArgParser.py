import argparse

import warm_tdm_api
import warm_tdm

class WarmTdmArgparse(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()

        self.add_argument(
            "--docs",
            type     = str,
            required = False,
            default = '',
            help     = "Path To Store Docs")

        self.add_argument(
            "--sim",
            action = 'store_true',
            default = False)

        self.add_argument(
            "--emulate",
            action = 'store_true',
            default = False)

        self.add_argument(
            "--ip",
            type     = str,
            required = False,
            default = '192.168.3.11',
            help     = "IP address")

        self.add_argument(
            "--pollEn",
            type = bool,
            required = False,
            default = False,
            help = 'Enable or disable polling on startup')

        self.add_argument(
            "--initRead",
            type = bool,
            required = False,
            default = True,
            help = 'Enable or disable read of all register on startup')

        self.add_argument(
            "--rowBoards",
            type     = int,
            default  = 1,
            help     = "Number of row boards in group")

        self.add_argument(
            "--maxRows",
            type = int,
            default = 128,
            help = "Maximum number of row indices to map registers for")

        self.add_argument(
            "--columnBoards",
            type     = int,
            default  = 1,
            help     = "Number of column boards in group")

        self.add_argument(
            "--columnBoardType",
            choices= ['FPGA', 'AwaXe'],
            default= 'FPGA')

        self.add_argument(
            "--rowBoardType",
            choices= ['FPGA'],
            default= 'FPGA')

        self.add_argument(
            "--columnFrontEnd",
            choices= ['FpgaColFeb', 'FpgaColAwaXeFeb', 'FpgaColFebLnTes'],
            default= 'FpgaColFeb')

        self.add_argument(
            "--floatPid",
            action = 'store_true',
            default = False,
            help = 'Use floating-point PID (AdcDspFp) instead of fixed-point')

        self.add_argument(
            "--rowFrontEnd",
            choices= ['FpgaRowFeb'],
            default= 'FpgaRowFeb')


colBoardDict = {
    'FPGA': warm_tdm.ColumnFpgaBoard,
    'AwaXe': warm_tdm.ColumnAwaXeFpgaBoard}

colFeDict = {
    'FpgaColFeb': warm_tdm.FpgaBoardColumnFeb,
    'FpgaColAwaXeFeb': warm_tdm.FpgaBoardColumnAwaXeFeb,
    'FpgaColFebLnTes': warm_tdm.FpgaBoardColumnFebLnTes}

rowBoardDict = {
    'FPGA': warm_tdm.RowFpgaBoard}

rowFeDict = {
    'FpgaRowFeb': warm_tdm.FpgaBoardRowFeb}


def arg_dict(args):
    ret = {}
    ret['pollEn'] = args.pollEn
    ret['simulation'] = args.sim
    ret['emulate'] = args.emulate
    ret['maxRows'] = args.maxRows
    ret['initRead'] = False
    ret['colBoardClass'] = colBoardDict[args.columnBoardType]
    ret['colFeClass'] = colFeDict[args.columnFrontEnd]
    ret['rowBoardClass'] = rowBoardDict[args.rowBoardType]
    ret['rowFeClass'] = rowFeDict[args.rowFrontEnd]
    ret['useFloatPid'] = args.floatPid
    ret['groupConfig'] = warm_tdm_api.GroupConfig(
        columnBoards=args.columnBoards,
        rowBoards=args.rowBoards,
        maxRows=args.maxRows,
        host=args.ip)
    return ret
