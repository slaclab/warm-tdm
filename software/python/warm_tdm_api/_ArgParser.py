import argparse

import warm_tdm_api
import warm_tdm

class WarmTdmArgparse(argparse.ArgumentParser):
    def __init__(self):
        super().__init__()

        self.add_argument(
            "--gui",
            action = 'store_true',
            default = False,
            help = "Launch PyDM GUI after starting the server")

        self.add_argument(
            "--docs",
            type     = str,
            required = False,
            default = '',
            help     = "Path to store generated documentation")

        self.add_argument(
            "--sim",
            action = 'store_true',
            default = False,
            help = "Run in simulation mode (disables polling, increases timeout)")

        self.add_argument(
            "--emulate",
            action = 'store_true',
            default = False,
            help = "Run in emulation mode (no hardware)")

        self.add_argument(
            "--ip",
            type     = str,
            default = '192.168.3.11',
            help     = "IP address of the group coordinator board")

        self.add_argument(
            "--pollEn",
            action = 'store_true',
            default = False,
            help = 'Enable polling on startup')

        self.add_argument(
            "--initRead",
            action = 'store_true',
            default = True,
            help = 'Read all registers on startup')

        self.add_argument(
            "--rowBoards",
            type     = int,
            default  = 1,
            help     = "Number of row boards in group")

        self.add_argument(
            "--numRowSelects",
            type = int,
            default = 32,
            help = 'Number of row selects on row board')

        self.add_argument(
            "--numChipSelects",
            type = int,
            default = 0,
            help = 'Number of chip selects on row board')

        self.add_argument(
            "--rowAddrBits",
            type = int,
            default = 8,
            help = "Hardware row-address width: the deployed RTL generic "
                   "ROW_ADDR_BITS_G (3..8). The firmware row RAMs are "
                   "2**rowAddrBits deep. Default 8 (depth 256), the RTL default; "
                   "use 5 (depth 32) for the ColumnFpgaBoard160Coord target. "
                   "This must match the loaded bitfile.")

        self.add_argument(
            "--maxRows",
            type = int,
            default = 256,
            help = "Number of row indices the software maps/uses. A software "
                   "choice bounded by the hardware depth: 1 <= maxRows <= "
                   "2**rowAddrBits. Default 256 (full depth of an 8-bit build).")

        self.add_argument(
            "--columnBoards",
            type     = int,
            default  = 1,
            help     = "Number of column boards in group")

        self.add_argument(
            "--columnBoardType",
            choices= ['FPGA', 'AwaXe'],
            default= 'FPGA',
            help = "Column board hardware type")

        self.add_argument(
            "--rowBoardType",
            choices= ['FPGA'],
            default= 'FPGA',
            help = "Row board hardware type")

        self.add_argument(
            "--columnFrontEnd",
            choices= ['FpgaColFeb', 'FpgaColAwaXeFeb', 'FpgaColFebLnTes'],
            default= 'FpgaColFeb',
            help = "Column front-end board type")

        self.add_argument(
            "--floatPid",
            action = 'store_true',
            default = False,
            help = 'Use floating-point PID (AdcDspFp) instead of fixed-point')

        self.add_argument(
            "--rowFrontEnd",
            choices= ['FpgaRowFeb'],
            default= 'FpgaRowFeb',
            help = "Row front-end board type")


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
    ret['numRowSelects'] = args.numRowSelects
    ret['numChipSelects'] = args.numChipSelects
    ret['initRead'] = args.initRead and not args.sim
    ret['colBoardClass'] = colBoardDict[args.columnBoardType]
    ret['colFeClass'] = colFeDict[args.columnFrontEnd]
    ret['rowBoardClass'] = rowBoardDict[args.rowBoardType]
    ret['rowFeClass'] = rowFeDict[args.rowFrontEnd]
    ret['useFloatPid'] = args.floatPid
    ret['groupConfig'] = warm_tdm_api.GroupConfig(
        columnBoards=args.columnBoards,
        rowBoards=args.rowBoards,
        maxRows=args.maxRows,
        rowAddrBits=args.rowAddrBits,
        host=args.ip)
    return ret
