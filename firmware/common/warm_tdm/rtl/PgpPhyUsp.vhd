-------------------------------------------------------------------------------
-- Title      : PGP PHY for UltraScale+ FPGAs
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: PGP2b PHY layer for UltraScale+, using ClockManagerUltraScale
--              and Pgp2bGtyUltra.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.Pgp2bPkg.all;
use surf.SsiPkg.all;

library unisim;
use unisim.vcomponents.all;

entity PgpPhyUsp is
   generic (
      TPD_G          : time := 1 ns;
      REF_CLK_FREQ_G : real := 250.0E+6);
   port (
      refRst          : in  sl;
      gtRefClk        : in  sl;
      fabRefClk       : in  sl;
      pgpTxP          : out sl;
      pgpTxN          : out sl;
      pgpRxP          : in  sl;
      pgpRxN          : in  sl;
      pgpClk          : out sl;
      pgpRst          : out sl;
      axiClk          : out sl;
      axiRst          : out sl;
      pgpTxIn         : in  Pgp2bTxInType;
      pgpTxOut        : out Pgp2bTxOutType;
      pgpRxIn         : in  Pgp2bRxInType;
      pgpRxOut        : out Pgp2bRxOutType;
      pgpTxMasters    : in  AxiStreamMasterArray(3 downto 0);
      pgpTxSlaves     : out AxiStreamSlaveArray(3 downto 0);
      pgpRxMasters    : out AxiStreamMasterArray(3 downto 0);
      pgpRxCtrl       : in  AxiStreamCtrlArray(3 downto 0);
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType);
end entity PgpPhyUsp;

architecture rtl of PgpPhyUsp is

   signal iAxiClk : sl;
   signal iAxiRst : sl;
   signal iPgpClk : sl;
   signal iPgpRst : sl;

begin

   axiClk <= iAxiClk;
   axiRst <= iAxiRst;
   pgpClk <= iPgpClk;
   pgpRst <= iPgpRst;

   U_ClockManagerUltraScale : entity surf.ClockManagerUltraScale
      generic map (
         TPD_G              => TPD_G,
         TYPE_G             => "MMCM",
         INPUT_BUFG_G       => false,
         FB_BUFG_G          => true,
         RST_IN_POLARITY_G  => '1',
         NUM_CLOCKS_G       => 2,
         BANDWIDTH_G        => "OPTIMIZED",
         CLKIN_PERIOD_G     => 8.0,
         DIVCLK_DIVIDE_G    => 1,
         CLKFBOUT_MULT_F_G  => 8.0,
         CLKOUT0_DIVIDE_F_G => 8.0,
         CLKOUT1_DIVIDE_G   => 16)
      port map (
         clkIn     => fabRefClk,
         rstIn     => refRst,
         clkOut(0) => iAxiClk,
         clkOut(1) => iPgpClk,
         rstOut(0) => iAxiRst,
         rstOut(1) => iPgpRst);

   U_Pgp2bGtyUltra : entity surf.Pgp2bGtyUltra
      generic map (
         TPD_G             => TPD_G,
         VC_INTERLEAVE_G   => 1,
         PAYLOAD_CNT_TOP_G => 7,
         NUM_VC_EN_G       => 2)
      port map (
         stableClk        => fabRefClk,
         stableRst        => refRst,
         gtRefClk         => gtRefClk,
         pgpGtTxP         => pgpTxP,
         pgpGtTxN         => pgpTxN,
         pgpGtRxP         => pgpRxP,
         pgpGtRxN         => pgpRxN,
         pgpTxReset       => iPgpRst,
         pgpTxResetDone   => open,
         pgpTxOutClk      => open,
         pgpTxClk         => iPgpClk,
         pgpTxMmcmLocked  => '1',
         pgpRxReset       => iPgpRst,
         pgpRxResetDone   => open,
         pgpRxOutClk      => open,
         pgpRxClk         => iPgpClk,
         pgpRxMmcmLocked  => '1',
         pgpTxIn          => pgpTxIn,
         pgpTxOut         => pgpTxOut,
         pgpRxIn          => pgpRxIn,
         pgpRxOut         => pgpRxOut,
         pgpTxMasters     => pgpTxMasters,
         pgpTxSlaves      => pgpTxSlaves,
         pgpRxMasters     => pgpRxMasters,
         pgpRxMasterMuxed => open,
         pgpRxCtrl        => pgpRxCtrl,
         axilClk          => axilClk,
         axilRst          => axilRst,
         axilReadMaster   => axilReadMaster,
         axilReadSlave    => axilReadSlave,
         axilWriteMaster  => axilWriteMaster,
         axilWriteSlave   => axilWriteSlave);

end architecture rtl;
