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
      TPD_G              : time             := 1 ns;
      SIMULATION_G       : boolean          := false;
      SIM_PGP_PORT_NUM_G : positive         := 7000;
      SIM_ETH_PORT_NUM_G : positive         := 8000;
      BUILD_INFO_G       : BuildInfoType;
      RING_ADDR_0_G      : boolean          := false;
      ETH_10G_G          : boolean          := true;
      DHCP_G             : boolean          := false;         -- true = DHCP, false = static address
      IP_ADDR_G          : slv(31 downto 0) := x"0B01A8C0");  -- 192.168.1.10 (before DHCP)
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
      xbarDataSel : out slv(1 downto 0) := "00";
      xbarClkSel  : out slv(1 downto 0) := "00";
      xbarMgtSel  : out slv(1 downto 0) := "00";

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
      leds : out slv(7 downto 0);

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

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(8);  -- Maybe packetizer config?

   constant NUM_AXIL_MASTERS_C : integer := 6;
   constant AXIL_COMMON_C      : integer := 0;
   constant AXIL_TIMING_RX_C   : integer := 1;
   constant AXIL_PRBS_RX_C     : integer := 2;
   constant AXIL_PRBS_TX_C     : integer := 3;
   constant AXIL_DACS_C        : integer := 4;
   constant AXIL_COM_C         : integer := 5;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_COMMON_C    => (
         baseAddr      => X"00000000",
         addrBits      => 20,
         connectivity  => X"FFFF"),
      AXIL_TIMING_RX_C => (
         baseAddr      => X"00100000",
         addrBits      => 16,
         connectivity  => X"FFFF"),
      AXIL_PRBS_RX_C   => (
         baseAddr      => X"00100000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_PRBS_TX_C   => (
         baseAddr      => X"00101000",
         addrBits      => 8,
         connectivity  => X"FFFF"),
      AXIL_DACS_C      => (
         baseAddr      => X"01000000",
         addrBits      => 24,
         connectivity  => X"FFFF"),
      AXIL_COM_C       => (
         baseAddr      => X"A0000000",
         addrBits      => 24,
         connectivity  => X"FFFF"));

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
   signal timingClk125 : sl;
   signal timingRst125 : sl;
   signal timingData   : LocalTimingType;

   -- DAC SPI AXIL
   constant DAC_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(11 downto 0) := genAxiLiteConfig(12, AXIL_XBAR_CFG_C(AXIL_DACS_C).baseAddr, 24, 20);

   signal dacAxilWriteMasters : AxiLiteWriteMasterArray(11 downto 0);
   signal dacAxilWriteSlaves  : AxiLiteWriteSlaveArray(11 downto 0);
   signal dacAxilReadMasters  : AxiLiteReadMasterArray(11 downto 0);
   signal dacAxilReadSlaves   : AxiLiteReadSlaveArray(11 downto 0);

   -- Debug streams
   signal dataTxAxisMaster : AxiStreamMasterType;
   signal dataTxAxisSlave  : AxiStreamSlaveType;
   signal dataRxAxisMaster : AxiStreamMasterType;
   signal dataRxAxisSlave  : AxiStreamSlaveType;


begin

   -------------------------------------------------------------------------------------------------
   -- Timing Interface
   -------------------------------------------------------------------------------------------------
   U_TimingRx_1 : entity warm_tdm.TimingRx
      generic map (
         TPD_G             => TPD_G,
         SIMULATION_G      => SIMULATION_G,
         IODELAY_GROUP_G   => "IODELAY0",
         IDELAYCTRL_FREQ_G => 200.0)
      port map (
         timingRefClkP   => gtRefClk1P,                             -- [in]
         timingRefClkN   => gtRefClk1N,                             -- [in]
         timingRxClkP    => timingRxClkP,                           -- [in]
         timingRxClkN    => timingRxClkN,                           -- [in]
         timingRxDataP   => timingRxDataP,                          -- [in]
         timingRxDataN   => timingRxDataN,                          -- [in]
         timingClkOut    => timingClk125,                           -- [out]
         timingRstOut    => timingRst125,                           -- [out]
         timingData      => timingData,                             -- [out]
         axilClk         => axilClk,                                -- [in]
         axilRst         => axilRst,                                -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_TIMING_RX_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_TIMING_RX_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_TIMING_RX_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_TIMING_RX_C));

--    U_TimingRx_1 : entity warm_tdm.TimingRx
--       generic map (
--          TPD_G => TPD_G)
--       port map (
--          timingRefClkP => gtRefClk1P,     -- [in]
--          timingRefClkN => gtRefClk1N,     -- [in]
--          timingRxClkP  => timingRxClkP,   -- [in]
--          timingRxClkN  => timingRxClkN,   -- [in]
--          timingRxTrigP => timingRxTrigP,  -- [in]
--          timingRxTrigN => timingRxTrigN,  -- [in]
--          dacTriggerB   => dacTriggerB,    -- [out]
--          dacClkP       => dacClkP,        -- [out]
--          dacClkN       => dacClkN);       -- [out]

   -------------------------------------------------------------------------------------------------
   -- Communications Interfaces
   -------------------------------------------------------------------------------------------------
   U_ComCore_1 : entity warm_tdm.ComCore
      generic map (
         TPD_G              => TPD_G,
         SIMULATION_G       => SIMULATION_G,
         SIM_PGP_PORT_NUM_G => SIM_PGP_PORT_NUM_G,
         SIM_ETH_PORT_NUM_G => SIM_ETH_PORT_NUM_G,
         RING_ADDR_0_G      => RING_ADDR_0_G,
         AXIL_BASE_ADDR_G   => DAC_XBAR_CFG_C(AXIL_COM_C).baseAddr,
         ETH_10G_G          => ETH_10G_G,
         DHCP_G             => DHCP_G,
         IP_ADDR_G          => IP_ADDR_G)
      port map (
         gtRefClkP        => gtRefClk0P,                       -- [in]
         gtRefClkN        => gtRefClk0N,                       -- [in]
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
   -- DAC Config Crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_DACs : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 12,
         MASTERS_CONFIG_G   => DAC_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,                           -- [in]
         axiClkRst           => axilRst,                           -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(AXIL_DACS_C),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(AXIL_DACS_C),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(AXIL_DACS_C),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(AXIL_DACS_C),    -- [out]
         mAxiWriteMasters    => dacAxilWriteMasters,               -- [out]
         mAxiWriteSlaves     => dacAxilWriteSlaves,                -- [in]
         mAxiReadMasters     => dacAxilReadMasters,                -- [out]
         mAxiReadSlaves      => dacAxilReadSlaves);                -- [in]

   -- DAC Config interfaces
   DAC_SPI_GEN : for i in 11 downto 0 generate
      U_AxiSpiMaster_1 : entity surf.AxiSpiMaster
         generic map (
            TPD_G             => TPD_G,
            ADDRESS_SIZE_G    => 16,
            DATA_SIZE_G       => 16,
            MODE_G            => "RW",
            SHADOW_EN_G       => false,
            CPHA_G            => '1',
            CPOL_G            => '1',
            CLK_PERIOD_G      => 156.25E+6,
            SPI_SCLK_PERIOD_G => 100.0E-6,
            SPI_NUM_CHIPS_G   => 1)
         port map (
            axiClk         => axilClk,                 -- [in]
            axiRst         => axilRst,                 -- [in]
            axiReadMaster  => dacAxilReadMasters(i),   -- [in]
            axiReadSlave   => dacAxilReadSlaves(i),    -- [out]
            axiWriteMaster => dacAxilWriteMasters(i),  -- [in]
            axiWriteSlave  => dacAxilWriteSlaves(i),   -- [out]
            coreSclk       => dacSclk(i),              -- [out]
            coreSDin       => dacSdo(i),               -- [in]
            coreSDout      => dacSdio(i),              -- [out]
            coreMCsb(0)    => dacCsB(i));              -- [out]

      U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
         generic map (
            TPD_G => TPD_G)
         port map (
            clkIn   => timingData.rowStrobe,  -- [in]
            clkOutP => dacClkP(i),            -- [out]
            clkOutN => dacClkN(i));           -- [out]
   end generate DAC_SPI_GEN;



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
