-------------------------------------------------------------------------------
-- Title      : EthPhyUsp
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Ethernet PHY layer for UltraScale+ FPGAs.
-- Handles clock generation, GT instantiation (QPLL + MAC/PCS), and outputs
-- ethClk/ethRst/phyReady. Supports 1 GbE (GigEthGtyUltraScale) and 10 GbE
-- (TenGigEthGtyUltraScale) via the ETH_10G_G generic.
-------------------------------------------------------------------------------
-- This file is part of 'Warm TDM'
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'Warm TDM', including this file,
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

entity EthPhyUsp is
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
end entity EthPhyUsp;

architecture rtl of EthPhyUsp is

   signal ethClkLoc     : sl;
   signal ethRstLoc     : sl;
   signal ethClkDiv2Loc : sl;
   signal ethRstDiv2Loc : sl;
   signal refRst        : sl;
   signal pwrUpRst      : sl;

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
      U_MMCM : entity surf.ClockManagerUltraScale
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

      ---------------------------------
      -- GigE Core for UltraScale Plus
      ---------------------------------
      U_ETH_PHY_MAC : entity surf.GigEthGtyUltraScale
         generic map (
            TPD_G         => TPD_G,
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
      signal usQpllOutClk    : slv(1 downto 0);
      signal usQpllOutRefClk : slv(1 downto 0);
      signal usQpllLock      : slv(1 downto 0);
      signal usQpllReset     : slv(1 downto 0);
   begin

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
      U_MMCM : entity surf.ClockManagerUltraScale
         generic map(
            TPD_G              => TPD_G,
            TYPE_G             => "MMCM",
            INPUT_BUFG_G       => false,
            FB_BUFG_G          => true,
            RST_IN_POLARITY_G  => '1',
            NUM_CLOCKS_G       => 1,
            -- MMCM attributes
            BANDWIDTH_G        => "HIGH",
            CLKIN_PERIOD_G     => 12.8,    -- 78.125 MHz (156.25/2 from ODIV2)
            DIVCLK_DIVIDE_G    => 1,
            CLKFBOUT_MULT_F_G  => 16.0,   -- VCO = 78.125 * 16 = 1250 MHz
            CLKOUT0_DIVIDE_F_G => 8.0)    -- 1250 / 8 = 156.25 MHz
         port map(
            clkIn     => fabRefClk156,
            rstIn     => pwrUpRst,
            clkOut(0) => ethClkLoc,
            rstOut(0) => ethRstLoc,
            locked    => open);

      ---------------------------------
      -- QPLL for 10G GTY UltraScale+
      ---------------------------------
      U_GtyUltraScaleQuadPll : entity surf.GtyUltraScaleQuadPll
         generic map (
            TPD_G             => TPD_G,
            QPLL_REFCLK_SEL_G => (others => "001"),
            QPLL_FBDIV_G      => (others => 66),
            QPLL_REFCLK_DIV_G => (others => 1))
         port map (
            qPllRefClk(0)  => gtRefClk156,
            qPllRefClk(1)  => '0',
            qPllOutClk     => usQpllOutClk,
            qPllOutRefClk  => usQpllOutRefClk,
            qPllLock       => usQpllLock,
            qPllLockDetClk => (others => ethClkLoc),
            qPllReset      => usQpllReset);

      ------------------------------------
      -- 10 GbE Core for GTY UltraScale+
      ------------------------------------
      U_TenGigEthGtyUltraScale : entity surf.TenGigEthGtyUltraScale
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
            coreClk            => ethClkLoc,
            coreRst            => ethRstLoc,
            phyClk             => open,
            phyRst             => open,
            phyReady           => phyReady,
            -- QPLL Interface
            qplllock           => usQpllLock,
            qplloutclk         => usQpllOutClk,
            qplloutrefclk      => usQpllOutRefClk,
            qpllRst            => usQpllReset,
            -- MGT Ports
            gtTxP              => gtTxP,
            gtTxN              => gtTxN,
            gtRxP              => gtRxP,
            gtRxN              => gtRxN);

   end generate TEN_GIG_ETH_GEN;

end architecture rtl;
