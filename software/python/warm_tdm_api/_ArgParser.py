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
            default = True,
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
            default = 32,
            help = "Maximum number of physical rows available")

        self.add_argument(
            "--columnBoards",
            type     = int,
            default  = 1,
            help     = "Number of column boards in group")

        self.add_argument(
            "--columnBoardType",
            choices= ['Legacy', 'FPGA', 'AwaXe', 'Vesper'],
            default= 'Legacy')

        self.add_argument(
            "--rowBoardType",
            choices= ['Legacy', 'FPGA'],
            default= 'Legacy')

        self.add_argument(
            "--columnFrontEnd",
            choices= ['Legacy', 'LegacyCh0Feb', 'FpgaColFeb', 'FpgaColAwaXeFeb'],
            default= 'Legacy')

        self.add_argument(
            "--rowFrontEnd",
            choices= ['Legacy', 'FpgaRowFeb'],
            default= 'Legacy')


colBoardDict = {
    'Legacy': warm_tdm.ColumnModule,
    'FPGA': warm_tdm.ColumnFpgaBoard,
    'AwaXe': warm_tdm.ColumnAwaXeFpgaBoard,
    'Vesper': warm_tdm.ColumnVesperFpgaBoard
}


colFeDict = {
    'Legacy': warm_tdm.ColumnBoardC00StandardFrontEnd,
    'LegacyCh0Feb': warm_tdm.ColumnBoardC00FebBypassCh0,
    'FpgaColFeb': warm_tdm.FpgaBoardColumnFeb,
    'FpgaColAwaXeFeb':warm_tdm.FpgaBoardColumnAwaXeFeb,
    'FpgaColVesperFeb': warm_tdm.FpgaBoardColumnVesperFeb
}

rowBoardDict = {
    'Legacy': warm_tdm.RowModule,
    'FPGA': warm_tdm.RowFpgaBoard}

rowFeDict = {
    'Legacy': warm_tdm.RowBoardC01StandardFrontEnd,
    'FpgaRowFeb': warm_tdm.FpgaBoardRowFeb}


def arg_dict(args):
    ret = {}
    ret['pollEn'] = args.pollEn
    ret['simulation'] = args.sim
    ret['emulate'] = args.emulate
    ret['numRows'] = args.maxRows
    ret['initRead'] = False #args.initRead and not args.sim
    ret['colBoardClass'] = colBoardDict[args.columnBoardType]
    ret['colFeClass'] = colFeDict[args.columnFrontEnd]
    ret['rowBoardClass'] = rowBoardDict[args.rowBoardType]
    ret['rowFeClass'] = rowFeDict[args.rowFrontEnd]
    ret['groupConfig'] = warm_tdm_api.GroupConfig(groupId = 0,
                                                  rowBoards = args.rowBoards,
                                                  columnBoards = args.columnBoards,
                                                  host=args.ip)
    return ret
