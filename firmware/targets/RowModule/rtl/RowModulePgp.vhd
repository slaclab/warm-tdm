-------------------------------------------------------------------------------
-- Title      : Row Module PGP
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

entity RowModulePgp is

   generic (
      TPD_G          : time    := 1 ns;
      SIMULATION_G   : boolean := false;
      SIM_PORT_NUM_G : integer := 7000);

   port (
      pgpRefClkP : in  sl;
      pgpRefClkN : in  sl;
      pgpTxP     : out sl;
      pgpTxN     : out sl;
      pgpRxP     : in  sl;
      pgpRxN     : in  sl;

      axilClk         : out sl;
      axilRst         : out sl;
      axilWriteMaster : out AxiLiteWriteMasterType;
      axilWriteSlave  : in  AxiLiteWriteSlaveType;
      axilReadMaster  : out AxiLiteReadMasterType;
      axilReadSlave   : in  AxiLiteReadSlaveType);

end entity RowModulePgp;

architecture rtl of RowModulePgp is

   constant GTX_CFG_C : Gtx7CPllCfgType := getGtx7CPllCfg(312.5E6, 3.125E9);

   signal pgpClk       : sl;
   signal pgpRst       : sl;
   signal pgpTxIn      : Pgp2bTxInType;
   signal pgpTxOut     : Pgp2bTxOutType;
   signal pgpRxIn      : Pgp2bRxInType;
   signal pgpRxOut     : Pgp2bRxOutType;
   signal pgpTxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpTxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => => AXI_STREAM_SLAVE_INIT_C);
   signal pgpRxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));;
   signal pgpRxCtrl    : AxiStreamCtrlArray(3 downto 0)   := (others => AXI_STREAM_CTRL_UNUSED_C);

   signal fifoRxMasters : AxiStreamMasterArray(1 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal fifoRxSlaves  : AxiStreamSlaveArray(1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal fifoTxMasters : AxiStreamMasterArray(1 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal fifoTxSlaves  : AxiStreamSlaveArray(1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal appRxMasters : AxiStreamMasterArray(1 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appRxSlaves  : AxiStreamSlaveArray(1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal appTxMasters : AxiStreamMasterArray(1 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appTxSlaves  : AxiStreamSlaveArray(1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);


   constant NUM_AXIL_MASTERS_C : integer := 3;
   constant AXIL_EXT_C         : integer := 0;
   constant AXIL_PGP_C         : integer := 1;
   constant AXIL_GTX_C         : integer := 2;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_EXT_C      => (
         baseAddr     => X"00000000"
         addrBits     => 28,
         connectivity => X"FFFF"),
      AXIL_PGP_C      => (
         baseAddr     => X"A00000000",
         addrBits     => 8,
         connectivity => X"FFFF"),
      AXIL_GTX_C      => (
         baseAddr     => X"A0001000",
         addrBits     => 12,
         connectivity => X"FFFF"));

   signal mAxilWriteMaster : AxiLiteWriteMasterType;
   signal mAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal mAxilReadMaster  : AxiLiteReadMasterType;
   signal mAxilReadSlave   : AxiLiteReadSlaveType;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);


begin

   REAL_PGP_GEN : if (not SIMULATION_G) generate


      U_Pgp2bGtx7VarLatWrapper_1 : entity work.Pgp2bGtx7VarLatWrapper
         generic map (
            TPD_G              => TPD_G,
            CLKIN_PERIOD_G     => 6.4,
            DIVCLK_DIVIDE_G    => 1,
            CLKFBOUT_MULT_F_G  => 6.4,
            CLKOUT0_DIVIDE_F_G => 6.4,
--         CPLL_REFCLK_SEL_G  => CPLL_REFCLK_SEL_G,
            CPLL_FBDIV_G       => GTX_CFG_C.CPLL_FBDIV_G,
            CPLL_FBDIV_45_G    => GTX_CFG_C.CPLL_FBDIV_45_G,
            CPLL_REFCLK_DIV_G  => GTX_CFG_C.CPLL_REFCLK_DIV_G,
            RXOUT_DIV_G        => GTX_CFG_C.OUT_DIV_G,
            TXOUT_DIV_G        => GTX_CFG_C.OUT_DIV_G,
            RX_CLK25_DIV_G     => GTX_CFG_C.CLK5_DIV_G,
            TX_CLK25_DIV_G     => GTX_CFG_C.CLK25_DIV_G,
--          RX_OS_CFG_G        => RX_OS_CFG_G,
--          RXCDR_CFG_G        => RXCDR_CFG_G,
--          RXDFEXYDEN_G       => RXDFEXYDEN_G,
--          RX_DFE_KL_CFG2_G   => RX_DFE_KL_CFG2_G,
            VC_INTERLEAVE_G    => 1,
--         PAYLOAD_CNT_TOP_G  => PAYLOAD_CNT_TOP_G,
            NUM_VC_EN_G        => 2,
--          TX_POLARITY_G      => TX_POLARITY_G,
--          RX_POLARITY_G      => RX_POLARITY_G,
            TX_ENABLE_G        => true,
            RX_ENABLE_G        => true)
         port map (
            extRst          => '0',                              -- [in]
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
            gtClkP          => pgpRefClkP,                       -- [in]
            gtClkN          => pgpRefClkN,                       -- [in]
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
            axilWriteMaster => locAxilWriteMaster(AXIL_GTX_C),   -- [in]
            axilWriteSlave  => locAxilWriteSlaves(AXIL_GTX_C));  -- [out]

      U_Pgp2bAxi_1 : entity work.Pgp2bAxi
         generic map (
            TPD_G           => TPD_G,
            COMMON_TX_CLK_G => true,
            COMMON_RX_CLK_G => true,
            WRITE_EN_G      => false,
            AXI_CLK_FREQ_G  => 156.26E6)
         port map (
            pgpTxClk        => pgpClk,                           -- [in]
            pgpTxClkRst     => pgpRst,                           -- [in]
            pgpTxIn         => pgpTxIn,                          -- [out]
            pgpTxOut        => pgpTxOut,                         -- [in]
--         locTxIn         => locTxIn,          -- [in]
            pgpRxClk        => pgpClk,                           -- [in]
            pgpRxClkRst     => pgpst,                            -- [in]
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

   end generate REAL_PGP_GEN;

   SIM_GEN : if (SIMULATION_G) generate
      DESTS : for i in 1 downto 0 generate
         U_RogueTcpStreamWrap_1 : entity surf.RogueTcpStreamWrap
            generic map (
               TPD_G         => TPD_G,
               PORT_NUM_G    => SIM_PORT_NUM_G + i*2,
               SSI_EN_G      => true,
               CHAN_COUNT_G  => 1,
               AXIS_CONFIG_G => PACKETIZER2_AXIS_CFG_C)
            port map (
               axisClk     => ethClk,            -- [in]
               axisRst     => ethRst,            -- [in]
               sAxisMaster => pgpTxMasters(i),   -- [in]
               sAxisSlave  => pgpTxSlaves(i),    -- [out]
               mAxisMaster => pgpRxMasters(i),   -- [out]
               mAxisSlave  => pgpRxbSlaves(i));  -- [in]
      end generate;
   end generate SIM_GEN;

   RING_ROUTER_GEN : for i in 1 downto 0 generate
      -- buffers
      U_PgpRXVcFifo_1 : entity surf.PgpRXVcFifo
         generic map (
            TPD_G               => TPD_G,
            ROGUE_SIM_EN_G      => false,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 1,
--             VALID_THOLD_G       => VALID_THOLD_G,
--             VALID_BURST_MODE_G  => VALID_BURST_MODE_G,
            SYNTH_MODE_G        => "inferred",
            MEMORY_TYPE_G       => "block",
            GEN_SYNC_FIFO_G     => true,
            FIFO_ADDR_WIDTH_G   => 9,
            FIFO_PAUSE_THRESH_G => 256,
            PHY_AXI_CONFIG_G    => SSI_PGP2B_CONFIG_C,
            APP_AXI_CONFIG_G    => PACKETIZER2_AXIS_CFG_C)
         port map (
            pgpClk      => pgpClk,              -- [in]
            pgpRst      => pgpRst,              -- [in]
            rxlinkReady => pgpRxOut.linkReady,  -- [in]
            pgpRxMaster => pgpRxMasters(i),     -- [in]
            pgpRxCtrl   => pgpRxCtrl(i),        -- [out]
            pgpRxSlave  => pgpRxSlave(i),       -- [out]
            axisClk     => pgpClk,              -- [in]
            axisRst     => pgpRst,              -- [in]
            axisMaster  => fifoRxMasters(i),    -- [out]
            axisSlave   => fifoRxSlaves(i));    -- [in]


      U_RingRouter_1 : entity work.RingRouter
         generic map (
            TPD_G => TPD_G)
         port map (
            axisClk          => pgpClk,               -- [in]
            axisRst          => pgpRst,               -- [in]
            address          => address,              -- [in]
            rxLinkGood       => pgpRxOut.linkReady,   -- [in]
            txLinkGood       => pgpTxOut.linkReady,   -- [in]
            rxLinkAxisMaster => fifoRxMasters(i),     -- [in]
            rxLinkAxisSlave  => fifoRxSlaves(i),      -- [out]
            txLinkAxisMaster => fifoTxMasters(i),     -- [out]
            txLinkAxisSlave  => fifoTxSlaves(i),      -- [in]
            rxAppAxisMaster  => appRxAxisMasters(i),  -- [out]
            rxAppAxisSlave   => appRxAxisSlaves(i),   -- [in]
            txAppAxisMaster  => appTxAxisMasters(i),  -- [in]
            txAppAxisSlave   => appTxAxisSlaves(i));  -- [out]

      U_PgpTXVcFifo_1 : entity work.PgpTXVcFifo
         generic map (
            TPD_G             => TPD_G,
            INT_PIPE_STAGES_G => 1,
            PIPE_STAGES_G     => 1,
--             VALID_THOLD_G      => VALID_THOLD_G,
--             VALID_BURST_MODE_G => VALID_BURST_MODE_G,
            SYNTH_MODE_G      => "inferred",
            MEMORY_TYPE_G     => "block"
            GEN_SYNC_FIFO_G   => true,
            FIFO_ADDR_WIDTH_G => 9,
            APP_AXI_CONFIG_G  => PACKETIZER2_AXIS_CFG_C,
            PHY_AXI_CONFIG_G  => SSI_PGP2B_CONFIG_C)
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

   -- VC 0 is the SRP channel
   U_SrpV3AxiLite_1 : entity work.SrpV3AxiLite
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 1,
--          FIFO_PAUSE_THRESH_G   => FIFO_PAUSE_THRESH_G,
--          FIFO_SYNTH_MODE_G     => FIFO_SYNTH_MODE_G,
--          TX_VALID_THOLD_G      => TX_VALID_THOLD_G,
--          TX_VALID_BURST_MODE_G => TX_VALID_BURST_MODE_G,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => true,
         AXIL_CLK_FREQ_G     => 156.25E6
         AXI_STREAM_CONFIG_G => PACKETIZER2_AXIS_CFG_C)
      port map (
         sAxisClk         => pgpClk,               -- [in]
         sAxisRst         => pgpRst,               -- [in]
         sAxisMaster      => appRxAxisMasters(0),  -- [in]
         sAxisSlave       => appRxAxisSlaves(0),   -- [out]
         sAxisCtrl        => open,                 -- [out]
         mAxisClk         => pgpClk,               -- [in]
         mAxisRst         => pgpRst,               -- [in]
         mAxisMaster      => appTxAxisMasters(0),  -- [out]
         mAxisSlave       => appTxAxisSlaves(0),   -- [in]
         axilClk          => pgpClk,               -- [in]
         axilRst          => pgpRst,               -- [in]
         mAxilWriteMaster => mAxilWriteMaster,     -- [out]
         mAxilWriteSlave  => mAxilWriteSlave,      -- [in]
         mAxilReadMaster  => mAxilReadMaster,      -- [out]
         mAxilReadSlave   => mAxilReadSlave);      -- [in]

   -- VC 1 is the data channel and is unused by the Row Module
   txAppAxisMaster(1) <= axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C);
   rxAppAxisSlave(1)  <= AXI_STREAM_SLAVE_FORCE_C;

   U_AxiLiteCrossbar_1 : entity work.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,              -- [in]
         axiClkRst           => axilRst,              -- [in]
         sAxiWriteMasters(0) => mAxilWriteMaster,     -- [in]
         sAxiWriteSlaves(0)  => mAxilWriteSlave,      -- [out]
         sAxiReadMasters(0)  => mAxilReadMaster,      -- [in]
         sAxiReadSlaves(0)   => mAxilReadSlave,       -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]

   axilClk                       <= pgpClk;
   axilRst                       <= pgpRst;
   axilWriteMaster               <= locAxilWriteMasters(AXI_EXT_C);
   locAxilWriteSlaves(AXI_EXT_C) <= axilWriteSlave;
   axilReadMaster                <= locAxilReadMasters(AXI_EXT_C);
   locAxilReadMasters(AXI_EXT_C) <= axilReadSlave;

end architecture rtl;
