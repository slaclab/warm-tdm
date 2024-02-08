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
      REF_CLK_FREQ_G   : real             := 250.0E+6;
      RING_ADDR_0_G    : boolean          := false;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := X"00000000");

   port (
      -- GT Ports and clock
      refRst    : in  sl;
      gtRefClk  : in  sl;
      fabRefClk : in  sl;
      pgpTxP    : out slv(1 downto 0) := (others => '0');
      pgpTxN    : out slv(1 downto 0) := (others => '1');
      pgpRxP    : in  slv(1 downto 0);
      pgpRxN    : in  slv(1 downto 0);
      pgpTxLink : out sl;
      pgpRxLink : out sl;
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

   constant GTX_CFG_C : Gtx7CPllCfgType := getGtx7CPllCfg(REF_CLK_FREQ_G, 1.25E9);

   constant PACKET_SIZE_BYTES_C : integer := 512;

   signal pgpClk       : sl;
   signal pgpRst       : sl;
   signal pgpTxIn      : Pgp2bTxInArray(1 downto 0)       := (others => PGP2B_TX_IN_HALF_DUPLEX_C);
   signal pgpTxOut     : Pgp2bTxOutArray(1 downto 0)      := (others => PGP2B_TX_OUT_INIT_C);
   signal pgpRxIn      : Pgp2bRxInArray(1 downto 0)       := (others => PGP2B_RX_IN_INIT_C);
   signal pgpRxOut     : Pgp2bRxOutArray(1 downto 0)      := (others => PGP2B_RX_OUT_INIT_C);
   signal locPgpTxIn   : Pgp2bTxInArray(1 downto 0)       := (others => PGP2B_TX_IN_HALF_DUPLEX_C);
   signal pgpTxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpTxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal pgpRxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpRxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal pgpRxCtrl    : AxiStreamCtrlArray(3 downto 0)   := (others => AXI_STREAM_CTRL_UNUSED_C);
   signal locPgpRxCtrl : AxiStreamCtrlArray(3 downto 0)   := (others => AXI_STREAM_CTRL_UNUSED_C);
   signal locData      : slv(7 downto 0)                  := (others => '0');

   signal iAxiClk : sl;
   signal iAxiRst : sl;

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

   constant NUM_AXIL_MASTERS_C : integer := 4;
   constant AXIL_PGP_0_C       : integer := 0;
   constant AXIL_GTX_0_C       : integer := 1;
   constant AXIL_PGP_1_C       : integer := 2;
   constant AXIL_GTX_1_C       : integer := 3;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_PGP_0_C    => (
         baseAddr     => AXIL_BASE_ADDR_G + X"00000000",
         addrBits     => 8,
         connectivity => X"FFFF"),
      AXIL_GTX_0_C    => (
         baseAddr     => AXIL_BASE_ADDR_G + X"00001000",
         addrBits     => 12,
         connectivity => X"FFFF"),
      AXIL_PGP_1_C    => (
         baseAddr     => AXIL_BASE_ADDR_G + X"00002000",
         addrBits     => 8,
         connectivity => X"FFFF"),
      AXIL_GTX_1_C    => (
         baseAddr     => AXIL_BASE_ADDR_G + X"00003000",
         addrBits     => 12,
         connectivity => X"FFFF"));

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0) := (others => AXI_LITE_WRITE_MASTER_INIT_C);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_READ_MASTER_INIT_C);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)   := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);


begin

   pgpTxLink <= pgpTxOut(0).linkReady;
   pgpRxLink <= pgpRxOut(0).linkReady;

   locPgpTxIn(0).flowCntlDis <= '0' when RING_ADDR_0_G else '1';

   ClockManager7_Inst : entity surf.ClockManager7
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
         clkIn     => fabRefClk,
         rstIn     => refRst,
         clkOut(0) => iAxiClk,
         clkOut(1) => pgpClk,
         rstOut(0) => iAxiRst,
         rstOut(1) => pgpRst);

   axiClk <= iAxiClk;
   axiRst <= iAxiRst;

    REAL_PGP_GEN : if (true) generate --SIM_PORT_NUM_G = 0) generate
      Pgp2bGtx7VarLat_Inst_0 : entity surf.Pgp2bGtx7VarLat
         generic map (
            TPD_G                 => TPD_G,
            SIM_GTRESET_SPEEDUP_G => "TRUE",
            SIM_VERSION_G         => "4.0",
            -- CPLL Configurations
            TX_PLL_G              => "CPLL",
            RX_PLL_G              => "CPLL",
            CPLL_FBDIV_G          => GTX_CFG_C.CPLL_FBDIV_G,
            CPLL_FBDIV_45_G       => GTX_CFG_C.CPLL_FBDIV_45_G,
            CPLL_REFCLK_DIV_G     => GTX_CFG_C.CPLL_REFCLK_DIV_G,
            RXOUT_DIV_G           => GTX_CFG_C.OUT_DIV_G,
            TXOUT_DIV_G           => GTX_CFG_C.OUT_DIV_G,
            RX_CLK25_DIV_G        => GTX_CFG_C.CLK25_DIV_G,
            TX_CLK25_DIV_G        => GTX_CFG_C.CLK25_DIV_G,
            -- MGT Configurations
            RX_OS_CFG_G           => "0000010000000",        --RX_OS_CFG_G,
            RXCDR_CFG_G           => X"03000023FF10100020",  -- X"0000107FE106001041010",  --x"03000023ff10100020",  -- RXCDR_CFG_G,

            RXDFEXYDEN_G      => '1',   --RXDFEXYDEN_G,
            PMA_RSV_G         => x"00018480",
            RX_DFE_KL_CFG2_G  => X"301148AC",
            -- VC Configuration
            VC_INTERLEAVE_G   => 1,
            PAYLOAD_CNT_TOP_G => 7,
            NUM_VC_EN_G       => 4)
         port map (
            -- GT Clocking
            stableClk        => fabRefClk,
            gtCPllRefClk     => gtRefClk,
            gtCPllLock       => open,
            gtQPllRefClk     => '0',
            gtQPllClk        => '0',
            gtQPllLock       => '1',
            gtQPllRefClkLost => '0',
            gtQPllReset      => open,
            -- GT Serial IO
            gtTxP            => pgpTxP(0),
            gtTxN            => pgpTxN(0),
            gtRxP            => pgpRxP(0),
            gtRxN            => pgpRxN(0),
            -- Tx Clocking
            pgpTxReset       => pgpRst,
            pgpTxRecClk      => open,
            pgpTxClk         => pgpClk,
            pgpTxMmcmReset   => open,
            pgpTxMmcmLocked  => '1',
            -- Rx clocking
            pgpRxReset       => pgpRst,
            pgpRxRecClk      => open,
            pgpRxClk         => pgpClk,
            pgpRxMmcmReset   => open,
            pgpRxMmcmLocked  => '1',
            -- Non VC TX Signals
            pgpTxIn          => pgpTxIn(0),
            pgpTxOut         => pgpTxOut(0),
            -- Non VC RX Signals
            pgpRxIn          => pgpRxIn(0),
            pgpRxOut         => pgpRxOut(0),
            -- Frame TX Interface
            pgpTxMasters     => pgpTxMasters,
            pgpTxSlaves      => pgpTxSlaves,
            -- Frame RX Interface
            pgpRxMasters     => pgpRxMasters,
            pgpRxCtrl        => pgpRxCtrl,
            -- Debug Interface
--             txPreCursor      => txPreCursor,
--             txPostCursor     => txPostCursor,
--             txDiffCtrl       => txDiffCtrl,
            -- AXI-Lite Interface
            axilClk          => iAxiClk,
            axilRst          => iAxiRst,
            axilReadMaster   => locAxilReadMasters(AXIL_GTX_0_C),
            axilReadSlave    => locAxilReadSlaves(AXIL_GTX_0_C),
            axilWriteMaster  => locAxilWriteMasters(AXIL_GTX_0_C),
            axilWriteSlave   => locAxilWriteSlaves(AXIL_GTX_0_C));

      PGP_RX_CTRL : process (locPgpRxCtrl, pgpRxOut) is
         variable tmp : AxiStreamCtrlArray(3 downto 0);
      begin
         tmp := locPgpRxCtrl;
         for i in 3 downto 0 loop
            if (RING_ADDR_0_G = false) then
               if (pgpRxOut(0).linkReady = '1') then
                  tmp(i).pause := locPgpRxCtrl(i).pause or pgpRxOut(0).remPause(i);
               end if;
            end if;
         end loop;
         pgpRxCtrl <= tmp;

      end process PGP_RX_CTRL;

      Pgp2bGtx7VarLat_Inst_1 : entity surf.Pgp2bGtx7VarLat
         generic map (
            TPD_G                 => TPD_G,
            SIM_GTRESET_SPEEDUP_G => "TRUE",
            SIM_VERSION_G         => "4.0",
            -- CPLL Configurations
            TX_PLL_G              => "CPLL",
            RX_PLL_G              => "CPLL",
            CPLL_FBDIV_G          => GTX_CFG_C.CPLL_FBDIV_G,
            CPLL_FBDIV_45_G       => GTX_CFG_C.CPLL_FBDIV_45_G,
            CPLL_REFCLK_DIV_G     => GTX_CFG_C.CPLL_REFCLK_DIV_G,
            RXOUT_DIV_G           => GTX_CFG_C.OUT_DIV_G,
            TXOUT_DIV_G           => GTX_CFG_C.OUT_DIV_G,
            RX_CLK25_DIV_G        => GTX_CFG_C.CLK25_DIV_G,
            TX_CLK25_DIV_G        => GTX_CFG_C.CLK25_DIV_G,
            -- MGT Configurations
            RX_OS_CFG_G           => "0000010000000",        --RX_OS_CFG_G,
            RXCDR_CFG_G           => X"03000023ff10100020",  -- RXCDR_CFG_G,
            RXDFEXYDEN_G          => '1',                    --RXDFEXYDEN_G,
            PMA_RSV_G             => x"00018480",
            RX_DFE_KL_CFG2_G      => X"301148AC",
            -- VC Configuration
            VC_INTERLEAVE_G       => 1,
            PAYLOAD_CNT_TOP_G     => 7,
            NUM_VC_EN_G           => 1)
         port map (
            -- GT Clocking
            stableClk        => fabRefClk,
            gtCPllRefClk     => gtRefClk,
            gtCPllLock       => open,
            gtQPllRefClk     => '0',
            gtQPllClk        => '0',
            gtQPllLock       => '1',
            gtQPllRefClkLost => '0',
            gtQPllReset      => open,
            -- GT Serial IO
            gtTxP            => pgpTxP(1),
            gtTxN            => pgpTxN(1),
            gtRxP            => pgpRxP(1),
            gtRxN            => pgpRxN(1),
            -- Tx Clocking
            pgpTxReset       => pgpRst,
            pgpTxRecClk      => open,
            pgpTxClk         => pgpClk,
            pgpTxMmcmReset   => open,
            pgpTxMmcmLocked  => '1',
            -- Rx clocking
            pgpRxReset       => pgpRst,
            pgpRxRecClk      => open,
            pgpRxClk         => pgpClk,
            pgpRxMmcmReset   => open,
            pgpRxMmcmLocked  => '1',
            -- Non VC TX Signals
            pgpTxIn          => pgpTxIn(1),
            pgpTxOut         => pgpTxOut(1),
            -- Non VC RX Signals
            pgpRxIn          => pgpRxIn(1),
            pgpRxOut         => pgpRxOut(1),
            -- Frame TX Interface
            pgpTxMasters     => (others => AXI_STREAM_MASTER_INIT_C),
            pgpTxSlaves      => open,
            -- Frame RX Interface
            pgpRxMasters     => open,
            pgpRxCtrl        => (others => AXI_STREAM_CTRL_UNUSED_C),
            -- Debug Interface
--             txPreCursor      => txPreCursor,
--             txPostCursor     => txPostCursor,
--             txDiffCtrl       => txDiffCtrl,
            -- AXI-Lite Interface
            axilClk          => iAxiClk,
            axilRst          => iAxiRst,
            axilReadMaster   => locAxilReadMasters(AXIL_GTX_1_C),
            axilReadSlave    => locAxilReadSlaves(AXIL_GTX_1_C),
            axilWriteMaster  => locAxilWriteMasters(AXIL_GTX_1_C),
            axilWriteSlave   => locAxilWriteSlaves(AXIL_GTX_1_C));

  end generate;

--    SIM_GEN : if (SIM_PORT_NUM_G > 0) generate

--       U_RoguePgp2bSim_1 : entity surf.RoguePgp2bSim
--          generic map (
--             TPD_G         => TPD_G,
--             PORT_NUM_G    => 7000,         --SIM_PORT_NUM_G,
--             NUM_VC_G      => 4,
--             EN_SIDEBAND_G => true)
--          port map (
--             pgpClk       => pgpClk,        -- [in]
--             pgpClkRst    => pgpRst,        -- [in]
--             pgpRxIn      => pgpRxIn(0),    -- [in]
--             pgpRxOut     => pgpRxOut(0),   -- [out]
--             pgpTxIn      => pgpTxIn(0),    -- [in]
--             pgpTxOut     => pgpTxOut(0),   -- [out]
--             pgpTxMasters => pgpTxMasters,  -- [in]
--             pgpTxSlaves  => pgpTxSlaves,   -- [out]
--             pgpRxMasters => pgpRxMasters,  -- [out]
--             pgpRxSlaves  => pgpRxSlaves);  -- [in]

--    end generate;

   U_Pgp2bAxi_0 : entity surf.Pgp2bAxi
      generic map (
         TPD_G             => TPD_G,
         COMMON_TX_CLK_G   => false,
         COMMON_RX_CLK_G   => false,
         WRITE_EN_G        => true,
         AXI_CLK_FREQ_G    => 125.0E6,
         ERROR_CNT_WIDTH_G => 16)
      port map (
         pgpTxClk        => pgpClk,                             -- [in]
         pgpTxClkRst     => pgpRst,                             -- [in]
         pgpTxIn         => pgpTxIn(0),                         -- [out]
         pgpTxOut        => pgpTxOut(0),                        -- [in]
         locTxIn         => locPgpTxIn(0),                      -- [in]
         pgpRxClk        => pgpClk,                             -- [in]
         pgpRxClkRst     => pgpRst,                             -- [in]
         pgpRxIn         => pgpRxIn(0),                         -- [out]
         pgpRxOut        => pgpRxOut(0),                        -- [in]
--         locRxIn         => locRxIn,          -- [in]
--          statusWord      => statusWord,       -- [out]
--          statusSend      => statusSend,       -- [out]
         axilClk         => iAxiClk,                            -- [in]
         axilRst         => iAxiRst,                            -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_PGP_0_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_PGP_0_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_PGP_0_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_PGP_0_C));  -- [out]

   U_Pgp2bAxi_1 : entity surf.Pgp2bAxi
      generic map (
         TPD_G             => TPD_G,
         COMMON_TX_CLK_G   => false,
         COMMON_RX_CLK_G   => false,
         WRITE_EN_G        => true,
         AXI_CLK_FREQ_G    => 125.0E6,
         ERROR_CNT_WIDTH_G => 16)
      port map (
         pgpTxClk        => pgpClk,                             -- [in]
         pgpTxClkRst     => pgpRst,                             -- [in]
         pgpTxIn         => pgpTxIn(1),                         -- [out]
         pgpTxOut        => pgpTxOut(1),                        -- [in]
         locTxIn         => locPgpTxIn(1),                      -- [in]
         pgpRxClk        => pgpClk,                             -- [in]
         pgpRxClkRst     => pgpRst,                             -- [in]
         pgpRxIn         => pgpRxIn(1),                         -- [out]
         pgpRxOut        => pgpRxOut(1),                        -- [in]
--         locRxIn         => locRxIn,          -- [in]
--          statusWord      => statusWord,       -- [out]
--          statusSend      => statusSend,       -- [out]
         axilClk         => iAxiClk,                            -- [in]
         axilRst         => iAxiRst,                            -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_PGP_1_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_PGP_1_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_PGP_1_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_PGP_1_C));  -- [out]



   RING_ROUTER_GEN : for i in 3 downto 0 generate
      -- buffers
      U_PgpRXVcFifo_1 : entity surf.PgpRXVcFifo
         generic map (
            TPD_G               => TPD_G,
            ROGUE_SIM_EN_G      => SIMULATION_G,
--            FILTER_G            => true,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 0,
            VALID_THOLD_G       => PACKET_SIZE_BYTES_C/8,
            VALID_BURST_MODE_G  => true,
            SYNTH_MODE_G        => "inferred",
            MEMORY_TYPE_G       => "block",
            GEN_SYNC_FIFO_G     => false,
            FIFO_ADDR_WIDTH_G   => 8,
            FIFO_PAUSE_THRESH_G => PACKET_SIZE_BYTES_C/4,
            PHY_AXI_CONFIG_G    => SSI_PGP2B_CONFIG_C,
            APP_AXI_CONFIG_G    => AXIS_CONFIG_C)
         port map (
            pgpClk      => pgpClk,                 -- [in]
            pgpRst      => pgpRst,                 -- [in]
            rxlinkReady => pgpRxOut(0).linkReady,  -- [in]
            pgpRxMaster => pgpRxMasters(i),        -- [in]
            pgpRxCtrl   => locPgpRxCtrl(i),        -- [out]
            pgpRxSlave  => pgpRxSlaves(i),         -- [out]
            axisClk     => iAxiClk,                -- [in]
            axisRst     => iAxiRst,                -- [in]
            axisMaster  => fifoRxMasters(i),       -- [out]
            axisSlave   => fifoRxSlaves(i));       -- [in]

      address <= ite(RING_ADDR_0_G, "000", pgpRxOut(0).remLinkData(2 downto 0) + 1);

      locPgpTxIn(0).locData <= "00000" & address;
      locPgpTxIn(1).locData <= X"AA";
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
            TPD_G               => TPD_G,
            PACKET_SIZE_BYTES_G => PACKET_SIZE_BYTES_C)
         port map (
            axisClk          => iAxiClk,                -- [in]
            axisRst          => iAxiRst,                -- [in]
            address          => address,                -- [in]
            linkRxGood       => pgpRxOut(0).linkReady,  -- [in]
            linkTxGood       => pgpTxOut(0).linkReady,  -- [in]
            linkRxAxisMaster => fifoRxMasters(i),       -- [in]
            linkRxAxisSlave  => fifoRxSlaves(i),        -- [out]
            linkTxAxisMaster => fifoTxMasters(i),       -- [out]
            linkTxAxisSlave  => fifoTxSlaves(i),        -- [in]
            appRxAxisMaster  => appRxAxisMasters(i),    -- [out]
            appRxAxisSlave   => appRxAxisSlaves(i),     -- [in]
            appTxAxisMaster  => appTxAxisMasters(i),    -- [in]
            appTxAxisSlave   => appTxAxisSlaves(i));    -- [out]

      U_PgpTXVcFifo_1 : entity surf.PgpTXVcFifo
         generic map (
            TPD_G              => TPD_G,
            INT_PIPE_STAGES_G  => 1,
            PIPE_STAGES_G      => 0,
--            VALID_THOLD_G      => 500,
            VALID_BURST_MODE_G => true,
            SYNTH_MODE_G       => "inferred",
            MEMORY_TYPE_G      => "block",
            GEN_SYNC_FIFO_G    => false,
            FIFO_ADDR_WIDTH_G  => 8,
            APP_AXI_CONFIG_G   => AXIS_CONFIG_C,
            PHY_AXI_CONFIG_G   => SSI_PGP2B_CONFIG_C)
         port map (
            axisClk     => iAxiClk,                -- [in]
            axisRst     => iAxiRst,                -- [in]
            axisMaster  => fifoTxMasters(i),       -- [in]
            axisSlave   => fifoTxSlaves(i),        -- [out]
            pgpClk      => pgpClk,                 -- [in]
            pgpRst      => pgpRst,                 -- [in]
            rxlinkReady => pgpRxOut(0).linkReady,  -- [in]
            txlinkReady => pgpTxOut(0).linkReady,  -- [in]
            pgpTxMaster => pgpTxMasters(i),        -- [out]
            pgpTxSlave  => pgpTxSlaves(i));        -- [in]

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
            axisClk         => iAxiClk,                   -- [in]
            axisRst         => iAxiRst,                   -- [in]
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
            axisClk         => iAxiClk,                   -- [in]
            axisRst         => iAxiRst,                   -- [in]
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
   U_SrpV3AxiLite_1 : entity surf.SrpV3AxiLite
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         FIFO_ADDR_WIDTH_G   => 9,
--         FIFO_PAUSE_THRESH_G   => 8,
--          FIFO_SYNTH_MODE_G     => FIFO_SYNTH_MODE_G,
--          TX_VALID_THOLD_G      => TX_VALID_THOLD_G,
--          TX_VALID_BURST_MODE_G => TX_VALID_BURST_MODE_G,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => true,
         AXIL_CLK_FREQ_G     => 125.0E6,
         AXI_STREAM_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk         => iAxiClk,                          -- [in]
         sAxisRst         => iAxiRst,                          -- [in]
         sAxisMaster      => appLocalRxAxisMasters(VC_SRP_C),  -- [in]
         sAxisSlave       => appLocalRxAxisSlaves(VC_SRP_C),   -- [out]
         sAxisCtrl        => open,                             -- [out]
         mAxisClk         => iAxiClk,                          -- [in]
         mAxisRst         => iAxiRst,                          -- [in]
         mAxisMaster      => appLocalTxAxisMasters(VC_SRP_C),  -- [out]
         mAxisSlave       => appLocalTxAxisSlaves(VC_SRP_C),   -- [in]
         axilClk          => iAxiClk,                          -- [in]
         axilRst          => iAxiRst,                          -- [in]
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
         DEBUG_G            => true)
      port map (
         axiClk              => iAxiClk,              -- [in]
         axiClkRst           => iAxiRst,              -- [in]
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
         sAxisClk    => iAxiClk,                                 -- [in]
         sAxisRst    => iAxiRst,                                 -- [in]
         sAxisMaster => appLocalRxAxisMasters(VC_LOOPBACK_2_C),  -- [in]
         sAxisSlave  => appLocalRxAxisSlaves(VC_LOOPBACK_2_C),   -- [out]
         mAxisClk    => iAxiClk,                                 -- [in]
         mAxisRst    => iAxiRst,                                 -- [in]
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
         sAxisClk    => iAxiClk,                                 -- [in]
         sAxisRst    => iAxiRst,                                 -- [in]
         sAxisMaster => appLocalRxAxisMasters(VC_LOOPBACK_3_C),  -- [in]
         sAxisSlave  => appLocalRxAxisSlaves(VC_LOOPBACK_3_C),   -- [out]
         mAxisClk    => iAxiClk,                                 -- [in]
         mAxisRst    => iAxiRst,                                 -- [in]
         mAxisMaster => appLocalTxAxisMasters(VC_LOOPBACK_3_C),  -- [out]
         mAxisSlave  => appLocalTxAxisSlaves(VC_LOOPBACK_3_C));  -- [in]



end architecture rtl;
