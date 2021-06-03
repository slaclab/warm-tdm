-------------------------------------------------------------------------------
-- Title      : Warm TDM Row Module
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Top level of RowModule 
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

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity RowModule is

   generic (
      TPD_G                   : time             := 1 ns;
      SIMULATION_G            : boolean          := false;
      SIM_PGP_PORT_NUM_G      : positive         := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : positive         := 8000;
      SIM_ETH_DATA_PORT_NUM_G : positive         := 9000;
      BUILD_INFO_G            : BuildInfoType;
      RING_ADDR_0_G           : boolean          := false;
      ETH_10G_G               : boolean          := false;
      DHCP_G                  : boolean          := false;  
      IP_ADDR_G               : slv(31 downto 0) := x"0C03A8C0";  -- 192.168.3.12 
      MAC_ADDR_G              : slv(47 downto 0) := x"0C_00_16_56_00_08");
   port (
      -- Clocks
      gtRefClk0P : in sl;
      gtRefClk0N : in sl;
      gtRefClk1P : in sl;
      gtRefClk1N : in sl;

      -- PGP Interface
      pgpTxP : out slv(1 downto 0);
      pgpTxN : out slv(1 downto 0);
      pgpRxP : in  slv(1 downto 0);
      pgpRxN : in  slv(1 downto 0);

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

      -- PROM interface
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

      -- DAC Interfaces
      dacCsB      : out slv(11 downto 0);
      dacSdio     : out slv(11 downto 0);
      dacSdo      : in  slv(11 downto 0);
      dacSclk     : out slv(11 downto 0);
      dacResetB   : out slv(11 downto 0) := (others => '1');
      dacTriggerB : out slv(11 downto 0) := (others => '1');
      dacClkP     : out slv(11 downto 0);
      dacClkN     : out slv(11 downto 0));


end entity RowModule;

architecture rtl of RowModule is

   constant AXI_CLK_FREQ_C : real := 125.0E6;

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(8);  -- Maybe packetizer config?

   constant NUM_AXIL_MASTERS_C : integer := 6;
   constant AXIL_COMMON_C      : integer := 0;
   constant AXIL_TIMING_C      : integer := 1;
   constant AXIL_PRBS_RX_C     : integer := 2;
   constant AXIL_PRBS_TX_C     : integer := 3;
   constant AXIL_DACS_C        : integer := 4;
   constant AXIL_COM_C         : integer := 5;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_COMMON_C   => (
         baseAddr     => X"00000000",
         addrBits     => 20,
         connectivity => X"FFFF"),
      AXIL_TIMING_C   => (
         baseAddr     => X"00100000",
         addrBits     => 16,
         connectivity => X"FFFF"),
      AXIL_PRBS_RX_C  => (
         baseAddr     => X"00200000",
         addrBits     => 12,
         connectivity => X"FFFF"),
      AXIL_PRBS_TX_C  => (
         baseAddr     => X"00201000",
         addrBits     => 8,
         connectivity => X"FFFF"),
      AXIL_DACS_C     => (
         baseAddr     => X"01000000",
         addrBits     => 24,
         connectivity => X"FFFF"),
      AXIL_COM_C      => (
         baseAddr     => X"A0000000",
         addrBits     => 24,
         connectivity => X"FFFF"));

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

   -- Timing clocks and data
   signal timingRxClk125 : sl;
   signal timingRxRst125 : sl;
   signal timingRxData   : LocalTimingType;


   -- Debug streams
   signal dataTxAxisMaster : AxiStreamMasterType;
   signal dataTxAxisSlave  : AxiStreamSlaveType;
   signal dataRxAxisMaster : AxiStreamMasterType;
   signal dataRxAxisSlave  : AxiStreamSlaveType;

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

   Heartbeat_timingTxClk : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 8.0E-9,
         PERIOD_OUT_G => 0.8)
      port map (
         clk => timingRxClk125,
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
         RING_ADDR_0_G     => RING_ADDR_0_G,
         AXIL_CLK_FREQ_G   => AXI_CLK_FREQ_C,
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
         timingRxClkOut  => timingRxClk125,                      -- [out]
         timingRxRstOut  => timingRxRst125,                      -- [out]
         timingRxDataOut => timingRxData,                        -- [out]
         timingTxClkP    => timingTxClkP,                        -- [out]
         timingTxClkN    => timingTxClkN,                        -- [out]
         timingTxDataP   => timingTxDataP,                       -- [out]
         timingTxDataN   => timingTxDataN,                       -- [out]
         xbarClkSel      => xbarClkSel,                          -- [out]
         xbarDataSel     => xbarDataSel,                         -- [out]
         xbarMgtSel      => xbarMgtSel,                          -- [out]         
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
         IP_ADDR_G               => IP_ADDR_G,
         MAC_ADDR_G              => MAC_ADDR_G)
      port map (
         gtRefClkP        => gtRefClk0P,                       -- [in]
         gtRefClkN        => gtRefClk0N,                       -- [in]
         gtRefClkDiv2Out  => gtRefClk0Div2,                    -- [out]
         pgpTxP           => pgpTxP,                           -- [out]
         pgpTxN           => pgpTxN,                           -- [out]
         pgpRxP           => pgpRxP,                           -- [in]
         pgpRxN           => pgpRxN,                           -- [in]
         ethRxP           => sfp0RxP,                          -- [in]
         ethRxN           => sfp0RxN,                          -- [in]
         ethTxP           => sfp0TxP,                          -- [out]
         ethTxN           => sfp0TxN,                          -- [out]
         axilClkOut       => axilClk,                          -- [out]
         rssiStatus       => rssiStatus,                       -- [out]
         ethPhyReady      => ethPhyReady,                      -- [out]
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
   -- Main crosbar
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
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_COMMON_C).baseAddr,
         AXIL_CLK_FREQ_G  => AXI_CLK_FREQ_C)
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


   U_RowModuleDacs_1 : entity warm_tdm.RowModuleDacs
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => SIMULATION_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_DACS_C).baseAddr)
      port map (
         axilClk         => axilClk,                           -- [in]
         axilRst         => axilRst,                           -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_DACS_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_DACS_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_DACS_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_DACS_C),    -- [out]
         timingRxClk125  => timingRxClk125,                    -- [in]
         timingRxRst125  => timingRxRst125,                    -- [in]
         timingRxData    => timingRxData,                      -- [in]
         dacCsB          => dacCsB,                            -- [out]
         dacSdio         => dacSdio,                           -- [out]
         dacSdo          => dacSdo,                            -- [in]
         dacSclk         => dacSclk,                           -- [out]
         dacResetB       => dacResetB,                         -- [out]
         dacTriggerB     => dacTriggerB,                       -- [out]
         dacClkP         => dacClkP,                           -- [out]
         dacClkN         => dacClkN);                          -- [out]



   -------------------------------------------------------------------------------------------------
   -- PRBS modules for connection debugging (maybe unnecessary)
   -------------------------------------------------------------------------------------------------
   U_SsiPrbsRx_1 : entity surf.SsiPrbsRx
      generic map (
         TPD_G                     => TPD_G,
         STATUS_CNT_WIDTH_G        => 32,
         SLAVE_READY_EN_G          => true,
         GEN_SYNC_FIFO_G           => true,
         SYNTH_MODE_G              => "inferred",
--          MEMORY_TYPE_G             => MEMORY_TYPE_G,
         SLAVE_AXI_STREAM_CONFIG_G => AXIS_CONFIG_C,
         SLAVE_AXI_PIPE_STAGES_G   => 1)
      port map (
         sAxisClk       => axilClk,                              -- [in]
         sAxisRst       => axilRst,                              -- [in]
         sAxisMaster    => dataRxAxisMaster,                     -- [in]
         sAxisSlave     => dataRxAxisSlave,                      -- [out]
         axiClk         => axilClk,                              -- [in]
         axiRst         => axilRst,                              -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_PRBS_RX_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_PRBS_RX_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_PRBS_RX_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_PRBS_RX_C));  -- [out]

   U_SsiPrbsTx_1 : entity surf.SsiPrbsTx
      generic map (
         TPD_G                      => TPD_G,
--          MEMORY_TYPE_G              => MEMORY_TYPE_G,
         GEN_SYNC_FIFO_G            => true,
         SYNTH_MODE_G               => "inferred",
         MASTER_AXI_STREAM_CONFIG_G => AXIS_CONFIG_C,
         MASTER_AXI_PIPE_STAGES_G   => 1)
      port map (
         mAxisClk        => axilClk,                              -- [in]
         mAxisRst        => axilRst,                              -- [in]
         mAxisMaster     => dataTxAxisMaster,                     -- [out]
         mAxisSlave      => dataTxAxisSlave,                      -- [in]
         locClk          => axilClk,                              -- [in]
         locRst          => axilRst,                              -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_PRBS_TX_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_PRBS_TX_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_PRBS_TX_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_PRBS_TX_C));  -- [out]




end architecture rtl;
