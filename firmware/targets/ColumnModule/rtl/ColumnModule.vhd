-------------------------------------------------------------------------------
-- Title      : Warm TDM Row Module
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Top level of ColumnModule 
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.I2cPkg.all;
use surf.SsiPkg.all;
use surf.Ad9681Pkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;


entity ColumnModule is

   generic (
      TPD_G                   : time             := 1 ns;
      SIMULATION_G            : boolean          := false;
      SIM_PGP_PORT_NUM_G      : positive         := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : positive         := 8000;
      SIM_ETH_DATA_PORT_NUM_G : positive         := 9000;
      BUILD_INFO_G            : BuildInfoType;
      RING_ADDR_0_G           : boolean          := true;
      ETH_10G_G               : boolean          := false;
      DHCP_G                  : boolean          := true;  -- true = DHCP, false = static address
      IP_ADDR_G               : slv(31 downto 0) := x"0A01A8C0");  -- 192.168.1.10 (before DHCP)
   port (
      -- Clocks
      gtRefClk0P : in sl;
      gtRefClk0N : in sl;
      gtRefClk1P : in sl;
      gtRefClk1N : in sl;

      -- PGP Interface
      pgpTxP : out sl;
      pgpTxN : out sl;
      pgpRxP : in  sl;
      pgpRxN : in  sl;

      -- Timing Interface Crossbars
      xbarDataSel : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarClkSel  : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarMgtSel  : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");

      -- MGT Timing
--       timingRxP : in sl;
--       timingRxN : in sl;
--       timingTxP : out sl;
--       timingTxN : out sl;


      -- SelectIO Timing
      timingRxClkP  : in  sl;
      timingRxClkN  : in  sl;
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      timingTxClkP  : out sl;
      timingTxClkN  : out sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl;

      -- Generic SFP interfaces
      sfp0TxP : out sl;
      sfp0TxN : out sl;
      sfp0RxP : in  sl;
      sfp0RxN : in  sl;
--       sfp1TxP : out sl;
--       sfp1TxN : out sl;
--       sfp1RxP : in  sl;
--       sfp1RxN : in  sl;

      -- Boot PROM interface
      bootCsL  : out sl;
      bootMosi : out sl;
      bootMiso : in  sl;

      -- Local I2C PROM
      promScl : inout sl;
      promSda : inout sl;

      -- Power Monitor I2C
      pwrScl : inout sl;
      pwrSda : inout sl;

      -- Status LEDs
      leds           : out slv(7 downto 0) := "00000000";
      conRxGreenLed  : out sl              := '1';
      conRxYellowLed : out sl              := '1';
      conTxGreenLed  : out sl              := '1';
      conTxYellowLed : out sl              := '1';

      oscOe : out slv(1 downto 0) := "11";

      -- XADC
      vAuxP : in slv(3 downto 0);
      vAuxN : in slv(3 downto 0);

      -- Fast DAC Interfaces - 3.3V
      sq1BiasDb    : out slv(13 downto 0);
      sq1BiasWrt   : out slv(3 downto 0);
      sq1BiasClk   : out slv(3 downto 0);
      sq1BiasSel   : out slv(3 downto 0);
      sq1BiasReset : out slv(3 downto 0);

      sq1FbDb    : out slv(13 downto 0);
      sq1FbWrt   : out slv(3 downto 0);
      sq1FbClk   : out slv(3 downto 0);
      sq1FbSel   : out slv(3 downto 0);
      sq1FbReset : out slv(3 downto 0);

      saFbDb    : out slv(13 downto 0);
      saFbWrt   : out slv(3 downto 0);
      saFbClk   : out slv(3 downto 0);
      saFbSel   : out slv(3 downto 0);
      saFbReset : out slv(3 downto 0);

      -- SA Bias DAC - 1.8V
      saDacMosi   : out sl;
      saDacMiso   : in  sl;
      saDacSclk   : out sl;
      saDacSyncB  : out sl;
      saDacLdacB  : out sl := '1';
      saDacResetB : out sl := '1';

      -- TES Bias DAC - 1.8V
      tesDacMosi   : out sl;
      tesDacMiso   : in  sl;
      tesDacSclk   : out sl;
      tesDacSyncB  : out sl;
      tesDacLdacB  : out sl := '1';
      tesDacResetB : out sl := '1';

      -- TES Delatch
      tesDelatch : out slv(7 downto 0) := (others => '0');

      -- ADC Data - LVDS
      adcFClkP : in  slv(1 downto 0);
      adcFClkN : in  slv(1 downto 0);
      adcDClkP : in  slv(1 downto 0);
      adcDClkN : in  slv(1 downto 0);
      adcChP   : in  slv8Array(1 downto 0);
      adcChN   : in  slv8Array(1 downto 0);
      adcClkP  : out sl;
      adcClkN  : out sl;

      -- ADC Config - 1.8V
      adcSclk : out   sl;
      adcSdio : inout sl;
      adcCsb  : out   sl;
      adcSync : out   sl

      );

end entity ColumnModule;

architecture rtl of ColumnModule is

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(8);  -- Maybe packetizer config?

   constant NUM_AXIL_MASTERS_C  : integer := 10;
   constant AXIL_COMMON_C       : integer := 0;
   constant AXIL_TIMING_C       : integer := 1;
   constant AXIL_ADC_CONFIG_C   : integer := 2;
   constant AXIL_DATA_PATH_C    : integer := 3;
   constant AXIL_SQ1_BIAS_DAC_C : integer := 4;
   constant AXIL_SQ1_FB_DAC_C   : integer := 5;
   constant AXIL_SA_FB_DAC_C    : integer := 6;
   constant AXIL_SA_BIAS_DAC_C  : integer := 7;
   constant AXIL_TES_BIAS_DAC_C : integer := 8;
   constant AXIL_COM_C          : integer := 9;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_COMMON_C       => (
         baseAddr         => X"00000000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_TIMING_C       => (
         baseAddr         => X"00100000",
         addrBits         => 16,
         connectivity     => X"FFFF"),
      AXIL_ADC_CONFIG_C   => (
         baseAddr         => X"00200000",
         addrBits         => 16,
         connectivity     => X"FFFF"),
      AXIL_DATA_PATH_C    => (
         baseAddr         => X"00300000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SQ1_BIAS_DAC_C => (
         baseAddr         => X"00400000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SQ1_FB_DAC_C   => (
         baseAddr         => X"00500000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SA_FB_DAC_C    => (
         baseAddr         => X"00600000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SA_BIAS_DAC_C  => (
         baseAddr         => X"00700000",
         addrBits         => 12,
         connectivity     => X"FFFF"),
      AXIL_TES_BIAS_DAC_C => (
         baseAddr         => X"00701000",
         addrBits         => 12,
         connectivity     => X"FFFF"),
      AXIL_COM_C          => (
         baseAddr         => X"A0000000",
         addrBits         => 24,
         connectivity     => X"FFFF"));

   signal axilClk : sl;
   signal axilRst : sl;

   signal srpAxilWriteMaster : AxiLiteWriteMasterType;
   signal srpAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal srpAxilReadMaster  : AxiLiteReadMasterType;
   signal srpAxilReadSlave   : AxiLiteReadSlaveType;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   -- Data Streams
   signal dataTxAxisMaster : AxiStreamMasterType;
   signal dataTxAxisSlave  : AxiStreamSlaveType;
   signal dataRxAxisMaster : AxiStreamMasterType;
   signal dataRxAxisSlave  : AxiStreamSlaveType;

   -- Timing clocks and data
   signal timingClk125 : sl;
   signal timingRst125 : sl;
   signal timingData   : LocalTimingType;

   signal adc : Ad9681SerialType;

   -- Debug clocks
   signal gtRefClk0Div2 : sl;
   signal gtRefClk1     : sl;
   signal rssiStatus    : slv7Array(1 downto 0);
   signal ethPhyReady   : sl;


begin

   Heartbeat_gtRefClk0Div2 : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 6.4E-9,
         PERIOD_OUT_G => 0.64)
      port map (
         clk => gtRefClk0Div2,
         o   => leds(0));

   Heartbeat_gtRefClk1 : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 8.0E-9,
         PERIOD_OUT_G => 0.8)
      port map (
         clk => gtRefClk1,
         o   => leds(1));

   Heartbeat_axilClk : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 6.4E-9,
         PERIOD_OUT_G => 0.64)
      port map (
         clk => axilClk,
         o   => leds(2));

   Heartbeat_timingRxClk : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 8.0E-9,
         PERIOD_OUT_G => 0.8)
      port map (
         clk => timingClk125,
         o   => leds(3));

   leds(4) <= rssiStatus(0)(0);
   leds(5) <= rssiStatus(1)(0);
   leds(6) <= ethPhyReady;

   -------------------------------------------------------------------------------------------------
   -- Timing Interface
   -------------------------------------------------------------------------------------------------
   U_Timing_1 : entity warm_tdm.Timing
      generic map (
         TPD_G             => TPD_G,
         SIMULATION_G      => SIMULATION_G,
         AXIL_BASE_ADDR_G  => AXIL_XBAR_CFG_C(AXIL_TIMING_C).baseAddr,
         IODELAY_GROUP_G   => "IODELAY0",
         IDELAYCTRL_FREQ_G => 200.0)
      port map (
         timingRefClkP   => gtRefClk1P,                          -- [in]
         timingRefClkN   => gtRefClk1N,                          -- [in]
         timingRefClkOut => gtRefClk1,                           -- [out]
         timingRxClkP    => timingRxClkP,                        -- [in]
         timingRxClkN    => timingRxClkN,                        -- [in]
         timingRxDataP   => timingRxDataP,                       -- [in]
         timingRxDataN   => timingRxDataN,                       -- [in]
         timingClkOut    => timingClk125,                        -- [out]
         timingRstOut    => timingRst125,                        -- [out]
         timingDataOut   => timingData,                          -- [out]
         timingTxClkP    => timingTxClkP,                        -- [out]
         timingTxClkN    => timingTxClkN,                        -- [out]
         timingTxDataP   => timingTxDataP,                       -- [out]
         timingTxDataN   => timingTxDataN,                       -- [out]
         axilClk         => axilClk,                             -- [in]
         axilRst         => axilRst,                             -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_TIMING_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_TIMING_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_TIMING_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_TIMING_C));   -- [out]

   -------------------------------------------------------------------------------------------------
   -- Communications Interfaces
   -------------------------------------------------------------------------------------------------
   U_ComCore_1 : entity warm_tdm.ComCore
      generic map (
         TPD_G                   => TPD_G,
         SIMULATION_G            => SIMULATION_G,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         RING_ADDR_0_G           => RING_ADDR_0_G,
         AXIL_BASE_ADDR_G        => AXIL_XBAR_CFG_C(AXIL_COM_C).baseAddr,
         ETH_10G_G               => ETH_10G_G,
         DHCP_G                  => DHCP_G,
         IP_ADDR_G               => IP_ADDR_G)
      port map (
         gtRefClkP        => gtRefClk0P,                       -- [in]
         gtRefClkN        => gtRefClk0N,                       -- [in]
         gtRefClkDiv2Out  => gtRefClkDiv2Out,                  -- [out]
         pgpTxP           => pgpTxP,                           -- [out]
         pgpTxN           => pgpTxN,                           -- [out]
         pgpRxP           => pgpRxP,                           -- [in]
         pgpRxN           => pgpRxN,                           -- [in]
         ethRxP           => sfp0RxP,                          -- [in]
         ethRxN           => sfp0RxN,                          -- [in]
         ethTxP           => sfp0TxP,                          -- [out]
         ethTxN           => sfp0TxN,                          -- [out]
         axilClkOut       => axilClk,                          -- [out]
         axilRstOut       => axilRst,                          -- [out]
         mAxilWriteMaster => srpAxilWriteMaster,               -- [out]
         mAxilWriteSlave  => srpAxilWriteSlave,                -- [in]
         mAxilReadMaster  => srpAxilReadMaster,                -- [out]
         mAxilReadSlave   => srpAxilReadSlave,                 -- [in]
         sAxilWriteMaster => locAxilWriteMasters(AXIL_COM_C),  -- [in]
         sAxilWriteSlave  => locAxilWriteSlaves(AXIL_COM_C),   -- [out]
         sAxilReadMaster  => locAxilReadMasters(AXIL_COM_C),   -- [in]
         sAxilReadSlave   => locAxilReadSlaves(AXIL_COM_C),    -- [out]
         dataTxAxisMaster => dataTxAxisMaster,                 -- [in]
         dataTxAxisSlave  => dataTxAxisSlave,                  -- [out]
         dataRxAxisMaster => dataRxAxisMaster,                 -- [out]
         dataRxAxisSlave  => dataRxAxisSlave);                 -- [in]


   -------------------------------------------------------------------------------------------------
   -- Main crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_Main : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,              -- [in]
         axiClkRst           => axilRst,              -- [in]
         sAxiWriteMasters(0) => srpAxilWriteMaster,   -- [in]
         sAxiWriteSlaves(0)  => srpAxilWriteSlave,    -- [out]
         sAxiReadMasters(0)  => srpAxilReadMaster,    -- [in]
         sAxiReadSlaves(0)   => srpAxilReadSlave,     -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]


   -------------------------------------------------------------------------------------------------
   -- Common components
   -------------------------------------------------------------------------------------------------
   U_WarmTdmCommon_1 : entity warm_tdm.WarmTdmCommon
      generic map (
         TPD_G            => TPD_G,
         BUILD_INFO_G     => BUILD_INFO_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_COMMON_C).baseAddr)
      port map (
         axilClk         => axilClk,                             -- [in]
         axilRst         => axilRst,                             -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_COMMON_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_COMMON_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_COMMON_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_COMMON_C),    -- [out]
         bootCsL         => bootCsL,                             -- [out]
         bootMosi        => bootMosi,                            -- [out]
         bootMiso        => bootMiso,                            -- [in]
         promScl         => promScl,                             -- [inout]
         promSda         => promSda,                             -- [inout]
         pwrScl          => pwrScl,                              -- [inout]
         pwrSda          => pwrSda,                              -- [inout]
         vAuxP           => vAuxP,                               -- [in]
         vAuxN           => vAuxN);                              -- [in]


   -------------------------------------------------------------------------------------------------
   -- SA Bias
   -------------------------------------------------------------------------------------------------
   U_SA_BIAS_SPI : entity surf.AxiSpiMaster
      generic map (
         TPD_G             => TPD_G,
         ADDRESS_SIZE_G    => 8,
         DATA_SIZE_G       => 16,
         MODE_G            => "WO",
         SHADOW_EN_G       => true,
         CPHA_G            => '1',
         CPOL_G            => '0',
         CLK_PERIOD_G      => 6.4e-9,
         SPI_SCLK_PERIOD_G => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         SPI_NUM_CHIPS_G   => 1)
      port map (
         axiClk         => axilClk,                                  -- [in]
         axiRst         => axilRst,                                  -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_SA_BIAS_DAC_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_SA_BIAS_DAC_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_SA_BIAS_DAC_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_SA_BIAS_DAC_C),   -- [out]
         coreSclk       => saDacSclk,                                -- [out]
         coreSDin       => saDacMiso,                                -- [in]
         coreSDout      => saDacMosi,                                -- [out]
         coreMCsb(0)    => saDacSyncB);                              -- [out]

   -------------------------------------------------------------------------------------------------
   -- TES Bias
   -------------------------------------------------------------------------------------------------
   U_TES_BIAS_SPI : entity surf.AxiSpiMaster
      generic map (
         TPD_G             => TPD_G,
         ADDRESS_SIZE_G    => 8,
         DATA_SIZE_G       => 16,
         MODE_G            => "WO",
         SHADOW_EN_G       => true,
         CPHA_G            => '1',
         CPOL_G            => '0',
         CLK_PERIOD_G      => 6.4E-9,
         SPI_SCLK_PERIOD_G => ite(SIMULATION_G, 100.0E-9, 1.0e-6),
         SPI_NUM_CHIPS_G   => 1)
      port map (
         axiClk         => axilClk,                                   -- [in]
         axiRst         => axilRst,                                   -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_TES_BIAS_DAC_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_TES_BIAS_DAC_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_TES_BIAS_DAC_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_TES_BIAS_DAC_C),   -- [out]
         coreSclk       => tesDacSclk,                                -- [out]
         coreSDin       => tesDacMiso,                                -- [in]
         coreSDout      => tesDacMosi,                                -- [out]
         coreMCsb(0)    => tesDacSyncB);                              -- [out]


   -------------------------------------------------------------------------------------------------
   -- ADC Config
   -------------------------------------------------------------------------------------------------
   U_Ad9249Config_1 : entity surf.Ad9681Config
      generic map (
         TPD_G             => TPD_G,
         NUM_CHIPS_G       => 1,
         SCLK_PERIOD_G     => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         AXIL_CLK_PERIOD_G => 6.4E-9)
      port map (
         axilClk         => axilClk,                                 -- [in]
         axilRst         => axilRst,                                 -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_ADC_CONFIG_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_ADC_CONFIG_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_ADC_CONFIG_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_ADC_CONFIG_C),   -- [out]
--         adcPdwn(0)      => adcPdwn,                                 -- [out]
         adcSclk         => adcSclk,                                 -- [out]
         adcSdio         => adcSdio,                                 -- [inout]
         adcCsb(0)       => adcCsb);                                 -- [out]


   -------------------------------------------------------------------------------------------------
   -- ADC Data Path
   -------------------------------------------------------------------------------------------------
   adc.fClkP <= adcFClkP;
   adc.fClkN <= adcFClkN;
   adc.dClkP <= adcDClkP;
   adc.dClkN <= adcDClkN;
   adc.chP   <= adcChP;
   adc.chN   <= adcChN;

   U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
      generic map (
         TPD_G => TPD_G)
      port map (
         clkIn   => timingClk125,       -- [in]
         clkOutP => adcClkP,            -- [out]
         clkOutN => adcClkN);           -- [out]


   U_DataPath_1 : entity warm_tdm.DataPath
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_DATA_PATH_C).baseAddr,
         IODELAY_GROUP_G  => "IODELAY0")
      port map (
         adc             => adc,                                    -- [in]
         timingClk125    => timingClk125,                           -- [in]
         timingRst125    => timingRst125,                           -- [in]
         timingData      => timingData,                             -- [in]
         axisClk         => axilClk,                                -- [in]
         axisRst         => axilRst,                                -- [in]
         axisMaster      => dataTxAxisMaster,                       -- [out]
         axisSlave       => dataTxAxisSlave,                        -- [in]
         axilClk         => axilClk,                                -- [in]
         axilRst         => axilRst,                                -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_DATA_PATH_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_DATA_PATH_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_DATA_PATH_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_DATA_PATH_C));  -- [out]

   -------------------------------------------------------------------------------------------------
   -- Fast DAC drivers
   -------------------------------------------------------------------------------------------------
   U_FastDacDriver_SQ1_BIAS : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_BIAS_DAC_C).baseAddr)
      port map (
         timingClk125    => timingClk125,                              -- [in]
         timingRst125    => timingRst125,                              -- [in]
         timingData      => timingData,                                -- [in]
         dacDb           => sq1BiasDb,                                 -- [out]
         dacWrt          => sq1BiasWrt,                                -- [out]
         dacClk          => sq1BiasClk,                                -- [out]
         dacSel          => sq1BiasSel,                                -- [out]
         dacReset        => sq1BiasReset,                              -- [out]
         axilClk         => axilClk,                                   -- [in]
         axilRst         => axilRst,                                   -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_SQ1_BIAS_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SQ1_BIAS_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_SQ1_BIAS_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SQ1_BIAS_DAC_C));   -- [out]

   U_FastDacDriver_SQ1_FB : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_FB_DAC_C).baseAddr)
      port map (
         timingClk125    => timingClk125,                            -- [in]
         timingRst125    => timingRst125,                            -- [in]
         timingData      => timingData,                              -- [in]
         dacDb           => sq1FbDb,                                 -- [out]
         dacWrt          => sq1FbWrt,                                -- [out]
         dacClk          => sq1FbClk,                                -- [out]
         dacSel          => sq1FbSel,                                -- [out]
         dacReset        => sq1FbReset,                              -- [out]
         axilClk         => axilClk,                                 -- [in]
         axilRst         => axilRst,                                 -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_SQ1_FB_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SQ1_FB_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_SQ1_FB_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SQ1_FB_DAC_C));   -- [out]

   U_FastDacDriver_SA_FB : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SA_FB_DAC_C).baseAddr)
      port map (
         timingClk125    => timingClk125,                           -- [in]
         timingRst125    => timingRst125,                           -- [in]
         timingData      => timingData,                             -- [in]
         dacDb           => saFbDb,                                 -- [out]
         dacWrt          => saFbWrt,                                -- [out]
         dacClk          => saFbClk,                                -- [out]
         dacSel          => saFbSel,                                -- [out]
         dacReset        => saFbReset,                              -- [out]
         axilClk         => axilClk,                                -- [in]
         axilRst         => axilRst,                                -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_SA_FB_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SA_FB_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_SA_FB_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SA_FB_DAC_C));   -- [out]
end architecture rtl;
