-------------------------------------------------------------------------------
-- Title      : PGP PHY for 7-Series FPGAs
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx 7-Series
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: PGP2b PHY layer for 7-Series, using ClockManager7 and
--              Pgp2bGtx7VarLat with CPLL configuration.
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

entity PgpPhy7s is
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
end entity PgpPhy7s;

architecture rtl of PgpPhy7s is

   -- CPLL config for 250 MHz ref / 1.25 Gbps
   constant GTX_CPLL_FBDIV_C      : integer := 5;
   constant GTX_CPLL_FBDIV_45_C   : integer := 5;
   constant GTX_CPLL_REFCLK_DIV_C : integer := 1;
   constant GTX_OUT_DIV_C         : integer := 2;
   constant GTX_CLK25_DIV_C       : integer := 10;

   signal iAxiClk : sl;
   signal iAxiRst : sl;
   signal iPgpClk : sl;
   signal iPgpRst : sl;

begin

   axiClk <= iAxiClk;
   axiRst <= iAxiRst;
   pgpClk <= iPgpClk;
   pgpRst <= iPgpRst;

   U_ClockManager7 : entity surf.ClockManager7
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

   U_Pgp2bGtx7VarLat : entity surf.Pgp2bGtx7VarLat
      generic map (
         TPD_G                 => TPD_G,
         SIM_GTRESET_SPEEDUP_G => "TRUE",
         SIM_VERSION_G         => "4.0",
         TX_PLL_G              => "CPLL",
         RX_PLL_G              => "CPLL",
         CPLL_FBDIV_G          => GTX_CPLL_FBDIV_C,
         CPLL_FBDIV_45_G       => GTX_CPLL_FBDIV_45_C,
         CPLL_REFCLK_DIV_G     => GTX_CPLL_REFCLK_DIV_C,
         RXOUT_DIV_G           => GTX_OUT_DIV_C,
         TXOUT_DIV_G           => GTX_OUT_DIV_C,
         RX_CLK25_DIV_G        => GTX_CLK25_DIV_C,
         TX_CLK25_DIV_G        => GTX_CLK25_DIV_C,
         RX_OS_CFG_G           => "0000010000000",
         RXCDR_CFG_G           => X"03000023FF10100020",
         RXDFEXYDEN_G          => '1',
         PMA_RSV_G             => x"00018480",
         RX_DFE_KL_CFG2_G      => X"301148AC",
         VC_INTERLEAVE_G       => 1,
         PAYLOAD_CNT_TOP_G     => 7,
         NUM_VC_EN_G           => 2)
      port map (
         stableClk        => fabRefClk,
         gtCPllRefClk     => gtRefClk,
         gtCPllLock       => open,
         gtQPllRefClk     => '0',
         gtQPllClk        => '0',
         gtQPllLock       => '1',
         gtQPllRefClkLost => '0',
         gtQPllReset      => open,
         gtTxP            => pgpTxP,
         gtTxN            => pgpTxN,
         gtRxP            => pgpRxP,
         gtRxN            => pgpRxN,
         pgpTxReset       => iPgpRst,
         pgpTxRecClk      => open,
         pgpTxClk         => iPgpClk,
         pgpTxMmcmReset   => open,
         pgpTxMmcmLocked  => '1',
         pgpRxReset       => iPgpRst,
         pgpRxRecClk      => open,
         pgpRxClk         => iPgpClk,
         pgpRxMmcmReset   => open,
         pgpRxMmcmLocked  => '1',
         pgpTxIn          => pgpTxIn,
         pgpTxOut         => pgpTxOut,
         pgpRxIn          => pgpRxIn,
         pgpRxOut         => pgpRxOut,
         pgpTxMasters     => pgpTxMasters,
         pgpTxSlaves      => pgpTxSlaves,
         pgpRxMasters     => pgpRxMasters,
         pgpRxCtrl        => pgpRxCtrl,
         axilClk          => axilClk,
         axilRst          => axilRst,
         axilReadMaster   => axilReadMaster,
         axilReadSlave    => axilReadSlave,
         axilWriteMaster  => axilWriteMaster,
         axilWriteSlave   => axilWriteSlave);

end architecture rtl;
