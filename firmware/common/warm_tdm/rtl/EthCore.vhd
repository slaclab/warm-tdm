------------------------------------------------------------------------------
-- Title      :  EthCore
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Encapsulates ethernet stack, RSSI, SRP and IO buffers into a
-- single module.
-------------------------------------------------------------------------------
-- This file is part of 'KPIX'
-- It is subject to the license terms in the LICENSE.txt file found in the 
-- top-level directory of this distribution and at: 
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
-- No part of 'KPIX', including this file, 
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
use surf.SsiPkg.all;
use surf.EthMacPkg.all;

library unisim;
use unisim.vcomponents.all;

library warm_tdm;
use warm_tdm.WarmTdmPkg.all;

entity EthCore is
   generic (
      TPD_G               : time             := 1 ns;
      RING_ADDR_0_G       : boolean          := false;
      ETH_10G_G           : boolean          := false;
      SIMULATION_G        : boolean          := false;
      SIM_SRP_PORT_NUM_G  : integer          := 9000;
      SIM_DATA_PORT_NUM_G : integer          := 9000;
      AXIL_BASE_ADDR_G    : slv(31 downto 0) := X"00000000";
      AXIL_CLK_FREQ_G     : real             := 125.0E6;
      DHCP_G              : boolean          := false;        -- true = DHCP, false = static address
      IP_ADDR_G           : slv(31 downto 0) := x"0A01A8C0";  -- 192.168.1.10 (before DHCP)
      MAC_ADDR_G          : slv(47 downto 0) := x"00_00_16_56_00_08");
   port (
      extRst                : in  sl                    := '0';
      -- GT ports and clock
      gtRefClk              : in  sl;                         -- GT Ref Clock 156.25 MHz
      fabRefClk             : in  sl;
      gtRxP                 : in  sl;
      gtRxN                 : in  sl;
      gtTxP                 : out sl;
      gtTxN                 : out sl;
      -- Eth/RSSI Status
      phyReady              : out sl;
      rssiStatus            : out slv7Array(1 downto 0);
      -- AXI-Lite Interface for local register access
      axilClk               : in  sl;
      axilRst               : in  sl;
      mAxilReadMaster       : out AxiLiteReadMasterType;
      mAxilReadSlave        : in  AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      mAxilWriteMaster      : out AxiLiteWriteMasterType;
      mAxilWriteSlave       : in  AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      sAxilReadMaster       : in  AxiLiteReadMasterType;
      sAxilReadSlave        : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster      : in  AxiLiteWriteMasterType;
      sAxilWriteSlave       : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      -- IO Streams
      axisClk               : in  sl;
      axisRst               : in  sl;
      localDataRxAxisMaster : out AxiStreamMasterType;
      localDataRxAxisSlave  : in  AxiStreamSlaveType;
      localDataTxAxisMaster : in  AxiStreamMasterType;
      localDataTxAxisSlave  : out AxiStreamSlaveType;

      remoteRxAxisMasters : out AxiStreamMasterArray(3 downto 0);
      remoteRxAxisSlaves  : in  AxiStreamSlaveArray(3 downto 0);
      remoteTxAxisMasters : in  AxiStreamMasterArray(3 downto 0);
      remoteTxAxisSlaves  : out AxiStreamSlaveArray(3 downto 0));

end EthCore;

architecture rtl of EthCore is

   constant ETH_CLK_FREQ_C : real := ite(ETH_10G_G, 156.25E+6, 125.00E+6);

   constant SERVER_SIZE_C     : natural := 2;
   constant SRP_RSSI_INDEX_C  : natural := 0;
   constant DATA_RSSI_INDEX_C : natural := 1;
   constant SERVER_PORTS_C : PositiveArray(1 downto 0) := (
      SRP_RSSI_INDEX_C  => 8192,
      DATA_RSSI_INDEX_C => 8193);


   -- Both RSSI ports use the same TDEST and stream config
   constant RSSI_SIZE_C   : positive            := 4;
   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 8, tDestBits => 8, tUserBits => 8);

   constant RSSI_AXIS_CONFIG_C : AxiStreamConfigArray(RSSI_SIZE_C-1 downto 0) := (others => AXIS_CONFIG_C);

   -- Need to throttle down to simulate GigEth bandwidth
   constant ROGUE_AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 1, tDestBits => 8, tUserBits => 8);

   constant DEST_LOCAL_SRP_DATA_C  : integer := 0;
   constant DEST_LOCAL_LOOPBACK_C  : integer := 1;
   constant DEST_REMOTE_SRP_DATA_C : integer := 2;
   constant DEST_REMOTE_LOOPBACK_C : integer := 3;

   constant RSSI_ROUTES_C : Slv8Array(RSSI_SIZE_C-1 downto 0) := (
      DEST_LOCAL_SRP_DATA_C  => X"00",
      DEST_LOCAL_LOOPBACK_C  => X"10",
      DEST_REMOTE_SRP_DATA_C => "0000----",
      DEST_REMOTE_LOOPBACK_C => "0001----");

   constant RSSI_PRIORITY_C : IntegerArray(RSSI_SIZE_C-1 downto 0) := (
      DEST_LOCAL_SRP_DATA_C  => 1,
      DEST_LOCAL_LOOPBACK_C  => 0,
      DEST_REMOTE_SRP_DATA_C => 2,
      DEST_REMOTE_LOOPBACK_C => 0);


   constant AXIL_NUM_C       : integer := 4;
   constant AXIL_ETH_C       : integer := 0;
   constant AXIL_UDP_C       : integer := 1;
   constant AXIL_RSSI_SRP_C  : integer := 2;
   constant AXIL_RSSI_DATA_C : integer := 3;


   constant AXIL_XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(AXIL_NUM_C-1 downto 0) := (
      AXIL_ETH_C       => (
         baseAddr      => AXIL_BASE_ADDR_G + X"000000",
         addrBits      => 16,
         connectivity  => X"FFFF"),
      AXIL_UDP_C       => (
         baseAddr      => AXIL_BASE_ADDR_G + X"010000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_RSSI_SRP_C  => (
         baseAddr      => AXIL_BASE_ADDR_G + X"011000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_RSSI_DATA_C => (
         baseAddr      => AXIL_BASE_ADDR_G + X"012000",
         addrBits      => 12,
         connectivity  => X"FFFF"));


   signal refRst     : sl;
   signal ethClk     : sl;
   signal ethRst     : sl;
   signal ethClkDiv2 : sl;
   signal ethRstDiv2 : sl;

   signal efuse    : slv(31 downto 0);
   signal localMac : slv(47 downto 0);

   signal rxMaster : AxiStreamMasterType;
   signal rxSlave  : AxiStreamSlaveType;
   signal txMaster : AxiStreamMasterType;
   signal txSlave  : AxiStreamSlaveType;

   signal ibServerMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal ibServerSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);
   signal obServerMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal obServerSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);

   signal srpRssiIbMasters : AxiStreamMasterArray(RSSI_SIZE_C-1 downto 0);
   signal srpRssiIbSlaves  : AxiStreamSlaveArray(RSSI_SIZE_C-1 downto 0);
   signal srpRssiObMasters : AxiStreamMasterArray(RSSI_SIZE_C-1 downto 0);
   signal srpRssiObSlaves  : AxiStreamSlaveArray(RSSI_SIZE_C-1 downto 0);

   signal dataRssiIbMasters : AxiStreamMasterArray(RSSI_SIZE_C-1 downto 0);
   signal dataRssiIbSlaves  : AxiStreamSlaveArray(RSSI_SIZE_C-1 downto 0);
   signal dataRssiObMasters : AxiStreamMasterArray(RSSI_SIZE_C-1 downto 0);
   signal dataRssiObSlaves  : AxiStreamSlaveArray(RSSI_SIZE_C-1 downto 0);

   signal fifoRemoteRxAxisMasters : AxiStreamMasterArray(3 downto 0);
   signal fifoRemoteRxAxisSlaves  : AxiStreamSlaveArray(3 downto 0);
   signal fifoRemoteTxAxisMasters : AxiStreamMasterArray(3 downto 0);
   signal fifoRemoteTxAxisSlaves  : AxiStreamSlaveArray(3 downto 0);

   constant CHAN_MASK_C  : slv(7 downto 0)                                := "00010111";
   signal rogueIbMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal rogueIbSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal rogueObMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal rogueObSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal rogueDemuxAxisMasters : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal rogueDemuxAxisSlaves  : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);
   signal rogueMuxAxisMasters   : AxiStreamMasterArray(SERVER_SIZE_C-1 downto 0);
   signal rogueMuxAxisSlaves    : AxiStreamSlaveArray(SERVER_SIZE_C-1 downto 0);

   signal syncAxilReadMaster  : AxiLiteReadMasterType;
   signal syncAxilReadSlave   : AxiLiteReadSlaveType;
   signal syncAxilWriteMaster : AxiLiteWriteMasterType;
   signal syncAxilWriteSlave  : AxiLiteWriteSlaveType;

   signal locAxilReadMasters  : AxiLiteReadMasterArray(AXIL_NUM_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(AXIL_NUM_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);
   signal locAxilWriteMasters : AxiLiteWriteMasterArray(AXIL_NUM_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(AXIL_NUM_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

   signal qplllock      : sl;
   signal qplloutclk    : sl;
   signal qplloutrefclk : sl;
   signal qpllReset     : sl;


begin



   --------------------
   -- Local MAC Address
   --------------------
--    U_EFuse : EFUSE_USR
--       port map (
--          EFUSEUSR => efuse);

--    localMac(23 downto 0)  <= x"56_00_08";  -- 08:00:56:XX:XX:XX (big endian SLV)   
--    localMac(47 downto 24) <= efuse(31 downto 8);

   localMac(47 downto 0) <= MAC_ADDR_G;  --x"00_00_16_56_00_08";

   -- UdpEngineWrapper needs AXIL on eth clock so just sync everything
   U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G => TPD_G)
      port map (
         sAxiClk         => axilClk,              -- [in]
         sAxiClkRst      => axilRst,              -- [in]
         sAxiReadMaster  => sAxilReadMaster,      -- [in]
         sAxiReadSlave   => sAxilReadSlave,       -- [out]
         sAxiWriteMaster => sAxilWriteMaster,     -- [in]
         sAxiWriteSlave  => sAxilWriteSlave,      -- [out]
         mAxiClk         => ethClk,               -- [in]
         mAxiClkRst      => ethRst,               -- [in]
         mAxiReadMaster  => syncAxilReadMaster,   -- [out]
         mAxiReadSlave   => syncAxilReadSlave,    -- [in]
         mAxiWriteMaster => syncAxilWriteMaster,  -- [out]
         mAxiWriteSlave  => syncAxilWriteSlave);  -- [in]


   -- Check which clock is expected 
   U_XBAR : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => AXIL_NUM_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CONFIG_C)
      port map (
         axiClk              => ethClk,
         axiClkRst           => ethRst,
         sAxiWriteMasters(0) => syncAxilWriteMaster,
         sAxiWriteSlaves(0)  => syncAxilWriteSlave,
         sAxiReadMasters(0)  => syncAxilReadMaster,
         sAxiReadSlaves(0)   => syncAxilReadSlave,
         mAxiWriteMasters    => locAxilWriteMasters,
         mAxiWriteSlaves     => locAxilWriteSlaves,
         mAxiReadMasters     => locAxilReadMasters,
         mAxiReadSlaves      => locAxilReadSlaves);


   REAL_ETH_GEN : if (not SIMULATION_G) generate

      GIG_ETH_GEN : if (not ETH_10G_G) generate

         PwrUpRst_Inst : entity surf.PwrUpRst
            generic map (
               TPD_G => TPD_G)
            port map (
               arst   => extRst,
               clk    => fabRefClk,
               rstOut => refRst);

         ----------------
         -- Clock Manager
         ----------------
         U_MMCM : entity surf.ClockManager7
            generic map(
               TPD_G              => TPD_G,
               TYPE_G             => "MMCM",
               INPUT_BUFG_G       => false,
               FB_BUFG_G          => true,  -- Without this, will never lock in simulation
               RST_IN_POLARITY_G  => '1',
               NUM_CLOCKS_G       => 2,
               -- MMCM attributes
               BANDWIDTH_G        => "OPTIMIZED",
               CLKIN_PERIOD_G     => 8.0,   -- 250 MHz
               DIVCLK_DIVIDE_G    => 1,     -- 250 MHz = 156.25 MHz/5
               CLKFBOUT_MULT_F_G  => 8.0,   -- 1.0GHz = 250 MHz * 4
               CLKOUT0_DIVIDE_F_G => 8.0,   -- 125 MHz = 1.0GHz/8
               CLKOUT1_DIVIDE_G   => 16)    -- 62.5 MHz = 1.0GHz/16
            port map(
               clkIn     => fabRefClk,
               rstIn     => refRst,
               clkOut(0) => ethClk,
               clkOut(1) => ethClkDiv2,
               rstOut(0) => ethRst,
               rstOut(1) => ethRstDiv2,
               locked    => open);

         -------------------------
         -- GigE Core for KINTEX-7
         -------------------------
         U_ETH_PHY_MAC : entity surf.GigEthGtx7
            generic map (
               TPD_G                   => TPD_G,
               EN_AXI_REG_G            => true,
               AXIL_BASE_ADDR_G        => AXIL_XBAR_CONFIG_C(AXIL_ETH_C).baseAddr,
               AXIL_CLK_IS_SYSCLK125_G => true,
               AXIS_CONFIG_G           => EMAC_AXIS_CONFIG_C)
            port map (
               -- Local Configurations
               localMac           => localMac,
               -- Streaming DMA Interface 
               dmaClk             => ethClk,
               dmaRst             => ethRst,
               dmaIbMaster        => rxMaster,
               dmaIbSlave         => rxSlave,
               dmaObMaster        => txMaster,
               dmaObSlave         => txSlave,
               -- AXI Lite debug interface
               axiLiteClk         => ethClk,
               axiLiteRst         => ethRst,
               axiLiteReadMaster  => locAxilReadMasters(AXIL_ETH_C),
               axiLiteReadSlave   => locAxilReadSlaves(AXIL_ETH_C),
               axiLiteWriteMaster => locAxilWriteMasters(AXIL_ETH_C),
               axiLiteWriteSlave  => locAxilWriteSlaves(AXIL_ETH_C),
               -- PHY + MAC signals
               sysClk62           => ethClkDiv2,
               sysClk125          => ethClk,
               sysRst125          => ethRst,
               extRst             => refRst,  -- Check this
               phyReady           => phyReady,
               -- MGT Ports
               gtTxP              => gtTxP,
               gtTxN              => gtTxN,
               gtRxP              => gtRxP,
               gtRxN              => gtRxN);
      end generate GIG_ETH_GEN;

      TEN_GIG_ETH_GEN : if (ETH_10G_G) generate
         ethClk <= fabRefClk;

         PwrUpRst_Inst : entity surf.PwrUpRst
            generic map (
               TPD_G => TPD_G)
            port map (
               arst   => extRst,
               clk    => ethClk,
               rstOut => ethRst);

         Gtx7QuadPll_Inst : entity surf.Gtx7QuadPll
            generic map (
               TPD_G               => TPD_G,
               SIM_RESET_SPEEDUP_G => "TRUE",        --Does not affect hardware
               SIM_VERSION_G       => "4.0",
               QPLL_CFG_G          => x"0680181",
               QPLL_REFCLK_SEL_G   => "001",
               QPLL_FBDIV_G        => "0101000000",  -- 64B/66B Encoding
               QPLL_FBDIV_RATIO_G  => '0',           -- 64B/66B Encoding
               QPLL_REFCLK_DIV_G   => 1)
            port map (
               qPllRefClk     => gtRefClk,           -- 156.25 MHz
               qPllOutClk     => qPllOutClk,
               qPllOutRefClk  => qPllOutRefClk,
               qPllLock       => qPllLock,
               qPllLockDetClk => '0',                -- IP Core ties this to GND (see note below)
               qPllRefClkLost => open,
               qPllPowerDown  => '0',
               qPllReset      => qpllReset);

         U_TenGigEthGtx7_1 : entity surf.TenGigEthGtx7
            generic map (
               TPD_G         => TPD_G,
               PAUSE_EN_G    => true,
               EN_AXI_REG_G  => true,
               AXIS_CONFIG_G => EMAC_AXIS_CONFIG_C)
            port map (
               localMac           => localMac,                         -- [in]
               dmaClk             => ethClk,                           -- [in]
               dmaRst             => ethRst,                           -- [in]
               dmaIbMaster        => rxMaster,                         -- [out]
               dmaIbSlave         => rxSlave,                          -- [in]
               dmaObMaster        => txMaster,                         -- [in]
               dmaObSlave         => txSlave,                          -- [out]
               axiLiteClk         => ethClk,                           -- [in]
               axiLiteRst         => ethRst,                           -- [in]
               axiLiteReadMaster  => locAxilReadMasters(AXIL_ETH_C),   -- [in]
               axiLiteReadSlave   => locAxilReadSlaves(AXIL_ETH_C),    -- [out]
               axiLiteWriteMaster => locAxilWriteMasters(AXIL_ETH_C),  -- [in]
               axiLiteWriteSlave  => locAxilWriteSlaves(AXIL_ETH_C),   -- [out]
--                sigDet             => sigDet,              -- [in]
--                txFault            => txFault,             -- [in]
--               txDisable          => txDisable,           -- [out]
               extRst             => extRst,                           -- [in]
               phyClk             => ethClk,                           -- [in]
               phyRst             => ethRst,                           -- [in]
               phyReady           => phyReady,                         -- [out]
--                gtTxPreCursor      => gtTxPreCursor,       -- [in]
--                gtTxPostCursor     => gtTxPostCursor,      -- [in]
--                gtTxDiffCtrl       => gtTxDiffCtrl,        -- [in]
--                gtRxPolarity       => gtRxPolarity,        -- [in]
--                gtTxPolarity       => gtTxPolarity,        -- [in]
               qplllock           => qpllLock,                         -- [in]
               qplloutclk         => qpllOutClk,                       -- [in]
               qplloutrefclk      => qpllOutRefClk,                    -- [in]
               qpllRst            => qpllReset,                        -- [out]
               gtTxP              => gtTxP,                            -- [out]
               gtTxN              => gtTxN,                            -- [out]
               gtRxP              => gtRxP,                            -- [in]
               gtRxN              => gtRxN);                           -- [in]


      end generate TEN_GIG_ETH_GEN;

      ----------------------
      -- IPv4/ARP/UDP Engine
      ----------------------
      U_UDP : entity surf.UdpEngineWrapper
         generic map (
            -- Simulation Generics
            TPD_G          => TPD_G,
            -- UDP Server Generics
            SERVER_EN_G    => true,
            SERVER_SIZE_G  => SERVER_SIZE_C,
            SERVER_PORTS_G => SERVER_PORTS_C,
            -- UDP Client Generics
            CLIENT_EN_G    => false,
            -- General IPv4/ARP/DHCP Generics
            DHCP_G         => DHCP_G,
            CLK_FREQ_G     => ETH_CLK_FREQ_C,
            COMM_TIMEOUT_G => 30)
         port map (
            -- Local Configurations
            localMac        => localMac,
            localIp         => IP_ADDR_G,
            -- Interface to Ethernet Media Access Controller (MAC)
            obMacMaster     => rxMaster,
            obMacSlave      => rxSlave,
            ibMacMaster     => txMaster,
            ibMacSlave      => txSlave,
            -- Interface to UDP Server engine(s)
            obServerMasters => obServerMasters,
            obServerSlaves  => obServerSlaves,
            ibServerMasters => ibServerMasters,
            ibServerSlaves  => ibServerSlaves,
            -- AXI Lite debug interface
            axilReadMaster  => locAxilReadMasters(AXIL_UDP_C),
            axilReadSlave   => locAxilReadSlaves(AXIL_UDP_C),
            axilWriteMaster => locAxilWriteMasters(AXIL_UDP_C),
            axilWriteSlave  => locAxilWriteSlaves(AXIL_UDP_C),
            -- Clock and Reset
            clk             => ethClk,
            rst             => ethRst);

      ------------------------------------------
      -- Software's RSSI Server Interface @ 8192
      ------------------------------------------
      U_RssiServer_SRP : entity surf.RssiCoreWrapper
         generic map (
            TPD_G                 => TPD_G,
            APP_ILEAVE_EN_G       => true,
            ILEAVE_ON_NOTVALID_G  => true,
            MAX_SEG_SIZE_G        => 1024,
            SEGMENT_ADDR_SIZE_G   => 7,
            APP_STREAMS_G         => RSSI_SIZE_C,
            APP_STREAM_ROUTES_G   => RSSI_ROUTES_C,
            APP_STREAM_PRIORITY_G => RSSI_PRIORITY_C,
            APP_AXIS_CONFIG_G     => RSSI_AXIS_CONFIG_C,
            CLK_FREQUENCY_G       => ETH_CLK_FREQ_C,
            TIMEOUT_UNIT_G        => 1.0E-3,  -- In units of seconds
            SERVER_G              => true,
            RETRANSMIT_ENABLE_G   => true,
            BYPASS_CHUNKER_G      => false,
            WINDOW_ADDR_SIZE_G    => 3,
            PIPE_STAGES_G         => 0,
            TSP_AXIS_CONFIG_G     => EMAC_AXIS_CONFIG_C,
            INIT_SEQ_N_G          => 16#80#)
         port map (
            clk_i             => ethClk,
            rst_i             => ethRst,
            openRq_i          => '1',
            -- Application Layer Interface
            sAppAxisMasters_i => srpRssiIbMasters,
            sAppAxisSlaves_o  => srpRssiIbSlaves,
            mAppAxisMasters_o => srpRssiObMasters,
            mAppAxisSlaves_i  => srpRssiObSlaves,
            -- Transport Layer Interface
            sTspAxisMaster_i  => obServerMasters(SRP_RSSI_INDEX_C),
            sTspAxisSlave_o   => obServerSlaves(SRP_RSSI_INDEX_C),
            mTspAxisMaster_o  => ibServerMasters(SRP_RSSI_INDEX_C),
            mTspAxisSlave_i   => ibServerSlaves(SRP_RSSI_INDEX_C),
            -- AXI-Lite Interface
            axiClk_i          => ethClk,
            axiRst_i          => ethRst,
            axilReadMaster    => locAxilReadMasters(AXIL_RSSI_SRP_C),
            axilReadSlave     => locAxilReadSlaves(AXIL_RSSI_SRP_C),
            axilWriteMaster   => locAxilWriteMasters(AXIL_RSSI_SRP_C),
            axilWriteSlave    => locAxilWriteSlaves(AXIL_RSSI_SRP_C),
            -- Internal statuses
            statusReg_o       => rssiStatus(SRP_RSSI_INDEX_C));

      U_RssiServer_DATA : entity surf.RssiCoreWrapper
         generic map (
            TPD_G                 => TPD_G,
            APP_ILEAVE_EN_G       => true,
            ILEAVE_ON_NOTVALID_G  => true,
            MAX_SEG_SIZE_G        => 1024,
            SEGMENT_ADDR_SIZE_G   => 7,
            APP_STREAMS_G         => RSSI_SIZE_C,
            APP_STREAM_ROUTES_G   => RSSI_ROUTES_C,
            APP_STREAM_PRIORITY_G => RSSI_PRIORITY_C,
            APP_AXIS_CONFIG_G     => RSSI_AXIS_CONFIG_C,
            CLK_FREQUENCY_G       => ETH_CLK_FREQ_C,
            TIMEOUT_UNIT_G        => 1.0E-3,  -- In units of seconds
            SERVER_G              => true,
            RETRANSMIT_ENABLE_G   => true,
            BYPASS_CHUNKER_G      => false,
            WINDOW_ADDR_SIZE_G    => 3,
            PIPE_STAGES_G         => 0,
            TSP_AXIS_CONFIG_G     => EMAC_AXIS_CONFIG_C,
            INIT_SEQ_N_G          => 16#80#)
         port map (
            clk_i             => ethClk,
            rst_i             => ethRst,
            openRq_i          => '1',
            -- Application Layer Interface
            sAppAxisMasters_i => dataRssiIbMasters,
            sAppAxisSlaves_o  => dataRssiIbSlaves,
            mAppAxisMasters_o => dataRssiObMasters,
            mAppAxisSlaves_i  => dataRssiObSlaves,
            -- Transport Layer Interface
            sTspAxisMaster_i  => obServerMasters(DATA_RSSI_INDEX_C),
            sTspAxisSlave_o   => obServerSlaves(DATA_RSSI_INDEX_C),
            mTspAxisMaster_o  => ibServerMasters(DATA_RSSI_INDEX_C),
            mTspAxisSlave_i   => ibServerSlaves(DATA_RSSI_INDEX_C),
            -- AXI-Lite Interface
            axiClk_i          => ethClk,
            axiRst_i          => ethRst,
            axilReadMaster    => locAxilReadMasters(AXIL_RSSI_DATA_C),
            axilReadSlave     => locAxilReadSlaves(AXIL_RSSI_DATA_C),
            axilWriteMaster   => locAxilWriteMasters(AXIL_RSSI_DATA_C),
            axilWriteSlave    => locAxilWriteSlaves(AXIL_RSSI_DATA_C),
            -- Internal statuses
            statusReg_o       => rssiStatus(DATA_RSSI_INDEX_C));


   end generate REAL_ETH_GEN;

   SIM_GEN : if (SIMULATION_G and RING_ADDR_0_G) generate
      ethClk <= fabRefClk;

      PwrUpRst_Inst : entity surf.PwrUpRst
         generic map (
            TPD_G         => TPD_G,
            SIM_SPEEDUP_G => true)
         port map (
            arst   => extRst,
            clk    => ethClk,
            rstOut => ethRst);

      -- SRP
      U_RogueTcpStreamWrap_SRP : entity surf.RogueTcpStreamWrap
         generic map (
            TPD_G         => TPD_G,
            PORT_NUM_G    => SIM_SRP_PORT_NUM_G,
            SSI_EN_G      => true,
            CHAN_COUNT_G  => 0,
            CHAN_MASK_G   => CHAN_MASK_C,
            AXIS_CONFIG_G => ROGUE_AXIS_CONFIG_C)
         port map (
            axisClk     => ethClk,                            -- [in]
            axisRst     => ethRst,                            -- [in]
            sAxisMaster => rogueIbMasters(SRP_RSSI_INDEX_C),  -- [in]
            sAxisSlave  => rogueIbSlaves(SRP_RSSI_INDEX_C),   -- [out]
            mAxisMaster => rogueObMasters(SRP_RSSI_INDEX_C),  -- [out]
            mAxisSlave  => rogueObSlaves(SRP_RSSI_INDEX_C));  -- [in]

      U_AxiStreamResize_SRP_RX : entity surf.AxiStreamResize
         generic map (
            TPD_G               => TPD_G,
            SLAVE_AXI_CONFIG_G  => ROGUE_AXIS_CONFIG_C,
            MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
         port map (
            axisClk     => ethClk,                                   -- [in]
            axisRst     => ethRst,                                   -- [in]
            sAxisMaster => rogueObMasters(SRP_RSSI_INDEX_C),         -- [in]
            sAxisSlave  => rogueObSlaves(SRP_RSSI_INDEX_C),          -- [out]
            mAxisMaster => rogueDemuxAxisMasters(SRP_RSSI_INDEX_C),  -- [out]
            mAxisSlave  => rogueDemuxAxisSlaves(SRP_RSSI_INDEX_C));  -- [in]

      U_AxiStreamResize_SRP_TX : entity surf.AxiStreamResize
         generic map (
            TPD_G               => TPD_G,
            SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
            MASTER_AXI_CONFIG_G => ROGUE_AXIS_CONFIG_C)
         port map (
            axisClk     => ethClk,                                 -- [in]
            axisRst     => ethRst,                                 -- [in]
            sAxisMaster => rogueMuxAxisMasters(SRP_RSSI_INDEX_C),  -- [in]
            sAxisSlave  => rogueMuxAxisSlaves(SRP_RSSI_INDEX_C),   -- [out]
            mAxisMaster => rogueIbMasters(SRP_RSSI_INDEX_C),       -- [out]
            mAxisSlave  => rogueIbSlaves(SRP_RSSI_INDEX_C));       -- [in]


      U_AxiStreamDeMux_SRP : entity surf.AxiStreamDeMux
         generic map (
            TPD_G          => TPD_G,
            NUM_MASTERS_G  => RSSI_ROUTES_C'length,
            MODE_G         => "ROUTED",
            TDEST_ROUTES_G => RSSI_ROUTES_C)
         port map (
            axisClk      => ethClk,                                   -- [in]
            axisRst      => ethRst,                                   -- [in]
            sAxisMaster  => rogueDemuxAxisMasters(SRP_RSSI_INDEX_C),  -- [in]
            sAxisSlave   => rogueDemuxAxisSlaves(SRP_RSSI_INDEX_C),   -- [out]
            mAxisMasters => srpRssiObMasters,                         -- [out]
            mAxisSlaves  => srpRssiObSlaves);                         -- [in]

      U_AxiStreamMux_SRP : entity surf.AxiStreamMux
         generic map (
            TPD_G                => TPD_G,
            NUM_SLAVES_G         => RSSI_ROUTES_C'length,
            MODE_G               => "ROUTED",
            TDEST_ROUTES_G       => RSSI_ROUTES_C,
            PRIORITY_G           => RSSI_PRIORITY_C,
            ILEAVE_EN_G          => true,
            ILEAVE_ON_NOTVALID_G => true,
            ILEAVE_REARB_G       => (512/8)-3)
         port map (
            axisClk      => ethClk,                                 -- [in]
            axisRst      => ethRst,                                 -- [in]
            sAxisMasters => srpRssiIbMasters,                       -- [in]
            sAxisSlaves  => srpRssiIbSlaves,                        -- [out]
            mAxisMaster  => rogueMuxAxisMasters(SRP_RSSI_INDEX_C),  -- [out]
            mAxisSlave   => rogueMuxAxisSlaves(SRP_RSSI_INDEX_C));  -- [in]

      -- Data
      U_RogueTcpStreamWrap_DATA : entity surf.RogueTcpStreamWrap
         generic map (
            TPD_G         => TPD_G,
            PORT_NUM_G    => SIM_DATA_PORT_NUM_G,
            SSI_EN_G      => true,
            CHAN_MASK_G   => CHAN_MASK_C,
            AXIS_CONFIG_G => ROGUE_AXIS_CONFIG_C)
         port map (
            axisClk     => ethClk,                             -- [in]
            axisRst     => ethRst,                             -- [in]
            sAxisMaster => rogueIbMasters(DATA_RSSI_INDEX_C),  -- [in]
            sAxisSlave  => rogueIbSlaves(DATA_RSSI_INDEX_C),   -- [out]
            mAxisMaster => rogueObMasters(DATA_RSSI_INDEX_C),  -- [out]
            mAxisSlave  => rogueObSlaves(DATA_RSSI_INDEX_C));  -- [in]

      U_AxiStreamResize_DATA_RX : entity surf.AxiStreamResize
         generic map (
            TPD_G               => TPD_G,
            SLAVE_AXI_CONFIG_G  => ROGUE_AXIS_CONFIG_C,
            MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
         port map (
            axisClk     => ethClk,                                    -- [in]
            axisRst     => ethRst,                                    -- [in]
            sAxisMaster => rogueObMasters(DATA_RSSI_INDEX_C),         -- [in]
            sAxisSlave  => rogueObSlaves(DATA_RSSI_INDEX_C),          -- [out]
            mAxisMaster => rogueDemuxAxisMasters(DATA_RSSI_INDEX_C),  -- [out]
            mAxisSlave  => rogueDemuxAxisSlaves(DATA_RSSI_INDEX_C));  -- [in]

      U_AxiStreamResize_DATA_TX : entity surf.AxiStreamResize
         generic map (
            TPD_G               => TPD_G,
            SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
            MASTER_AXI_CONFIG_G => ROGUE_AXIS_CONFIG_C)
         port map (
            axisClk     => ethClk,                                  -- [in]
            axisRst     => ethRst,                                  -- [in]
            sAxisMaster => rogueMuxAxisMasters(DATA_RSSI_INDEX_C),  -- [in]
            sAxisSlave  => rogueMuxAxisSlaves(DATA_RSSI_INDEX_C),   -- [out]
            mAxisMaster => rogueIbMasters(DATA_RSSI_INDEX_C),       -- [out]
            mAxisSlave  => rogueIbSlaves(DATA_RSSI_INDEX_C));       -- [in]


      U_AxiStreamDeMux_DATA : entity surf.AxiStreamDeMux
         generic map (
            TPD_G          => TPD_G,
            NUM_MASTERS_G  => RSSI_ROUTES_C'length,
            MODE_G         => "ROUTED",
            TDEST_ROUTES_G => RSSI_ROUTES_C)
         port map (
            axisClk      => ethClk,                                    -- [in]
            axisRst      => ethRst,                                    -- [in]
            sAxisMaster  => rogueDemuxAxisMasters(DATA_RSSI_INDEX_C),  -- [in]
            sAxisSlave   => rogueDemuxAxisSlaves(DATA_RSSI_INDEX_C),   -- [out]
            mAxisMasters => dataRssiObMasters,                         -- [out]
            mAxisSlaves  => dataRssiObSlaves);                         -- [in]

      U_AxiStreamMux_DATA : entity surf.AxiStreamMux
         generic map (
            TPD_G                => TPD_G,
            NUM_SLAVES_G         => RSSI_ROUTES_C'length,
            MODE_G               => "ROUTED",
            TDEST_ROUTES_G       => RSSI_ROUTES_C,
            PRIORITY_G           => RSSI_PRIORITY_C,
            ILEAVE_EN_G          => true,
            ILEAVE_ON_NOTVALID_G => true,
            ILEAVE_REARB_G       => (512/8)-3)
         port map (
            axisClk      => ethClk,                                  -- [in]
            axisRst      => ethRst,                                  -- [in]
            sAxisMasters => dataRssiIbMasters,                       -- [in]
            sAxisSlaves  => dataRssiIbSlaves,                        -- [out]
            mAxisMaster  => rogueMuxAxisMasters(DATA_RSSI_INDEX_C),  -- [out]
            mAxisSlave   => rogueMuxAxisSlaves(DATA_RSSI_INDEX_C));  -- [in]      

   end generate SIM_GEN;

   ---------------------------------------
   -- SRP RSSI TDEST = 0x00 - Local register access control   
   ---------------------------------------
   U_SRPv3 : entity surf.SrpV3AxiLite
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => false,
         AXIL_CLK_FREQ_G     => AXIL_CLK_FREQ_G,
         AXI_STREAM_CONFIG_G => AXIS_CONFIG_C)
      port map (
         -- Streaming Slave (Rx) Interface (sAxisClk domain) 
         sAxisClk         => ethClk,
         sAxisRst         => ethRst,
         sAxisMaster      => srpRssiObMasters(DEST_LOCAL_SRP_DATA_C),
         sAxisSlave       => srpRssiObSlaves(DEST_LOCAL_SRP_DATA_C),
         -- Streaming Master (Tx) Data Interface (mAxisClk domain)
         mAxisClk         => ethClk,
         mAxisRst         => ethRst,
         mAxisMaster      => srpRssiIbMasters(DEST_LOCAL_SRP_DATA_C),
         mAxisSlave       => srpRssiIbSlaves(DEST_LOCAL_SRP_DATA_C),
         -- AXI Lite Bus (axilClk domain)
         axilClk          => axilClk,
         axilRst          => axilRst,
         mAxilReadMaster  => mAxilReadMaster,
         mAxilReadSlave   => mAxilReadSlave,
         mAxilWriteMaster => mAxilWriteMaster,
         mAxilWriteSlave  => mAxilWriteSlave);

   -----------------------------------------------------
   -- DATA RSSI TDEST 0x00 - Local Streaming Data TX buffer
   -- For clock transition
   -----------------------------------------------------
   U_AxiStreamFifoV2_LOC_TX : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "distributed",
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 6,
         FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**9-32,
         SLAVE_AXI_CONFIG_G  => DATA_AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk    => axisClk,                                   -- [in]
         sAxisRst    => axisRst,                                   -- [in]
         sAxisMaster => localDataTxAxisMaster,                     -- [in]
         sAxisSlave  => localDataTxAxisSlave,                      -- [out]
--         sAxisCtrl   => localTxAxisCtrl,                   -- [out]
         mAxisClk    => ethClk,                                    -- [in]
         mAxisRst    => ethRst,                                    -- [in]
         mAxisMaster => dataRssiIbMasters(DEST_LOCAL_SRP_DATA_C),  -- [out]
         mAxisSlave  => dataRssiIbSlaves(DEST_LOCAL_SRP_DATA_C));  -- [in]

   -- Could get rid of this fifo and just drop incomming data
   U_AxiStreamFifoV2_LOC_RX : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "distributed",
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 6,
         FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => DATA_AXIS_CONFIG_C)
      port map (
         sAxisClk    => ethClk,                                    -- [in]
         sAxisRst    => ethRst,                                    -- [in]
         sAxisMaster => dataRssiObMasters(DEST_LOCAL_SRP_DATA_C),  -- [in]
         sAxisSlave  => dataRssiObSlaves(DEST_LOCAL_SRP_DATA_C),   -- [out]
         mAxisClk    => axisClk,                                   -- [in]
         mAxisRst    => axisRst,                                   -- [in]
         mAxisMaster => localDataRxAxisMaster,                     -- [out]
         mAxisSlave  => localDataRxAxisSlave);                     -- [in]



   -------------------------------------------------------------------------------------------------
   -- SRP TDEST 0x10 - Local Loopback
   -------------------------------------------------------------------------------------------------
   U_AxiStreamFifoV2_SRP_LOOPBACK : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 9,
         FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk    => ethClk,                                   -- [in]
         sAxisRst    => ethRst,                                   -- [in]
         sAxisMaster => srpRssiObMasters(DEST_LOCAL_LOOPBACK_C),  -- [in]
         sAxisSlave  => srpRssiObSlaves(DEST_LOCAL_LOOPBACK_C),   -- [out]
         mAxisClk    => ethClk,                                   -- [in]
         mAxisRst    => ethRst,                                   -- [in]
         mAxisMaster => srpRssiIbMasters(DEST_LOCAL_LOOPBACK_C),  -- [out]
         mAxisSlave  => srpRssiIbSlaves(DEST_LOCAL_LOOPBACK_C));  -- [in]

   -------------------------------------------------------------------------------------------------
   -- DATA TDEST 0x10 - Local Loopback
   -------------------------------------------------------------------------------------------------
   U_AxiStreamFifoV2_DATA_LOOPBACK : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 9,
         FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
      port map (
         sAxisClk    => ethClk,                                    -- [in]
         sAxisRst    => ethRst,                                    -- [in]
         sAxisMaster => dataRssiObMasters(DEST_LOCAL_LOOPBACK_C),  -- [in]
         sAxisSlave  => dataRssiObSlaves(DEST_LOCAL_LOOPBACK_C),   -- [out]
         mAxisClk    => ethClk,                                    -- [in]
         mAxisRst    => ethRst,                                    -- [in]
         mAxisMaster => dataRssiIbMasters(DEST_LOCAL_LOOPBACK_C),  -- [out]
         mAxisSlave  => dataRssiIbSlaves(DEST_LOCAL_LOOPBACK_C));  -- [in]


   -------------------------------
   -- REMOTE channels
   -- Use fifos to transition to axi clock
   -------------------------------
   fifoRemoteRxAxisMasters(0) <= srpRssiObMasters(DEST_REMOTE_SRP_DATA_C);
   fifoRemoteRxAxisMasters(1) <= dataRssiObMasters(DEST_REMOTE_SRP_DATA_C);
   fifoRemoteRxAxisMasters(2) <= srpRssiObMasters(DEST_REMOTE_LOOPBACK_C);
   fifoRemoteRxAxisMasters(3) <= dataRssiObMasters(DEST_REMOTE_LOOPBACK_C);

   srpRssiObSlaves(DEST_REMOTE_SRP_DATA_C)  <= fifoRemoteRxAxisSlaves(0);
   dataRssiObSlaves(DEST_REMOTE_SRP_DATA_C) <= fifoRemoteRxAxisSlaves(1);
   srpRssiObSlaves(DEST_REMOTE_LOOPBACK_C)  <= fifoRemoteRxAxisSlaves(2);
   dataRssiObSlaves(DEST_REMOTE_LOOPBACK_C) <= fifoRemoteRxAxisSlaves(3);

   srpRssiIbMasters(DEST_REMOTE_SRP_DATA_C)  <= fifoRemoteTxAxisMasters(0);
   dataRssiIbMasters(DEST_REMOTE_SRP_DATA_C) <= fifoRemoteTxAxisMasters(1);
   srpRssiIbMasters(DEST_REMOTE_LOOPBACK_C)  <= fifoRemoteTxAxisMasters(2);
   dataRssiIbMasters(DEST_REMOTE_LOOPBACK_C) <= fifoRemoteTxAxisMasters(3);

   fifoRemoteTxAxisSlaves(0) <= srpRssiIbSlaves(DEST_REMOTE_SRP_DATA_C);
   fifoRemoteTxAxisSlaves(1) <= dataRssiIbSlaves(DEST_REMOTE_SRP_DATA_C);
   fifoRemoteTxAxisSlaves(2) <= srpRssiIbSlaves(DEST_REMOTE_LOOPBACK_C);
   fifoRemoteTxAxisSlaves(3) <= dataRssiIbSlaves(DEST_REMOTE_LOOPBACK_C);

   GEN_REMOTE_FIFOS : for i in 3 downto 0 generate
      U_AxiStreamFifoV2_REMOTE_RX : entity surf.AxiStreamFifoV2
         generic map (
            TPD_G               => TPD_G,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 0,
            SLAVE_READY_EN_G    => true,
            VALID_THOLD_G       => 1,
            VALID_BURST_MODE_G  => false,
            SYNTH_MODE_G        => "inferred",
            MEMORY_TYPE_G       => "distributed",
            GEN_SYNC_FIFO_G     => false,
            FIFO_ADDR_WIDTH_G   => 5,
            FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
            SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
            MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
         port map (
            sAxisClk    => ethClk,                      -- [in]
            sAxisRst    => ethRst,                      -- [in]
            sAxisMaster => fifoRemoteRxAxisMasters(i),  -- [in]
            sAxisSlave  => fifoRemoteRxAxisSlaves(i),   -- [out]
            mAxisClk    => axisClk,                     -- [in]
            mAxisRst    => axisRst,                     -- [in]
            mAxisMaster => remoteRxAxisMasters(i),      -- [out]
            mAxisSlave  => remoteRxAxisSlaves(i));      -- [in]

      U_AxiStreamFifoV2_REMOTE_TX : entity surf.AxiStreamFifoV2
         generic map (
            TPD_G               => TPD_G,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 0,
            SLAVE_READY_EN_G    => true,
            VALID_THOLD_G       => 1,
            VALID_BURST_MODE_G  => false,
            SYNTH_MODE_G        => "inferred",
            MEMORY_TYPE_G       => "distributed",
            GEN_SYNC_FIFO_G     => false,
            FIFO_ADDR_WIDTH_G   => 5,
            FIFO_FIXED_THRESH_G => true,
--         FIFO_PAUSE_THRESH_G => 2**12-32,
            SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_C,
            MASTER_AXI_CONFIG_G => AXIS_CONFIG_C)
         port map (
            sAxisClk    => axisClk,                     -- [in]
            sAxisRst    => axisRst,                     -- [in]
            sAxisMaster => remoteTxAxisMasters(i),      -- [in]
            sAxisSlave  => remoteTxAxisSlaves(i),       -- [out]
            mAxisClk    => ethClk,                      -- [in]
            mAxisRst    => ethRst,                      -- [in]
            mAxisMaster => fifoRemoteTxAxisMasters(i),  -- [out]
            mAxisSlave  => fifoRemoteTxAxisSlaves(i));  -- [in]

   end generate;

end rtl;
