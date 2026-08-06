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
            "--maxRows",
            type = int,
            default = 256,
            help = "Maximum number of row indices to map registers for. "
                   "Default 256 = 2**ROW_ADDR_BITS_G(=8), the RTL default. Use "
                   "32 for the ColumnFpgaBoard160Coord target (ROW_ADDR_BITS_G=5).")

        self.add_argument(
            "--columnBoards",
            type     = int,
            default  = 1,
            help     = "Number of column boards in group")

        self.add_argument(
            "--columnBoardType",
            choices= ['Legacy', 'FPGA', 'AwaXe'],
            default= 'FPGA',
            help = "Column board hardware type")

        self.add_argument(
            "--rowBoardType",
            choices= ['Legacy', 'FPGA'],
            default= 'FPGA',
            help = "Row board hardware type")

        self.add_argument(
            "--columnFrontEnd",
            choices= ['Legacy', 'LegacyCh0Feb', 'FpgaColFeb', 'FpgaColAwaXeFeb', 'FpgaColFebLnTes'],
            default= 'FpgaColFeb',
            help = "Column front-end board type")

        self.add_argument(
            "--rowFrontEnd",
            choices= ['Legacy', 'FpgaRowFeb'],
            default= 'FpgaRowFeb',
            help = "Row front-end board type")

        # NOTE (wtj-cleanup-sw): --floatPid is accepted but currently IGNORED.
        # The floating-point PID firmware (_AdcDspFp) is on the deferred firmware
        # track and is not present in this firmware/python tree. The flag is kept
        # so command lines and the future FP path do not need to change; Group
        # emits a warning if it is set. Wire it up when the FP firmware lands.
        self.add_argument(
            "--floatPid",
            action = 'store_true',
            default = False,
            help = '(IGNORED on this branch) Use floating-point PID (AdcDspFp) '
                   'instead of fixed-point. Reserved for the FP firmware.')


colBoardDict = {
    'Legacy': warm_tdm.ColumnModule,
    'FPGA': warm_tdm.ColumnFpgaBoard,
    'AwaXe': warm_tdm.ColumnAwaXeFpgaBoard}


colFeDict = {
    'Legacy': warm_tdm.ColumnBoardC00StandardFrontEnd,
    'LegacyCh0Feb': warm_tdm.ColumnBoardC00FebBypassCh0,
    'FpgaColFeb': warm_tdm.FpgaBoardColumnFeb,
    'FpgaColAwaXeFeb': warm_tdm.FpgaBoardColumnAwaXeFeb,
    'FpgaColFebLnTes': warm_tdm.FpgaBoardColumnFebLnTes}

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
        host=args.ip)
    return ret
