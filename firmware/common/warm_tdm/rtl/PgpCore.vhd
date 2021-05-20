-------------------------------------------------------------------------------
-- Title      : PGP Ring Interface for Warm TDM
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


library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
use surf.AxiLitePkg.all;
use surf.Gtx7CfgPkg.all;
use surf.Pgp2bPkg.all;

library warm_tdm;

entity PgpCore is

   generic (
      TPD_G            : time             := 1 ns;
      SIMULATION_G     : boolean          := false;
      SIM_PORT_NUM_G   : integer          := 7000;
      RING_ADDR_0_G    : boolean          := false;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := X"00000000");

   port (
      -- GT Ports and clock
      extRst    : in  sl;
      gtRefClk  : in  sl;
      gtRefClkG : in  sl;
      pgpTxP    : out sl;
      pgpTxN    : out sl;
      pgpRxP    : in  sl;
      pgpRxN    : in  sl;

      -- Main clock and reset 
      axiClk           : out sl;
      axiRst           : out sl;
      -- SRP 
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      -- Local register readout
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      -- Ethernet traffic bridged onto PGP
      ethRxAxisMasters : in  AxiStreamMasterArray(3 downto 0);
      ethRxAxisSlaves  : out AxiStreamSlaveArray(3 downto 0);
      ethTxAxisMasters : out AxiStreamMasterArray(3 downto 0);
      ethTxAxisSlaves  : in  AxiStreamSlaveArray(3 downto 0);
      -- Local Data
      dataTxAxisMaster : in  AxiStreamMasterType;
      dataTxAxisSlave  : out AxiStreamSlaveType;
      dataRxAxisMaster : out AxiStreamMasterType;
      dataRxAxisSlave  : in  AxiStreamSlaveType);

end entity PgpCore;

architecture rtl of PgpCore is

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 8, tDestBits => 8);

   signal address : slv(2 downto 0) := "111";

   constant GTX_CFG_C : Gtx7CPllCfgType := getGtx7CPllCfg(312.5E6, 3.125E9);

   signal pgpClk       : sl;
   signal pgpRst       : sl;
   signal pgpTxIn      : Pgp2bTxInType;
   signal pgpTxOut     : Pgp2bTxOutType;
   signal pgpRxIn      : Pgp2bRxInType;
   signal pgpRxOut     : Pgp2bRxOutType;
   signal locPgpTxIn   : Pgp2bTxInType                    := PGP2B_TX_IN_INIT_C;
   signal pgpTxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpTxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal pgpRxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpRxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal pgpRxCtrl    : AxiStreamCtrlArray(3 downto 0)   := (others => AXI_STREAM_CTRL_UNUSED_C);
   signal toggle       : sl;
   signal locData      : slv(7 downto 0);

   signal fifoRxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal fifoRxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal fifoTxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal fifoTxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal appRxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appRxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal appTxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appTxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal appLocalRxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appLocalRxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal appLocalTxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appLocalTxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   constant VC_SRP_C        : integer := 0;
   constant VC_DATA_C       : integer := 1;
   constant VC_LOOPBACK_2_C : integer := 2;
   constant VC_LOOPBACK_3_C : integer := 3;

   constant NUM_AXIL_MASTERS_C : integer := 2;
   constant AXIL_PGP_C         : integer := 0;
   constant AXIL_GTX_C         : integer := 1;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_PGP_C      => (
         baseAddr     => AXIL_BASE_ADDR_G + X"00000000",
         addrBits     => 8,
         connectivity => X"FFFF"),
      AXIL_GTX_C      => (
         baseAddr     => AXIL_BASE_ADDR_G + X"00001000",
         addrBits     => 12,
         connectivity => X"FFFF"));

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);


begin

   REAL_PGP_GEN : if (true) generate
      U_Pgp2bGtx7VarLatWrapper_1 : entity surf.Pgp2bGtx7VarLatWrapper
         generic map (
            TPD_G                 => TPD_G,
            SIM_GTRESET_SPEEDUP_G => "TRUE",
            SIM_VERSION_G         => "4.0",
            USE_REFCLK_G          => true,
            CLKIN_PERIOD_G        => 6.4,
            DIVCLK_DIVIDE_G       => 1,
            CLKFBOUT_MULT_F_G     => 6.375,
            CLKOUT0_DIVIDE_F_G    => 6.375,
--         CPLL_REFCLK_SEL_G  => CPLL_REFCLK_SEL_G,
            CPLL_FBDIV_G          => GTX_CFG_C.CPLL_FBDIV_G,
            CPLL_FBDIV_45_G       => GTX_CFG_C.CPLL_FBDIV_45_G,
            CPLL_REFCLK_DIV_G     => GTX_CFG_C.CPLL_REFCLK_DIV_G,
            RXOUT_DIV_G           => GTX_CFG_C.OUT_DIV_G,
            TXOUT_DIV_G           => GTX_CFG_C.OUT_DIV_G,
            RX_CLK25_DIV_G        => GTX_CFG_C.CLK25_DIV_G,
            TX_CLK25_DIV_G        => GTX_CFG_C.CLK25_DIV_G,
--          RX_OS_CFG_G        => RX_OS_CFG_G,
--          RXCDR_CFG_G        => RXCDR_CFG_G,
--          RXDFEXYDEN_G       => RXDFEXYDEN_G,
--          RX_DFE_KL_CFG2_G   => RX_DFE_KL_CFG2_G,
            VC_INTERLEAVE_G       => 1,
--         PAYLOAD_CNT_TOP_G  => PAYLOAD_CNT_TOP_G,
            NUM_VC_EN_G           => 4,
--          TX_POLARITY_G      => TX_POLARITY_G,
--          RX_POLARITY_G      => RX_POLARITY_G,
            TX_ENABLE_G           => true,
            RX_ENABLE_G           => true)
         port map (
            extRst          => extRst,                           -- [in]
            pgpClk          => pgpClk,                           -- [out]
            pgpRst          => pgpRst,                           -- [out]
            stableClk       => open,                             -- [out]
            pgpTxIn         => pgpTxIn,                          -- [in]
            pgpTxOut        => pgpTxOut,                         -- [out]
            pgpRxIn         => pgpRxIn,                          -- [in]
            pgpRxOut        => pgpRxOut,                         -- [out]
            pgpTxMasters    => pgpTxMasters,                     -- [in]
            pgpTxSlaves     => pgpTxSlaves,                      -- [out]
            pgpRxMasters    => pgpRxMasters,                     -- [out]
            pgpRxCtrl       => pgpRxCtrl,                        -- [in]
--             gtClkP          => pgpRefClkP,                       -- [in]
--             gtClkN          => pgpRefClkN,                       -- [in]
            gtRefClk        => gtRefClk,                         -- [in]
            gtRefClkBufg    => gtRefClkG,                        -- [in]
            gtTxP           => pgpTxP,                           -- [out]
            gtTxN           => pgpTxN,                           -- [out]
            gtRxP           => pgpRxP,                           -- [in]
            gtRxN           => pgpRxN,                           -- [in]
--          txPreCursor     => txPreCursor,      -- [in]
--          txPostCursor    => txPostCursor,     -- [in]
--          txDiffCtrl      => txDiffCtrl,       -- [in]
            axilClk         => pgpClk,                           -- [in]
            axilRst         => pgpRst,                           -- [in]
            axilReadMaster  => locAxilReadMasters(AXIL_GTX_C),   -- [in]
            axilReadSlave   => locAxilReadSlaves(AXIL_GTX_C),    -- [out]
            axilWriteMaster => locAxilWriteMasters(AXIL_GTX_C),  -- [in]
            axilWriteSlave  => locAxilWriteSlaves(AXIL_GTX_C));  -- [out]
   end generate REAL_PGP_GEN;

   SIM_GEN : if (false) generate
      ClockManager7_Inst : entity surf.ClockManager7
         generic map(
            TPD_G              => TPD_G,
            TYPE_G             => "MMCM",
            INPUT_BUFG_G       => false,
            FB_BUFG_G          => true,
            RST_IN_POLARITY_G  => '1',
            NUM_CLOCKS_G       => 1,
            -- MMCM attributes
            BANDWIDTH_G        => "OPTIMIZED",
            CLKIN_PERIOD_G     => 6.4,
            DIVCLK_DIVIDE_G    => 1,
            CLKFBOUT_MULT_F_G  => 6.375,
            CLKOUT0_DIVIDE_F_G => 6.375)
         port map(
            clkIn     => gtRefClkG,
            rstIn     => '0',
            clkOut(0) => pgpClk,
            rstOut(0) => pgpRst);

      U_ClockDivider_1 : entity surf.ClockDivider
         generic map (
            TPD_G         => TPD_G,
            COUNT_WIDTH_G => 8)
         port map (
            clk        => pgpClk,           -- [in]
            rst        => pgpRst,           -- [in]
            highCount  => (others => '1'),  -- [in]
            lowCount   => (others => '1'),  -- [in]
            delayCount => (others => '0'),  -- [in]
            divClk     => toggle,           -- [out]
            preRise    => open,             -- [out]
            preFall    => open);            -- [out]

      U_RoguePgp2bSim_1 : entity surf.RoguePgp2bSim
         generic map (
            TPD_G         => TPD_G,
            PORT_NUM_G    => SIM_PORT_NUM_G,
            NUM_VC_G      => 4,
            EN_SIDEBAND_G => true)
         port map (
            pgpClk       => pgpClk,        -- [in]
            pgpClkRst    => pgpRst,        -- [in]
            pgpRxIn      => pgpRxIn,       -- [in]
            pgpRxOut     => pgpRxOut,      -- [out]
            pgpTxIn      => pgpTxIn,       -- [in]
            pgpTxOut     => pgpTxOut,      -- [out]
            pgpTxMasters => pgpTxMasters,  -- [in]
            pgpTxSlaves  => pgpTxSlaves,   -- [out]
            pgpRxMasters => pgpRxMasters,  -- [out]
            pgpRxSlaves  => pgpRxSlaves);  -- [in]

   end generate SIM_GEN;

   U_Pgp2bAxi_1 : entity surf.Pgp2bAxi
      generic map (
         TPD_G             => TPD_G,
         COMMON_TX_CLK_G   => true,
         COMMON_RX_CLK_G   => true,
         WRITE_EN_G        => true,
         AXI_CLK_FREQ_G    => 156.26E6,
         ERROR_CNT_WIDTH_G => 16)
      port map (
         pgpTxClk        => pgpClk,                           -- [in]
         pgpTxClkRst     => pgpRst,                           -- [in]
         pgpTxIn         => pgpTxIn,                          -- [out]
         pgpTxOut        => pgpTxOut,                         -- [in]
         locTxIn         => locPgpTxIn,                       -- [in]
         pgpRxClk        => pgpClk,                           -- [in]
         pgpRxClkRst     => pgpRst,                           -- [in]
         pgpRxIn         => pgpRxIn,                          -- [out]
         pgpRxOut        => pgpRxOut,                         -- [in]
--         locRxIn         => locRxIn,          -- [in]
--          statusWord      => statusWord,       -- [out]
--          statusSend      => statusSend,       -- [out]
         axilClk         => pgpClk,                           -- [in]
         axilRst         => pgpRst,                           -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_PGP_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_PGP_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_PGP_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_PGP_C));  -- [out]


   RING_ROUTER_GEN : for i in 3 downto 0 generate
      -- buffers
      U_PgpRXVcFifo_1 : entity surf.PgpRXVcFifo
         generic map (
            TPD_G               => TPD_G,
            ROGUE_SIM_EN_G      => SIMULATION_G,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 0,
            VALID_THOLD_G       => 500,
            VALID_BURST_MODE_G  => true,
            SYNTH_MODE_G        => "inferred",
            MEMORY_TYPE_G       => "block",
            GEN_SYNC_FIFO_G     => true,
            FIFO_ADDR_WIDTH_G   => 10,
            FIFO_PAUSE_THRESH_G => 256,
            PHY_AXI_CONFIG_G    => SSI_PGP2B_CONFIG_C,
            APP_AXI_CONFIG_G    => AXIS_CONFIG_C)
         port map (
            pgpClk      => pgpClk,              -- [in]
            pgpRst      => pgpRst,              -- [in]
            rxlinkReady => pgpRxOut.linkReady,  -- [in]
            pgpRxMaster => pgpRxMasters(i),     -- [in]
            pgpRxCtrl   => pgpRxCtrl(i),        -- [out]
            pgpRxSlave  => pgpRxSlaves(i),      -- [out]
            axisClk     => pgpClk,              -- [in]
            axisRst     => pgpRst,              -- [in]
            axisMaster  => fifoRxMasters(i),    -- [out]
            axisSlave   => fifoRxSlaves(i));    -- [in]

      address <= ite(RING_ADDR_0_G, "000", pgpRxOut.remLinkData(2 downto 0) + 1);

      locPgpTxIn.locData <= "00000" & address;
--       U_SlvDelay_1 : entity surf.SlvDelay
--          generic map (
--             TPD_G        => TPD_G,
--             SRL_EN_G     => false,
--             DELAY_G      => 10,
--             REG_OUTPUT_G => true,
--             WIDTH_G      => 8)
--          port map (
--             clk  => pgpClk,               -- [in]
--             rst  => pgpRst,               -- [in]
--             din  => locData,              -- [in]
--             dout => locPgpTxIn.locData);  -- [out]

      U_RingRouter_1 : entity warm_tdm.RingRouter
         generic map (
            TPD_G => TPD_G)
         port map (
            axisClk          => pgpClk,               -- [in]
            axisRst          => pgpRst,               -- [in]
            address          => address,              -- [in]
            linkRxGood       => pgpRxOut.linkReady,   -- [in]
            linkTxGood       => pgpTxOut.linkReady,   -- [in]
            linkRxAxisMaster => fifoRxMasters(i),     -- [in]
            linkRxAxisSlave  => fifoRxSlaves(i),      -- [out]
            linkTxAxisMaster => fifoTxMasters(i),     -- [out]
            linkTxAxisSlave  => fifoTxSlaves(i),      -- [in]
            appRxAxisMaster  => appRxAxisMasters(i),  -- [out]
            appRxAxisSlave   => appRxAxisSlaves(i),   -- [in]
            appTxAxisMaster  => appTxAxisMasters(i),  -- [in]
            appTxAxisSlave   => appTxAxisSlaves(i));  -- [out]

      U_PgpTXVcFifo_1 : entity surf.PgpTXVcFifo
         generic map (
            TPD_G              => TPD_G,
            INT_PIPE_STAGES_G  => 1,
            PIPE_STAGES_G      => 0,
            VALID_THOLD_G      => 500,
            VALID_BURST_MODE_G => true,
            SYNTH_MODE_G       => "inferred",
            MEMORY_TYPE_G      => "block",
            GEN_SYNC_FIFO_G    => true,
            FIFO_ADDR_WIDTH_G  => 10,
            APP_AXI_CONFIG_G   => AXIS_CONFIG_C,
            PHY_AXI_CONFIG_G   => SSI_PGP2B_CONFIG_C)
         port map (
            axisClk     => pgpClk,              -- [in]
            axisRst     => pgpRst,              -- [in]
            axisMaster  => fifoTxMasters(i),    -- [in]
            axisSlave   => fifoTxSlaves(i),     -- [out]
            pgpClk      => pgpClk,              -- [in]
            pgpRst      => pgpRst,              -- [in]
            rxlinkReady => pgpRxOut.linkReady,  -- [in]
            txlinkReady => pgpTxOut.linkReady,  -- [in]
            pgpTxMaster => pgpTxMasters(i),     -- [out]
            pgpTxSlave  => pgpTxSlaves(i));     -- [in]

   end generate RING_ROUTER_GEN;


   -------------------------------------------------------------------------------------------------
   -- Mux Ethernet streams in to local PGP streams
   -------------------------------------------------------------------------------------------------
   ETH_STREAM_MUX : for i in 3 downto 0 generate
      U_AxiStreamDeMux_1 : entity surf.AxiStreamDeMux
         generic map (
            TPD_G          => TPD_G,
            NUM_MASTERS_G  => 2,
            MODE_G         => "ROUTED",
            TDEST_ROUTES_G => (
               0           => "0-------",
               1           => "1-------"),
            PIPE_STAGES_G  => 0)
         port map (
            axisClk         => pgpClk,                    -- [in]
            axisRst         => pgpRst,                    -- [in]
            sAxisMaster     => appRxAxisMasters(i),       -- [in]
            sAxisSlave      => appRxAxisSlaves(i),        -- [out]
            mAxisMasters(0) => appLocalRxAxisMasters(i),  -- [out]
            mAxisMasters(1) => ethTxAxisMasters(i),       -- [out]            
            mAxisSlaves(0)  => appLocalRxAxisSlaves(i),   -- [in]
            mAxisSlaves(1)  => ethTxAxisSlaves(i));       -- [in]      

      U_AxiStreamMux_1 : entity surf.AxiStreamMux
         generic map (
            TPD_G                => TPD_G,
            PIPE_STAGES_G        => 0,
            NUM_SLAVES_G         => 2,
            MODE_G               => "ROUTED",
            TDEST_ROUTES_G       => (
               0                 => "0-------",
               1                 => "1-------"),
            ILEAVE_EN_G          => true,                 -- 
            ILEAVE_ON_NOTVALID_G => true,
            ILEAVE_REARB_G       => 31,                   -- Check this
            REARB_DELAY_G        => true,
            FORCED_REARB_HOLD_G  => false)
         port map (
            axisClk         => pgpClk,                    -- [in]
            axisRst         => pgpRst,                    -- [in]
            sAxisMasters(0) => appLocalTxAxisMasters(i),  -- [in]
            sAxisMasters(1) => ethRxAxisMasters(i),       -- [in]            
            sAxisSlaves(0)  => appLocalTxAxisSlaves(i),   -- [out]
            sAxisSlaves(1)  => ethRxAxisSlaves(i),        -- [out]            
            mAxisMaster     => appTxAxisMasters(i),       -- [out]
            mAxisSlave      => appTxAxisSlaves(i));       -- [in]
   end generate ETH_STREAM_MUX;

   ------------------------------------
   -- VC0 - SRP
   ------------------------------------
   axiClk <= pgpClk;
   axiRst <= pgpRst;
   U_SrpV3AxiLite_1 : entity surf.SrpV3AxiLite
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
--          FIFO_PAUSE_THRESH_G   => FIFO_PAUSE_THRESH_G,
--          FIFO_SYNTH_MODE_G     => FIFO_SYNTH_MODE_G,
--          TX_VALID_THOLD_G      => TX_VALID_THOLD_G,
--          TX_VALID_BURST_MODE_G => TX_VALID_BURST_MODE_G,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => true,
         AXIL_CLK_FREQ_G     => 156.25E6,
         AXI_STREAM_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk         => pgpClk,                           -- [in]
         sAxisRst         => pgpRst,                           -- [in]
         sAxisMaster      => appLocalRxAxisMasters(VC_SRP_C),  -- [in]
         sAxisSlave       => appLocalRxAxisSlaves(VC_SRP_C),   -- [out]
         sAxisCtrl        => open,                             -- [out]
         mAxisClk         => pgpClk,                           -- [in]
         mAxisRst         => pgpRst,                           -- [in]
         mAxisMaster      => appLocalTxAxisMasters(VC_SRP_C),  -- [out]
         mAxisSlave       => appLocalTxAxisSlaves(VC_SRP_C),   -- [in]
         axilClk          => pgpClk,                           -- [in]
         axilRst          => pgpRst,                           -- [in]
         mAxilWriteMaster => mAxilWriteMaster,                 -- [out]
         mAxilWriteSlave  => mAxilWriteSlave,                  -- [in]
         mAxilReadMaster  => mAxilReadMaster,                  -- [out]
         mAxilReadSlave   => mAxilReadSlave);                  -- [in]


   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => pgpClk,               -- [in]
         axiClkRst           => pgpRst,               -- [in]
         sAxiWriteMasters(0) => sAxilWriteMaster,     -- [in]
         sAxiWriteSlaves(0)  => sAxilWriteSlave,      -- [out]
         sAxiReadMasters(0)  => sAxilReadMaster,      -- [in]
         sAxiReadSlaves(0)   => sAxilReadSlave,       -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]

   ----------------------------------------
   -- VC 1 is the data channel 
   ----------------------------------------
   appLocalTxAxisMasters(VC_DATA_C) <= dataTxAxisMaster;
   dataTxAxisSlave                  <= appLocalTxAxisSlaves(VC_DATA_C);
   appLocalRxAxisSlaves(VC_DATA_C)  <= dataRxAxisSlave;
   dataRxAxisMaster                 <= appLocalRxAxisMasters(VC_DATA_C);

   ---------------------------------
   -- VC 2 and 3 are Loopback
   ---------------------------------
   U_AxiStreamFifoV2_LOOPBACK_2 : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 9,
         FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk    => pgpClk,                                  -- [in]
         sAxisRst    => pgpRst,                                  -- [in]
         sAxisMaster => appLocalRxAxisMasters(VC_LOOPBACK_2_C),  -- [in]
         sAxisSlave  => appLocalRxAxisSlaves(VC_LOOPBACK_2_C),   -- [out]
         mAxisClk    => pgpClk,                                  -- [in]
         mAxisRst    => pgpRst,                                  -- [in]
         mAxisMaster => appLocalTxAxisMasters(VC_LOOPBACK_2_C),  -- [out]
         mAxisSlave  => appLocalTxAxisSlaves(VC_LOOPBACK_2_C));  -- [in]

   U_AxiStreamFifoV2_LOOPBACK_3 : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 9,
         FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk    => pgpClk,                                  -- [in]
         sAxisRst    => pgpRst,                                  -- [in]
         sAxisMaster => appLocalRxAxisMasters(VC_LOOPBACK_3_C),  -- [in]
         sAxisSlave  => appLocalRxAxisSlaves(VC_LOOPBACK_3_C),   -- [out]
         mAxisClk    => pgpClk,                                  -- [in]
         mAxisRst    => pgpRst,                                  -- [in]
         mAxisMaster => appLocalTxAxisMasters(VC_LOOPBACK_3_C),  -- [out]
         mAxisSlave  => appLocalTxAxisSlaves(VC_LOOPBACK_3_C));  -- [in]



end architecture rtl;
