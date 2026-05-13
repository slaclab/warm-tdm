-------------------------------------------------------------------------------
-- Title      : PGP Ring Interface for Warm TDM
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
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
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
use surf.AxiLitePkg.all;
use surf.Pgp2bPkg.all;

library warm_tdm;

entity PgpCore is
   generic (
      TPD_G            : time             := 1 ns;
      SIMULATION_G     : boolean          := false;
      FPGA_FAMILY_G    : string           := "7SERIES";
      SIM_PORT_NUM_G   : integer          := 7000;
      REF_CLK_FREQ_G   : real             := 250.0E+6;
      RING_ADDR_0_G    : boolean          := false;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := X"00000000");
   port (
      refRst           : in  sl;
      gtRefClk         : in  sl;
      fabRefClk        : in  sl;
      pgpTxP           : out slv(1 downto 0)       := (others => '0');
      pgpTxN           : out slv(1 downto 0)       := (others => '1');
      pgpRxP           : in  slv(1 downto 0);
      pgpRxN           : in  slv(1 downto 0);
      pgpTxLink        : out sl;
      pgpRxLink        : out sl;
      axiClk           : out sl;
      axiRst           : out sl;
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      ethRxAxisMasters : in  AxiStreamMasterArray(3 downto 0);
      ethRxAxisSlaves  : out AxiStreamSlaveArray(3 downto 0);
      ethTxAxisMasters : out AxiStreamMasterArray(3 downto 0);
      ethTxAxisSlaves  : in  AxiStreamSlaveArray(3 downto 0);
      dataTxAxisMaster : in  AxiStreamMasterType;
      dataTxAxisSlave  : out AxiStreamSlaveType;
      dataRxAxisMaster : out AxiStreamMasterType;
      dataRxAxisSlave  : in  AxiStreamSlaveType);
end entity PgpCore;

architecture rtl of PgpCore is

   constant AXIS_CONFIG_C       : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 8, tDestBits => 8);
   constant PACKET_SIZE_BYTES_C : integer             := 512;

   component PgpPhy7s is
      generic (
         TPD_G          : time := 1 ns;
         REF_CLK_FREQ_G : real := 250.0E+6);
      port (
         refRst          : in  sl;
         gtRefClk        : in  sl;
         fabRefClk       : in  sl;
         pgpTxP          : out sl;
         pgpTxN          : out sl;
         pgpRxP          : in  sl;
         pgpRxN          : in  sl;
         pgpClk          : out sl;
         pgpRst          : out sl;
         axiClk          : out sl;
         axiRst          : out sl;
         pgpTxIn         : in  Pgp2bTxInType;
         pgpTxOut        : out Pgp2bTxOutType;
         pgpRxIn         : in  Pgp2bRxInType;
         pgpRxOut        : out Pgp2bRxOutType;
         pgpTxMasters    : in  AxiStreamMasterArray(3 downto 0);
         pgpTxSlaves     : out AxiStreamSlaveArray(3 downto 0);
         pgpRxMasters    : out AxiStreamMasterArray(3 downto 0);
         pgpRxCtrl       : in  AxiStreamCtrlArray(3 downto 0);
         axilClk         : in  sl;
         axilRst         : in  sl;
         axilReadMaster  : in  AxiLiteReadMasterType;
         axilReadSlave   : out AxiLiteReadSlaveType;
         axilWriteMaster : in  AxiLiteWriteMasterType;
         axilWriteSlave  : out AxiLiteWriteSlaveType);
   end component;

   component PgpPhyUsp is
      generic (
         TPD_G          : time := 1 ns;
         REF_CLK_FREQ_G : real := 250.0E+6);
      port (
         refRst          : in  sl;
         gtRefClk        : in  sl;
         fabRefClk       : in  sl;
         pgpTxP          : out sl;
         pgpTxN          : out sl;
         pgpRxP          : in  sl;
         pgpRxN          : in  sl;
         pgpClk          : out sl;
         pgpRst          : out sl;
         axiClk          : out sl;
         axiRst          : out sl;
         pgpTxIn         : in  Pgp2bTxInType;
         pgpTxOut        : out Pgp2bTxOutType;
         pgpRxIn         : in  Pgp2bRxInType;
         pgpRxOut        : out Pgp2bRxOutType;
         pgpTxMasters    : in  AxiStreamMasterArray(3 downto 0);
         pgpTxSlaves     : out AxiStreamSlaveArray(3 downto 0);
         pgpRxMasters    : out AxiStreamMasterArray(3 downto 0);
         pgpRxCtrl       : in  AxiStreamCtrlArray(3 downto 0);
         axilClk         : in  sl;
         axilRst         : in  sl;
         axilReadMaster  : in  AxiLiteReadMasterType;
         axilReadSlave   : out AxiLiteReadSlaveType;
         axilWriteMaster : in  AxiLiteWriteMasterType;
         axilWriteSlave  : out AxiLiteWriteSlaveType);
   end component;

   constant VC_SRP_C        : integer := 0;
   constant VC_DATA_C       : integer := 1;
   constant VC_LOOPBACK_2_C : integer := 2;
   constant VC_LOOPBACK_3_C : integer := 3;

   constant NUM_AXIL_MASTERS_C : integer := 2;
   constant AXIL_PGP_0_C      : integer := 0;
   constant AXIL_GTX_0_C      : integer := 1;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_PGP_0_C => (baseAddr => AXIL_BASE_ADDR_G + X"00000000", addrBits => 8, connectivity => X"FFFF"),
      AXIL_GTX_0_C => (baseAddr => AXIL_BASE_ADDR_G + X"00001000", addrBits => 12, connectivity => X"FFFF"));

   signal iAxiClk : sl;
   signal iAxiRst : sl;
   signal pgpClk  : sl;
   signal pgpRst  : sl;

   signal pgpTxIn    : Pgp2bTxInType  := PGP2B_TX_IN_HALF_DUPLEX_C;
   signal pgpTxOut   : Pgp2bTxOutType := PGP2B_TX_OUT_INIT_C;
   signal pgpRxIn    : Pgp2bRxInType  := PGP2B_RX_IN_INIT_C;
   signal pgpRxOut   : Pgp2bRxOutType := PGP2B_RX_OUT_INIT_C;
   signal locPgpTxIn : Pgp2bTxInType  := PGP2B_TX_IN_HALF_DUPLEX_C;

   signal pgpTxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpTxSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal pgpRxMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(SSI_PGP2B_CONFIG_C));
   signal pgpRxCtrl    : AxiStreamCtrlArray(3 downto 0)   := (others => AXI_STREAM_CTRL_UNUSED_C);

   signal appRxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appRxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal appTxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appTxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal appLocalRxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appLocalRxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal appLocalTxAxisMasters : AxiStreamMasterArray(3 downto 0) := (others => axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C));
   signal appLocalTxAxisSlaves  : AxiStreamSlaveArray(3 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal address : slv(2 downto 0) := "111";

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0) := (others => AXI_LITE_WRITE_MASTER_INIT_C);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0)  := (others => AXI_LITE_READ_MASTER_INIT_C);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0)   := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

begin

   pgpTxLink <= pgpTxOut.linkReady;
   pgpRxLink <= pgpRxOut.linkReady;
   axiClk    <= iAxiClk;
   axiRst    <= iAxiRst;

   locPgpTxIn.flowCntlDis <= '0' when RING_ADDR_0_G else '1';
   locPgpTxIn.locData     <= "00000" & address;

   address <= ite(RING_ADDR_0_G, "000", pgpRxOut.remLinkData(2 downto 0) + 1);

   ---------------------------------------------------------------------------
   -- PHY Layer (architecture-specific)
   -- Using component instantiation so the inactive generate path
   -- doesn't force elaboration of the other family's PHY entity.
   ---------------------------------------------------------------------------
   GEN_7SERIES : if (FPGA_FAMILY_G = "7SERIES") generate
      U_Phy : PgpPhy7s
         generic map (
            TPD_G          => TPD_G,
            REF_CLK_FREQ_G => REF_CLK_FREQ_G)
         port map (
            refRst          => refRst,
            gtRefClk        => gtRefClk,
            fabRefClk       => fabRefClk,
            pgpTxP          => pgpTxP(0),
            pgpTxN          => pgpTxN(0),
            pgpRxP          => pgpRxP(0),
            pgpRxN          => pgpRxN(0),
            pgpClk          => pgpClk,
            pgpRst          => pgpRst,
            axiClk          => iAxiClk,
            axiRst          => iAxiRst,
            pgpTxIn         => pgpTxIn,
            pgpTxOut        => pgpTxOut,
            pgpRxIn         => pgpRxIn,
            pgpRxOut        => pgpRxOut,
            pgpTxMasters    => pgpTxMasters,
            pgpTxSlaves     => pgpTxSlaves,
            pgpRxMasters    => pgpRxMasters,
            pgpRxCtrl       => pgpRxCtrl,
            axilClk         => iAxiClk,
            axilRst         => iAxiRst,
            axilReadMaster  => locAxilReadMasters(AXIL_GTX_0_C),
            axilReadSlave   => locAxilReadSlaves(AXIL_GTX_0_C),
            axilWriteMaster => locAxilWriteMasters(AXIL_GTX_0_C),
            axilWriteSlave  => locAxilWriteSlaves(AXIL_GTX_0_C));
   end generate;

   GEN_ULTRASCALE_PLUS : if (FPGA_FAMILY_G = "ULTRASCALE_PLUS") generate
      U_Phy : PgpPhyUsp
         generic map (
            TPD_G          => TPD_G,
            REF_CLK_FREQ_G => REF_CLK_FREQ_G)
         port map (
            refRst          => refRst,
            gtRefClk        => gtRefClk,
            fabRefClk       => fabRefClk,
            pgpTxP          => pgpTxP(0),
            pgpTxN          => pgpTxN(0),
            pgpRxP          => pgpRxP(0),
            pgpRxN          => pgpRxN(0),
            pgpClk          => pgpClk,
            pgpRst          => pgpRst,
            axiClk          => iAxiClk,
            axiRst          => iAxiRst,
            pgpTxIn         => pgpTxIn,
            pgpTxOut        => pgpTxOut,
            pgpRxIn         => pgpRxIn,
            pgpRxOut        => pgpRxOut,
            pgpTxMasters    => pgpTxMasters,
            pgpTxSlaves     => pgpTxSlaves,
            pgpRxMasters    => pgpRxMasters,
            pgpRxCtrl       => pgpRxCtrl,
            axilClk         => iAxiClk,
            axilRst         => iAxiRst,
            axilReadMaster  => locAxilReadMasters(AXIL_GTX_0_C),
            axilReadSlave   => locAxilReadSlaves(AXIL_GTX_0_C),
            axilWriteMaster => locAxilWriteMasters(AXIL_GTX_0_C),
            axilWriteSlave  => locAxilWriteSlaves(AXIL_GTX_0_C));
   end generate;

   ---------------------------------------------------------------------------
   -- PGP Status/Control Registers
   ---------------------------------------------------------------------------
   U_Pgp2bAxi_0 : entity surf.Pgp2bAxi
      generic map (
         TPD_G             => TPD_G,
         COMMON_TX_CLK_G   => false,
         COMMON_RX_CLK_G   => false,
         WRITE_EN_G        => true,
         AXI_CLK_FREQ_G    => 125.0E6,
         ERROR_CNT_WIDTH_G => 16)
      port map (
         pgpTxClk        => pgpClk,
         pgpTxClkRst     => pgpRst,
         pgpTxIn         => pgpTxIn,
         pgpTxOut        => pgpTxOut,
         locTxIn         => locPgpTxIn,
         pgpRxClk        => pgpClk,
         pgpRxClkRst     => pgpRst,
         pgpRxIn         => pgpRxIn,
         pgpRxOut        => pgpRxOut,
         axilClk         => iAxiClk,
         axilRst         => iAxiRst,
         axilReadMaster  => locAxilReadMasters(AXIL_PGP_0_C),
         axilReadSlave   => locAxilReadSlaves(AXIL_PGP_0_C),
         axilWriteMaster => locAxilWriteMasters(AXIL_PGP_0_C),
         axilWriteSlave  => locAxilWriteSlaves(AXIL_PGP_0_C));

   ---------------------------------------------------------------------------
   -- Ring Router (VC FIFOs + routing logic)
   ---------------------------------------------------------------------------
   U_PgpRingRouter : entity warm_tdm.PgpRingRouter
      generic map (
         TPD_G               => TPD_G,
         SIMULATION_G        => SIMULATION_G,
         RING_ADDR_0_G       => RING_ADDR_0_G,
         PACKET_SIZE_BYTES_G => PACKET_SIZE_BYTES_C)
      port map (
         axiClk         => iAxiClk,
         axiRst         => iAxiRst,
         pgpClk         => pgpClk,
         pgpRst         => pgpRst,
         pgpRxLinkReady => pgpRxOut.linkReady,
         pgpTxLinkReady => pgpTxOut.linkReady,
         pgpRxMasters   => pgpRxMasters,
         pgpRxCtrl      => pgpRxCtrl,
         pgpTxMasters   => pgpTxMasters,
         pgpTxSlaves    => pgpTxSlaves,
         remPause       => pgpRxOut.remPause,
         address        => address,
         appRxMasters   => appRxAxisMasters,
         appRxSlaves    => appRxAxisSlaves,
         appTxMasters   => appTxAxisMasters,
         appTxSlaves    => appTxAxisSlaves);

   ---------------------------------------------------------------------------
   -- Ethernet Stream Mux (bridges Ethernet traffic onto PGP VCs)
   ---------------------------------------------------------------------------
   ETH_STREAM_MUX : for i in 1 downto 0 generate
      U_AxiStreamDeMux_1 : entity surf.AxiStreamDeMux
         generic map (
            TPD_G          => TPD_G,
            NUM_MASTERS_G  => 2,
            MODE_G         => "ROUTED",
            TDEST_ROUTES_G => (0 => "0-------", 1 => "1-------"),
            PIPE_STAGES_G  => 0)
         port map (
            axisClk         => iAxiClk,
            axisRst         => iAxiRst,
            sAxisMaster     => appRxAxisMasters(i),
            sAxisSlave      => appRxAxisSlaves(i),
            mAxisMasters(0) => appLocalRxAxisMasters(i),
            mAxisMasters(1) => ethTxAxisMasters(i),
            mAxisSlaves(0)  => appLocalRxAxisSlaves(i),
            mAxisSlaves(1)  => ethTxAxisSlaves(i));

      U_AxiStreamMux_1 : entity surf.AxiStreamMux
         generic map (
            TPD_G                => TPD_G,
            PIPE_STAGES_G        => 0,
            NUM_SLAVES_G         => 2,
            MODE_G               => "ROUTED",
            TDEST_ROUTES_G       => (0 => "0-------", 1 => "1-------"),
            ILEAVE_EN_G          => true,
            ILEAVE_ON_NOTVALID_G => true,
            ILEAVE_REARB_G       => 31,
            REARB_DELAY_G        => true,
            FORCED_REARB_HOLD_G  => false)
         port map (
            axisClk         => iAxiClk,
            axisRst         => iAxiRst,
            sAxisMasters(0) => appLocalTxAxisMasters(i),
            sAxisMasters(1) => ethRxAxisMasters(i),
            sAxisSlaves(0)  => appLocalTxAxisSlaves(i),
            sAxisSlaves(1)  => ethRxAxisSlaves(i),
            mAxisMaster     => appTxAxisMasters(i),
            mAxisSlave      => appTxAxisSlaves(i));
   end generate;

   ---------------------------------------------------------------------------
   -- SRP (VC0)
   ---------------------------------------------------------------------------
   U_SrpV3AxiLite_1 : entity surf.SrpV3AxiLite
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         FIFO_ADDR_WIDTH_G   => 10,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => true,
         AXIL_CLK_FREQ_G     => 125.0E6,
         AXI_STREAM_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk         => iAxiClk,
         sAxisRst         => iAxiRst,
         sAxisMaster      => appLocalRxAxisMasters(VC_SRP_C),
         sAxisSlave       => appLocalRxAxisSlaves(VC_SRP_C),
         sAxisCtrl        => open,
         mAxisClk         => iAxiClk,
         mAxisRst         => iAxiRst,
         mAxisMaster      => appLocalTxAxisMasters(VC_SRP_C),
         mAxisSlave       => appLocalTxAxisSlaves(VC_SRP_C),
         axilClk          => iAxiClk,
         axilRst          => iAxiRst,
         mAxilWriteMaster => mAxilWriteMaster,
         mAxilWriteSlave  => mAxilWriteSlave,
         mAxilReadMaster  => mAxilReadMaster,
         mAxilReadSlave   => mAxilReadSlave);

   ---------------------------------------------------------------------------
   -- AXI-Lite Crossbar (for local register access)
   ---------------------------------------------------------------------------
   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C)
      port map (
         axiClk              => iAxiClk,
         axiClkRst           => iAxiRst,
         sAxiWriteMasters(0) => sAxilWriteMaster,
         sAxiWriteSlaves(0)  => sAxilWriteSlave,
         sAxiReadMasters(0)  => sAxilReadMaster,
         sAxiReadSlaves(0)   => sAxilReadSlave,
         mAxiWriteMasters    => locAxilWriteMasters,
         mAxiWriteSlaves     => locAxilWriteSlaves,
         mAxiReadMasters     => locAxilReadMasters,
         mAxiReadSlaves      => locAxilReadSlaves);

   ---------------------------------------------------------------------------
   -- VC Assignments
   ---------------------------------------------------------------------------
   appLocalTxAxisMasters(VC_DATA_C) <= dataTxAxisMaster;
   dataTxAxisSlave                  <= appLocalTxAxisSlaves(VC_DATA_C);
   appLocalRxAxisSlaves(VC_DATA_C)  <= dataRxAxisSlave;
   dataRxAxisMaster                 <= appLocalRxAxisMasters(VC_DATA_C);

   appLocalTxAxisMasters(VC_LOOPBACK_2_C) <= AXI_STREAM_MASTER_INIT_C;
   appLocalRxAxisSlaves(VC_LOOPBACK_2_C)  <= AXI_STREAM_SLAVE_FORCE_C;
   appLocalTxAxisMasters(VC_LOOPBACK_3_C) <= AXI_STREAM_MASTER_INIT_C;
   appLocalRxAxisSlaves(VC_LOOPBACK_3_C)  <= AXI_STREAM_SLAVE_FORCE_C;

end architecture rtl;
