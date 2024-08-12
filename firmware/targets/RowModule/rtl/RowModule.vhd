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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

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
use warm_tdm.WarmTdmPkg.all;

entity RowModule is

   generic (
      TPD_G                   : time                  := 1 ns;
      SIMULATION_G            : boolean               := false;
      SIMULATE_PGP_G          : boolean               := true;
      SIM_PGP_PORT_NUM_G      : integer               := 0;
      SIM_ETH_SRP_PORT_NUM_G  : integer               := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer               := 9000;
      BUILD_INFO_G            : BuildInfoType;
      RING_ADDR_0_G           : boolean               := false;
      NUM_ROW_SELECTS_G       : integer range 1 to 32 := 32;
      NUM_CHIP_SELECTS_G      : integer range 0 to 8  := 0;
      ETH_10G_G               : boolean               := false;
      DHCP_G                  : boolean               := false;
      IP_ADDR_G               : slv(31 downto 0)      := x"0C03A8C0";  -- 192.168.3.12 
      MAC_ADDR_G              : slv(47 downto 0)      := x"0C_00_16_56_00_08");
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
      xbarDataSel   : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarClkSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarMgtSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarTimingSel : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");

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

      -- XADC
      vAuxP : in slv(3 downto 0);
      vAuxN : in slv(3 downto 0);

      -- DAC Interfaces
      dacDb    : out slv(13 downto 0);
      dacWrt   : out slv(15 downto 0);
      dacClk   : out slv(15 downto 0);
      dacSel   : out slv(15 downto 0);
      dacReset : out slv(15 downto 0));

end entity RowModule;

architecture rtl of RowModule is

   constant AXI_CLK_FREQ_C : real := 125.0E6;

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(8);  -- Maybe packetizer config?

   constant NUM_AXIL_MASTERS_C : integer := 3;
   constant AXIL_PRBS_RX_C     : integer := 0;
   constant AXIL_PRBS_TX_C     : integer := 1;
   constant AXIL_DACS_C        : integer := 2;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_PRBS_RX_C  => (
         baseAddr     => APP_BASE_ADDR_C + X"00200000",
         addrBits     => 12,
         connectivity => X"FFFF"),
      AXIL_PRBS_TX_C  => (
         baseAddr     => APP_BASE_ADDR_C + X"00201000",
         addrBits     => 8,
         connectivity => X"FFFF"),
      AXIL_DACS_C     => (
         baseAddr     => APP_BASE_ADDR_C + X"01000000",
         addrBits     => 16,
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
   signal axisClk          : sl;
   signal axisRst          : sl;
   signal dataTxAxisMaster : AxiStreamMasterType;
   signal dataTxAxisSlave  : AxiStreamSlaveType;
   signal dataRxAxisMaster : AxiStreamMasterType;
   signal dataRxAxisSlave  : AxiStreamSlaveType;

   -- Debug clocks
   signal fabRefClk0 : sl;
   signal fabRefClk1 : sl;
   signal gtRefClk0  : sl;
   signal gtRefClk1  : sl;

   signal rssiStatus  : slv7Array(1 downto 0);
   signal ethPhyReady : sl;


begin
   -------------------------------------------------------------------------------------------------
   -- Shared logic
   -- PGP, Ethernet, Timing, AxiVersion, Etc
   -------------------------------------------------------------------------------------------------
   U_WarmTdmCore_1 : entity warm_tdm.WarmTdmCore
      generic map (
         TPD_G                   => TPD_G,
         SIMULATION_G            => SIMULATION_G,
         SIMULATE_PGP_G          => SIMULATE_PGP_G,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         BUILD_INFO_G            => BUILD_INFO_G,
         RING_ADDR_0_G           => RING_ADDR_0_G,
         ETH_10G_G               => ETH_10G_G,
         DHCP_G                  => DHCP_G,
         IP_ADDR_G               => IP_ADDR_G,
         MAC_ADDR_G              => MAC_ADDR_G,
         XADC_AUX_CHANS_G        => (12, 4, 11, 3))
      port map (
         gtRefClk0P       => gtRefClk0P,          -- [in]
         gtRefClk0N       => gtRefClk0N,          -- [in]
         gtRefClk1P       => gtRefClk1P,          -- [in]
         gtRefClk1N       => gtRefClk1N,          -- [in]
         pgpTxP           => pgpTxP,              -- [out]
         pgpTxN           => pgpTxN,              -- [out]
         pgpRxP           => pgpRxP,              -- [in]
         pgpRxN           => pgpRxN,              -- [in]
         xbarDataSel      => xbarDataSel,         -- [out]
         xbarClkSel       => xbarClkSel,          -- [out]
         xbarMgtSel       => xbarMgtSel,          -- [out]
         timingRxClkP     => timingRxClkP,        -- [in]
         timingRxClkN     => timingRxClkN,        -- [in]
         timingRxDataP    => timingRxDataP,       -- [in]
         timingRxDataN    => timingRxDataN,       -- [in]
         timingTxClkP     => timingTxClkP,        -- [out]
         timingTxClkN     => timingTxClkN,        -- [out]
         timingTxDataP    => timingTxDataP,       -- [out]
         timingTxDataN    => timingTxDataN,       -- [out]
         sfp0TxP          => sfp0TxP,             -- [out]
         sfp0TxN          => sfp0TxN,             -- [out]
         sfp0RxP          => sfp0RxP,             -- [in]
         sfp0RxN          => sfp0RxN,             -- [in]
         bootCsL          => bootCsL,             -- [out]
         bootMosi         => bootMosi,            -- [out]
         bootMiso         => bootMiso,            -- [in]
         promScl          => promScl,             -- [inout]
         promSda          => promSda,             -- [inout]
         pwrScl           => pwrScl,              -- [inout]
         pwrSda           => pwrSda,              -- [inout]
         leds             => leds,                -- [out]
         conRxGreenLed    => conRxGreenLed,       -- [out]
         conRxYellowLed   => conRxYellowLed,      -- [out]
         conTxGreenLed    => conTxGreenLed,       -- [out]
         conTxYellowLed   => conTxYellowLed,      -- [out]
         vAuxP            => vAuxP,               -- [in]
         vAuxN            => vAuxN,               -- [in]
         axilClk          => axilClk,             -- [out]
         axilRst          => axilRst,             -- [out]
         axilWriteMaster  => srpAxilWriteMaster,  -- [out]
         axilWriteSlave   => srpAxilWriteSlave,   -- [in]
         axilReadMaster   => srpAxilReadMaster,   -- [out]
         axilReadSlave    => srpAxilReadSlave,    -- [in]
         timingRxClk125   => timingRxClk125,      -- [out]
         axisClk          => axisClk,             -- [out]
         axisRst          => axisRst,             -- [out]
         dataTxAxisMaster => dataTxAxisMaster,    -- [in]
         dataTxAxisSlave  => dataTxAxisSlave,     -- [out]
         dataRxAxisMaster => dataRxAxisMaster,    -- [out]
         dataRxAxisSlave  => dataRxAxisSlave,     -- [in]         
         timingRxRst125   => timingRxRst125,      -- [out]
         timingRxData     => timingRxData);       -- [out]

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
   -- DACS
   -------------------------------------------------------------------------------------------------
   U_RowDacDriver_1 : entity warm_tdm.RowDacDriver
      generic map (
         TPD_G              => TPD_G,
         NUM_ROW_SELECTS_G  => NUM_ROW_SELECTS_G,
         NUM_CHIP_SELECTS_G => NUM_CHIP_SELECTS_G,
         AXIL_BASE_ADDR_G   => AXIL_XBAR_CFG_C(AXIL_DACS_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125,                    -- [in]
         timingRxRst125  => timingRxRst125,                    -- [in]
         timingRxData    => timingRxData,                      -- [in]
         dacDb           => dacDb,                             -- [out]
         dacWrt          => dacWrt,                            -- [out]
         dacClk          => dacClk,                            -- [out]
         dacSel          => dacSel,                            -- [out]
         dacReset        => dacReset,                          -- [out]
         axilClk         => axilClk,                           -- [in]
         axilRst         => axilRst,                           -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_DACS_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_DACS_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_DACS_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_DACS_C));   -- [out]



   -------------------------------------------------------------------------------------------------
   -- PRBS modules for connection debugging (maybe unnecessary)
   -------------------------------------------------------------------------------------------------
   U_SsiPrbsRx_1 : entity surf.SsiPrbsRx
      generic map (
         TPD_G                     => TPD_G,
         STATUS_CNT_WIDTH_G        => 32,
         SLAVE_READY_EN_G          => true,
         GEN_SYNC_FIFO_G           => false,  -- really axil and axis clock are the same
         SYNTH_MODE_G              => "inferred",
--          MEMORY_TYPE_G             => MEMORY_TYPE_G,
         SLAVE_AXI_STREAM_CONFIG_G => AXIS_CONFIG_C,
         SLAVE_AXI_PIPE_STAGES_G   => 1)
      port map (
         sAxisClk       => axisClk,     -- [in]
         sAxisRst       => axisRst,     -- [in]
         sAxisMaster    => dataRxAxisMaster,  -- [in]
         sAxisSlave     => dataRxAxisSlave,   -- [out]
         axiClk         => axilClk,     -- [in]
         axiRst         => axilRst,     -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_PRBS_RX_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_PRBS_RX_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_PRBS_RX_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_PRBS_RX_C));  -- [out]

   U_SsiPrbsTx_1 : entity surf.SsiPrbsTx
      generic map (
         TPD_G                      => TPD_G,
--          MEMORY_TYPE_G              => MEMORY_TYPE_G,
         GEN_SYNC_FIFO_G            => false,
         SYNTH_MODE_G               => "inferred",
         MASTER_AXI_STREAM_CONFIG_G => AXIS_CONFIG_C,
         MASTER_AXI_PIPE_STAGES_G   => 1)
      port map (
         mAxisClk        => axisClk,                              -- [in]
         mAxisRst        => axisRst,                              -- [in]
         mAxisMaster     => dataTxAxisMaster,                     -- [out]
         mAxisSlave      => dataTxAxisSlave,                      -- [in]
         locClk          => axilClk,                              -- [in]
         locRst          => axilRst,                              -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_PRBS_TX_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_PRBS_TX_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_PRBS_TX_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_PRBS_TX_C));  -- [out]




end architecture rtl;
