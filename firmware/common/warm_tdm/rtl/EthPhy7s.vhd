-------------------------------------------------------------------------------
-- Title      : EthPhy7s
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Ethernet PHY layer for 7-Series FPGAs.
-- Handles clock generation, GT instantiation (QPLL + MAC/PCS), and outputs
-- ethClk/ethRst/phyReady. Supports 1 GbE (GigEthGtx7) and 10 GbE
-- (TenGigEthGtx7) via the ETH_10G_G generic.
-------------------------------------------------------------------------------
-- This file is part of 'KPIX'
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'KPIX', including this file,
-- may be copied, modified, propagated, or distributed except according to
-- the terms contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;
use surf.AxiStreamPkg.all;
use surf.EthMacPkg.all;

library unisim;
use unisim.vcomponents.all;

entity EthPhy7s is
   generic (
      TPD_G     : time    := 1 ns;
      ETH_10G_G : boolean := false);
   port (
      extRst          : in  sl;
      -- Reference clocks
      fabRefClk125    : in  sl;
      gtRefClk156     : in  sl;
      fabRefClk156    : in  sl;
      -- GT
      gtTxP           : out sl;
      gtTxN           : out sl;
      gtRxP           : in  sl;
      gtRxN           : in  sl;
      -- Outputs
      ethClk          : out sl;
      ethRst          : out sl;
      ethClkDiv2      : out sl;
      ethRstDiv2      : out sl;
      phyReady        : out sl;
      -- MAC interface
      localMac        : in  slv(47 downto 0);
      rxMaster        : out AxiStreamMasterType;
      rxSlave         : in  AxiStreamSlaveType;
      txMaster        : in  AxiStreamMasterType;
      txSlave         : out AxiStreamSlaveType;
      -- AXI-Lite for PHY registers
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType);
end entity EthPhy7s;

architecture rtl of EthPhy7s is

   signal ethClkLoc     : sl;
   signal ethRstLoc     : sl;
   signal ethClkDiv2Loc : sl;
   signal ethRstDiv2Loc : sl;
   signal refRst        : sl;
   signal pwrUpRst      : sl;
   signal qpllResetLoc  : sl;
   signal qpllLock      : sl;
   signal qpllOutClk    : sl;
   signal qpllOutRefClk : sl;
   signal qpllReset     : sl;

begin

   ethClk     <= ethClkLoc;
   ethRst     <= ethRstLoc;
   ethClkDiv2 <= ethClkDiv2Loc;
   ethRstDiv2 <= ethRstDiv2Loc;

   ---------------------------------------------------------------------------
   -- 1 GbE PHY
   ---------------------------------------------------------------------------
   GIG_ETH_GEN : if (not ETH_10G_G) generate

      U_PwrUpRst : entity surf.PwrUpRst
         generic map (
            TPD_G => TPD_G)
         port map (
            arst   => extRst,
            clk    => fabRefClk125,
            rstOut => refRst);

      ----------------
      -- Clock Manager
      ----------------
      U_MMCM : entity surf.ClockManager7
         generic map(
            TPD_G              => TPD_G,
            TYPE_G             => "MMCM",
            INPUT_BUFG_G       => false,
            FB_BUFG_G          => true,
            RST_IN_POLARITY_G  => '1',
            NUM_CLOCKS_G       => 2,
            -- MMCM attributes
            BANDWIDTH_G        => "OPTIMIZED",
            CLKIN_PERIOD_G     => 8.0,
            DIVCLK_DIVIDE_G    => 1,
            CLKFBOUT_MULT_F_G  => 8.0,
            CLKOUT0_DIVIDE_F_G => 8.0,
            CLKOUT1_DIVIDE_G   => 16)
         port map(
            clkIn     => fabRefClk125,
            rstIn     => refRst,
            clkOut(0) => ethClkLoc,
            clkOut(1) => ethClkDiv2Loc,
            rstOut(0) => ethRstLoc,
            rstOut(1) => ethRstDiv2Loc,
            locked    => open);

      -------------------------
      -- GigE Core for Kintex-7
      -------------------------
      U_ETH_PHY_MAC : entity surf.GigEthGtx7
         generic map (
            TPD_G                   => TPD_G,
            EN_AXI_REG_G            => true,
            AXIL_BASE_ADDR_G        => X"00000000",
            AXIL_CLK_IS_SYSCLK125_G => true,
            AXIS_CONFIG_G           => EMAC_AXIS_CONFIG_C)
         port map (
            -- Local Configurations
            localMac           => localMac,
            -- Streaming DMA Interface
            dmaClk             => ethClkLoc,
            dmaRst             => ethRstLoc,
            dmaIbMaster        => rxMaster,
            dmaIbSlave         => rxSlave,
            dmaObMaster        => txMaster,
            dmaObSlave         => txSlave,
            -- AXI-Lite Interface
            axiLiteClk         => axilClk,
            axiLiteRst         => axilRst,
            axiLiteReadMaster  => axilReadMaster,
            axiLiteReadSlave   => axilReadSlave,
            axiLiteWriteMaster => axilWriteMaster,
            axiLiteWriteSlave  => axilWriteSlave,
            -- PHY + MAC signals
            sysClk62           => ethClkDiv2Loc,
            sysClk125          => ethClkLoc,
            sysRst125          => ethRstLoc,
            extRst             => refRst,
            phyReady           => phyReady,
            -- MGT Ports
            gtTxP              => gtTxP,
            gtTxN              => gtTxN,
            gtRxP              => gtRxP,
            gtRxN              => gtRxN);

   end generate GIG_ETH_GEN;

   ---------------------------------------------------------------------------
   -- 10 GbE PHY
   ---------------------------------------------------------------------------
   TEN_GIG_ETH_GEN : if (ETH_10G_G) generate

      -- No ethClkDiv2 needed for 10G
      ethClkDiv2Loc <= '0';
      ethRstDiv2Loc <= '1';

      U_PwrUpRst : entity surf.PwrUpRst
         generic map (
            TPD_G => TPD_G)
         port map (
            arst   => extRst,
            clk    => fabRefClk156,
            rstOut => pwrUpRst);

      ----------------
      -- Clock Manager
      ----------------
      U_MMCM : entity surf.ClockManager7
         generic map(
            TPD_G              => TPD_G,
            TYPE_G             => "MMCM",
            INPUT_BUFG_G       => false,
            FB_BUFG_G          => true,
            RST_IN_POLARITY_G  => '1',
            NUM_CLOCKS_G       => 1,
            -- MMCM attributes
            BANDWIDTH_G        => "HIGH",
            CLKIN_PERIOD_G     => 6.4,
            DIVCLK_DIVIDE_G    => 1,
            CLKFBOUT_MULT_F_G  => 7.625,
            CLKOUT0_DIVIDE_F_G => 7.625)
         port map(
            clkIn     => fabRefClk156,
            rstIn     => pwrUpRst,
            clkOut(0) => ethClkLoc,
            rstOut(0) => ethRstLoc,
            locked    => open);

      --------------------
      -- QPLL for 10G GTX
      --------------------
      qpllResetLoc <= pwrUpRst or qpllReset;

      U_Gtx7QuadPll : entity surf.Gtx7QuadPll
         generic map (
            TPD_G               => TPD_G,
            SIM_RESET_SPEEDUP_G => "TRUE",
            SIM_VERSION_G       => "4.0",
            QPLL_CFG_G          => x"0680181",
            QPLL_REFCLK_SEL_G   => "001",
            QPLL_FBDIV_G        => "0101000000",
            QPLL_FBDIV_RATIO_G  => '0',
            QPLL_REFCLK_DIV_G   => 1)
         port map (
            qPllRefClk     => gtRefClk156,
            qPllOutClk     => qpllOutClk,
            qPllOutRefClk  => qpllOutRefClk,
            qPllLock       => qpllLock,
            qPllLockDetClk => '0',
            qPllRefClkLost => open,
            qPllPowerDown  => '0',
            qPllReset      => qpllResetLoc);

      --------------------------
      -- 10 GbE Core for GTX7
      --------------------------
      U_TenGigEthGtx7 : entity surf.TenGigEthGtx7
         generic map (
            TPD_G         => TPD_G,
            PAUSE_EN_G    => true,
            EN_AXI_REG_G  => true,
            AXIS_CONFIG_G => EMAC_AXIS_CONFIG_C)
         port map (
            -- Local Configurations
            localMac           => localMac,
            -- Streaming DMA Interface
            dmaClk             => ethClkLoc,
            dmaRst             => ethRstLoc,
            dmaIbMaster        => rxMaster,
            dmaIbSlave         => rxSlave,
            dmaObMaster        => txMaster,
            dmaObSlave         => txSlave,
            -- AXI-Lite Interface
            axiLiteClk         => axilClk,
            axiLiteRst         => axilRst,
            axiLiteReadMaster  => axilReadMaster,
            axiLiteReadSlave   => axilReadSlave,
            axiLiteWriteMaster => axilWriteMaster,
            axiLiteWriteSlave  => axilWriteSlave,
            -- PHY signals
            extRst             => extRst,
            phyClk             => ethClkLoc,
            phyRst             => ethRstLoc,
            phyReady           => phyReady,
            -- QPLL Interface
            qplllock           => qpllLock,
            qplloutclk         => qpllOutClk,
            qplloutrefclk      => qpllOutRefClk,
            qpllRst            => qpllReset,
            -- MGT Ports
            gtTxP              => gtTxP,
            gtTxN              => gtTxN,
            gtRxP              => gtRxP,
            gtRxN              => gtRxN);

   end generate TEN_GIG_ETH_GEN;

end architecture rtl;
