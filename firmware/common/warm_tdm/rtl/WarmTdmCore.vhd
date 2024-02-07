-------------------------------------------------------------------------------
-- Title      : Warm TDM Core
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;
use surf.AxiStreamPkg.all;

library warm_tdm;
use warm_tdm.WarmTdmPkg.all;
use warm_tdm.TimingPkg.all;

entity WarmTdmCore is

   generic (
      TPD_G                   : time                     := 1 ns;
      SIMULATION_G            : boolean                  := false;
      SIM_PGP_PORT_NUM_G      : integer                  := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer                  := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer                  := 9000;
      BUILD_INFO_G            : BuildInfoType;
      RING_ADDR_0_G           : boolean                  := false;
      ETH_10G_G               : boolean                  := false;
      DHCP_G                  : boolean                  := false;
      IP_ADDR_G               : slv(31 downto 0)         := x"0B03A8C0";  -- 192.168.3.11
      MAC_ADDR_G              : slv(47 downto 0)         := x"0B_00_16_56_00_08";
      XADC_AUX_CHANS_G        : IntegerArray(3 downto 0) := (12, 4, 11, 3));

   port (
      ----------------
      -- IO Interfaces
      ----------------
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
      xbarDataSel   : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarClkSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarMgtSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarTimingSel : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");

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

      -- Board thermistors
      vAuxP : in slv(3 downto 0);
      vAuxN : in slv(3 downto 0);

      ---------------------
      -- Firmware Intefaces
      ---------------------
      -- AxiLite interface
      axilClk         : out sl;
      axilRst         : out sl;
      axilWriteMaster : out AxiLiteWriteMasterType;
      axilWriteSlave  : in  AxiLiteWriteSlaveType;
      axilReadMaster  : out AxiLiteReadMasterType;
      axilReadSlave   : in  AxiLiteReadSlaveType;

      -- Data Streamss
      axisClk          : out sl;
      axisRst          : out sl;
      dataTxAxisMaster : in  AxiStreamMasterType;
      dataTxAxisSlave  : out AxiStreamSlaveType;
      dataRxAxisMaster : out AxiStreamMasterType;
      dataRxAxisSlave  : in  AxiStreamSlaveType := AXI_STREAM_SLAVE_FORCE_C;


      -- Timing Rx
      timingRxClk125 : out sl;
      timingRxRst125 : out sl;
      timingRxData   : out LocalTimingType);



end entity WarmTdmCore;

architecture rtl of WarmTdmCore is

   constant NUM_AXIL_MASTERS_C : integer := 4;
   constant AXIL_COMMON_C      : integer := 0;
   constant AXIL_TIMING_C      : integer := 1;
   constant AXIL_COM_C         : integer := 2;
   constant AXIL_APP_C         : integer := 3;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_COMMON_C   => (
         baseAddr     => X"00000000",
         addrBits     => 20,
         connectivity => X"FFFF"),
      AXIL_TIMING_C   => (
         baseAddr     => X"00100000",
         addrBits     => 20,
         connectivity => X"FFFF"),
      AXIL_COM_C      => (
         baseAddr     => X"A0000000",
         addrBits     => 24,
         connectivity => X"FFFF"),
      AXIL_APP_C      => (
         baseAddr     => APP_BASE_ADDR_C,
         addrBits     => 28,
         connectivity => X"FFFF"));

   signal locAxilClk : sl;
   signal locAxilRst : sl;

   signal srpAxilWriteMaster : AxiLiteWriteMasterType;
   signal srpAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal srpAxilReadMaster  : AxiLiteReadMasterType;
   signal srpAxilReadSlave   : AxiLiteReadSlaveType;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);


   signal fabRefClk0 : sl;
   signal fabRefClk1 : sl;
   signal gtRefClk0  : sl;
   signal gtRefClk1  : sl;

   signal rssiStatus  : slv7Array(1 downto 0);
   signal ethPhyReady : sl;

   signal locTimingRxClk125 : sl;


begin

   axilClk <= locAxilClk;
   axilRst <= locAxilRst;
   axisClk <= locAxilClk;
   axisRst <= locAxilRst;

   timingRxClk125 <= locTimingRxClk125;

   Heartbeat_RefClk0 : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 6.4E-9,
         PERIOD_OUT_G => 0.64)
      port map (
         clk => fabRefClk0,
         o   => leds(0));

   Heartbeat_RefClk1 : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 4.0E-9,
         PERIOD_OUT_G => 0.4)
      port map (
         clk => fabRefClk1,
         o   => leds(1));

   Heartbeat_axilClk : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 6.4E-9,
         PERIOD_OUT_G => 0.64)
      port map (
         clk => locAxilClk,
         o   => leds(2));

   Heartbeat_timingRxClk : entity surf.Heartbeat
      generic map (
         TPD_G        => TPD_G,
         PERIOD_IN_G  => 8.0E-9,
         PERIOD_OUT_G => 0.8)
      port map (
         clk => locTimingRxClk125,
         o   => leds(3));

   leds(4) <= rssiStatus(0)(0);
   leds(5) <= rssiStatus(1)(0);
   leds(6) <= ethPhyReady;

   -------------------------------------------------------------------------------------------------
   -- APP AXI-Lite
   -------------------------------------------------------------------------------------------------
   axilWriteMaster                <= locAxilWriteMasters(AXIL_APP_C);
   locAxilWriteSlaves(AXIL_APP_C) <= axilWriteSlave;
   axilReadMaster                 <= locAxilReadMasters(AXIL_APP_C);
   locAxilReadSlaves(AXIL_APP_C)  <= axilReadSlave;


   -------------------------------------------------------------------------------------------------
   -- Clock buffers
   -------------------------------------------------------------------------------------------------
   U_ClockDist_1 : entity warm_tdm.ClockDist
      generic map (
         TPD_G        => TPD_G,
         CLK_0_DIV2_G => true,
         CLK_1_DIV2_G => true)
      port map (
         gtRefClk0P => gtRefClk0P,      -- [in]
         gtRefClk0N => gtRefClk0N,      -- [in]
         gtRefClk0  => gtRefClk0,       -- [out]
         fabRefClk0 => fabRefClk0,      -- [out]
         gtRefClk1P => gtRefClk1P,      -- [in]
         gtRefClk1N => gtRefClk1N,      -- [in]
         gtRefClk1  => gtRefClk1,       -- [out]
         fabRefClk1 => fabRefClk1);     -- [out]

   -------------------------------------------------------------------------------------------------
   -- Crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_Main : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => locAxilClk,           -- [in]
         axiClkRst           => locAxilRst,           -- [in]
         sAxiWriteMasters(0) => srpAxilWriteMaster,   -- [in]
         sAxiWriteSlaves(0)  => srpAxilWriteSlave,    -- [out]
         sAxiReadMasters(0)  => srpAxilReadMaster,    -- [in]
         sAxiReadSlaves(0)   => srpAxilReadSlave,     -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]

   -------------------------------------------------------------------------------------------------
   -- Timing Interface
   -------------------------------------------------------------------------------------------------
   U_Timing_1 : entity warm_tdm.Timing
      generic map (
         TPD_G             => TPD_G,
         SIMULATION_G      => SIMULATION_G,
         RING_ADDR_0_G     => RING_ADDR_0_G,
         AXIL_CLK_FREQ_G   => AXIL_CLK_FREQ_C,
         AXIL_BASE_ADDR_G  => AXIL_XBAR_CFG_C(AXIL_TIMING_C).baseAddr,
         IODELAY_GROUP_G   => "IODELAY0",
         IDELAYCTRL_FREQ_G => 200.0)
      port map (
         timingGtRefClk  => gtRefClk1,  -- [in]
         timingFabRefClk => fabRefClk1,     -- [in]
         timingRxClkP    => timingRxClkP,   -- [in]
         timingRxClkN    => timingRxClkN,   -- [in]
         timingRxDataP   => timingRxDataP,  -- [in]
         timingRxDataN   => timingRxDataN,  -- [in]
         timingRxClkOut  => locTimingRxClk125,                   -- [out]
         timingRxRstOut  => timingRxRst125,                      -- [out]
         timingRxDataOut => timingRxData,   -- [out]
         timingTxClkP    => timingTxClkP,   -- [out]
         timingTxClkN    => timingTxClkN,   -- [out]
         timingTxDataP   => timingTxDataP,  -- [out]
         timingTxDataN   => timingTxDataN,  -- [out]
         xbarClkSel      => xbarClkSel,     -- [out]
         xbarDataSel     => xbarDataSel,    -- [out]
         xbarMgtSel      => xbarMgtSel,     -- [out]
         xbarTimingSel   => xbarTimingSel,  -- [out]                                                                 -- 
         axilClk         => locAxilClk,     -- [in]
         axilRst         => locAxilRst,     -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_TIMING_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_TIMING_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_TIMING_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_TIMING_C));   -- [out]

   -------------------------------------------------------------------------------------------------
   -- Communications Interfaces
   -------------------------------------------------------------------------------------------------
   U_PgpEthCore_1 : entity warm_tdm.PgpEthCore
      generic map (
         TPD_G                   => TPD_G,
         SIMULATION_G            => SIMULATION_G,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         REF_CLK_FREQ_G          => 250.0E6,
         RING_ADDR_0_G           => RING_ADDR_0_G,
         AXIL_BASE_ADDR_G        => AXIL_XBAR_CFG_C(AXIL_COM_C).baseAddr,
         ETH_10G_G               => ETH_10G_G,
         DHCP_G                  => DHCP_G,
         IP_ADDR_G               => IP_ADDR_G,
         MAC_ADDR_G              => MAC_ADDR_G)
      port map (
         gtRefClk         => gtRefClk1,                        -- [in]
         fabRefClk        => fabRefClk1,                       -- [in]
         pgpTxP           => pgpTxP,                           -- [out]
         pgpTxN           => pgpTxN,                           -- [out]
         pgpRxP           => pgpRxP,                           -- [in]
         pgpRxN           => pgpRxN,                           -- [in]
         ethRxP           => sfp0RxP,                          -- [in]
         ethRxN           => sfp0RxN,                          -- [in]
         ethTxP           => sfp0TxP,                          -- [out]
         ethTxN           => sfp0TxN,                          -- [out]
         rssiStatus       => rssiStatus,                       -- [out]
         ethPhyReady      => ethPhyReady,                      -- [out]
         axilClkOut       => locAxilClk,                       -- [out]
         axilRstOut       => locAxilRst,                       -- [out]
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
   -- Common components
   -------------------------------------------------------------------------------------------------
   U_WarmTdmCommon_1 : entity warm_tdm.WarmTdmCommon
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => SIMULATION_G,
         BUILD_INFO_G     => BUILD_INFO_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_COMMON_C).baseAddr,
         AXIL_CLK_FREQ_G  => AXIL_CLK_FREQ_C,
         XADC_AUX_CHANS_G => XADC_AUX_CHANS_G)
      port map (
         axilClk         => locAxilClk,                          -- [in]
         axilRst         => locAxilRst,                          -- [in]
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



end rtl;
