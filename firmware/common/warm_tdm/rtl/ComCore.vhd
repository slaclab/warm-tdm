-------------------------------------------------------------------------------
-- Title      : ComCore
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: PGP and Ethernet cores
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

library unisim;
use unisim.vcomponents.all;

library warm_tdm;

entity ComCore is

   generic (
      TPD_G                   : time             := 1 ns;
      SIMULATION_G            : boolean          := false;
      SIM_PGP_PORT_NUM_G      : integer          := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer          := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer          := 9000;
      RING_ADDR_0_G           : boolean          := false;
      AXIL_BASE_ADDR_G        : slv(31 downto 0) := X"00000000";
      ETH_10G_G               : boolean          := true;
      DHCP_G                  : boolean          := false;  -- true = DHCP, false = static address
      IP_ADDR_G               : slv(31 downto 0) := X"0A01A8C0";  -- 192.168.1.10 (before DHCP)
      MAC_ADDR_G              : slv(47 downto 0) := x"00_00_16_56_00_08");
   port (
      gtRefClkP       : in  sl;
      gtRefClkN       : in  sl;
      gtRefClkDiv2Out : out sl;

      -- PGP IO
      pgpTxP : out sl;
      pgpTxN : out sl;
      pgpRxP : in  sl;
      pgpRxN : in  sl;

      -- Ethernet IO
      ethRxP : in  sl;
      ethRxN : in  sl;
      ethTxP : out sl;
      ethTxN : out sl;

      -- Debug
      rssiStatus  : out slv7Array(1 downto 0);
      ethPhyReady : out sl;

      -- AXI Lite Master
      axilClkOut       : out sl;
      axilRstOut       : out sl;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType;
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType;
      -- AXI Lite Slave
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType;
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType;

      -- Data Streams
      dataTxAxisMaster : in  AxiStreamMasterType;
      dataTxAxisSlave  : out AxiStreamSlaveType;
      dataRxAxisMaster : out AxiStreamMasterType;
      dataRxAxisSlave  : in  AxiStreamSlaveType);


end entity ComCore;

architecture rtl of ComCore is

   constant AXIL_PGP_C : integer := 0;
   constant AXIL_ETH_C : integer := 1;

   signal gtRefClk      : sl;
   signal gtRefClkDiv2  : sl;
   signal gtRefClkDiv2G : sl;

   signal axilClk : sl;
   signal axilRst : sl;

   signal mLocAxilWriteMasters : AxiLiteWriteMasterArray(1 downto 0);
   signal mLocAxilWriteSlaves  : AxiLiteWriteSlaveArray(1 downto 0);
   signal mLocAxilReadMasters  : AxiLiteReadMasterArray(1 downto 0);
   signal mLocAxilReadSlaves   : AxiLiteReadSlaveArray(1 downto 0);

   signal sLocAxilWriteMasters : AxiLiteWriteMasterArray(1 downto 0);
   signal sLocAxilWriteSlaves  : AxiLiteWriteSlaveArray(1 downto 0);
   signal sLocAxilReadMasters  : AxiLiteReadMasterArray(1 downto 0);
   signal sLocAxilReadSlaves   : AxiLiteReadSlaveArray(1 downto 0);

   signal ethRemoteRxAxisMasters : AxiStreamMasterArray(3 downto 0);
   signal ethRemoteRxAxisSlaves  : AxiStreamSlaveArray(3 downto 0);
   signal ethRemoteTxAxisMasters : AxiStreamMasterArray(3 downto 0);
   signal ethRemoteTxAxisSlaves  : AxiStreamSlaveArray(3 downto 0);

   signal ethDataRxAxisMaster : AxiStreamMasterType;
   signal ethDataRxAxisSlave  : AxiStreamSlaveType;
   signal ethDataTxAxisMaster : AxiStreamMasterType;
   signal ethDataTxAxisSlave  : AxiStreamSlaveType;


   signal pgpDataRxAxisMaster : AxiStreamMasterType;
   signal pgpDataRxAxisSlave  : AxiStreamSlaveType;
   signal pgpDataTxAxisMaster : AxiStreamMasterType;
   signal pgpDataTxAxisSlave  : AxiStreamSlaveType;

   signal refRst : sl;

begin

   axilClkOut <= axilClk;
   axilRstOut <= axilRst;


   ------------------
   -- Reference Clock
   ------------------
   U_IBUFDS_GTE2 : IBUFDS_GTE2
      port map (
         I     => gtRefClkP,
         IB    => gtRefClkN,
         CEB   => '0',
         ODIV2 => gtRefClkDiv2,
         O     => gtRefClk);

   U_BUFG : BUFG
      port map (
         I => gtRefClkDiv2,
         O => gtRefClkDiv2G);
   gtRefClkDiv2Out <= gtRefClkDiv2G;

   -----------------
   -- Power Up Reset
   -----------------
   U_PwrUpRst : entity surf.PwrUpRst
      generic map (
         TPD_G         => TPD_G,
         SIM_SPEEDUP_G => SIMULATION_G)
      port map (
         clk    => gtRefClkDiv2G,
         rstOut => refRst);

   -----------------
   -- PGP Interface
   -----------------
   U_PgpCore_1 : entity warm_tdm.PgpCore
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => SIMULATION_G,
         SIM_PORT_NUM_G   => SIM_PGP_PORT_NUM_G,
         RING_ADDR_0_G    => RING_ADDR_0_G,
         AXIL_BASE_ADDR_G => AXIL_BASE_ADDR_G)
      port map (
         refRst           => refRst,                            -- [in]
         gtRefClk         => gtRefClk,                          -- [in]
         gtRefClkG        => gtRefClkDiv2G,                     -- [in]
         pgpTxP           => pgpTxP,                            -- [out]
         pgpTxN           => pgpTxN,                            -- [out]
         pgpRxP           => pgpRxP,                            -- [in]
         pgpRxN           => pgpRxN,                            -- [in]
         axiClk           => axilClk,                           -- [out]
         axiRst           => axilRst,                           -- [out]
         mAxilReadMaster  => mLocAxilReadMasters(AXIL_PGP_C),   -- [out]
         mAxilReadSlave   => mLocAxilReadSlaves(AXIL_PGP_C),    -- [in]
         mAxilWriteMaster => mLocAxilWriteMasters(AXIL_PGP_C),  -- [out]
         mAxilWriteSlave  => mLocAxilWriteSlaves(AXIL_PGP_C),   -- [in]
         sAxilReadMaster  => sLocAxilReadMasters(AXIL_PGP_C),   -- [in]
         sAxilReadSlave   => sLocAxilReadSlaves(AXIL_PGP_C),    -- [out]
         sAxilWriteMaster => sLocAxilWriteMasters(AXIL_PGP_C),  -- [in]
         sAxilWriteSlave  => sLocAxilWriteSlaves(AXIL_PGP_C),   -- [out]
         ethRxAxisMasters => ethRemoteRxAxisMasters,            -- [in]
         ethRxAxisSlaves  => ethRemoteRxAxisSlaves,             -- [out]
         ethTxAxisMasters => ethRemoteTxAxisMasters,            -- [out]
         ethTxAxisSlaves  => ethRemoteTxAxisSlaves,             -- [in]
         dataTxAxisMaster => pgpDataTxAxisMaster,               -- [in]
         dataTxAxisSlave  => pgpDataTxAxisSlave,                -- [out]
         dataRxAxisMaster => pgpDataRxAxisMaster,               -- [out]
         dataRxAxisSlave  => pgpDataRxAxisSlave);               -- [in]

   ---------------------
   -- Ethernet Interface
   ---------------------
   U_EthCore_1 : entity warm_tdm.EthCore
      generic map (
         TPD_G               => TPD_G,
         RING_ADDR_0_G       => RING_ADDR_0_G,
         ETH_10G_G           => ETH_10G_G,
         SIMULATION_G        => SIMULATION_G,
         SIM_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         AXIL_BASE_ADDR_G    => AXIL_BASE_ADDR_G + X"00100000",
         AXIL_CLK_FREQ_G     => 125.0e6,
         DHCP_G              => DHCP_G,
         IP_ADDR_G           => IP_ADDR_G,
         MAC_ADDR_G          => MAC_ADDR_G)
      port map (
         extRst                => '0',                               -- [in]
         refClk                => gtRefClkDiv2,                      -- [in]
         refClkG               => gtRefClkDiv2G,                     -- [in]
         gtRxP                 => ethRxP,                            -- [in]
         gtRxN                 => ethRxN,                            -- [in]
         gtTxP                 => ethTxP,                            -- [out]
         gtTxN                 => ethTxN,                            -- [out]
         phyReady              => ethPhyReady,                       -- [out]
         rssiStatus            => rssiStatus,                        -- [out]
         axilClk               => axilClk,                           -- [in]
         axilRst               => axilRst,                           -- [in]
         mAxilReadMaster       => mLocAxilReadMasters(AXIL_ETH_C),   -- [out]
         mAxilReadSlave        => mLocAxilReadSlaves(AXIL_ETH_C),    -- [in]
         mAxilWriteMaster      => mLocAxilWriteMasters(AXIL_ETH_C),  -- [out]
         mAxilWriteSlave       => mLocAxilWriteSlaves(AXIL_ETH_C),   -- [in]
         sAxilReadMaster       => sLocAxilReadMasters(AXIL_ETH_C),   -- [in]
         sAxilReadSlave        => sLocAxilReadSlaves(AXIL_ETH_C),    -- [out]
         sAxilWriteMaster      => sLocAxilWriteMasters(AXIL_ETH_C),  -- [in]
         sAxilWriteSlave       => sLocAxilWriteSlaves(AXIL_ETH_C),   -- [out]
         axisClk               => axilClk,                           -- [in]
         axisRst               => axilRst,                           -- [in]
         localDataRxAxisMaster => ethDataRxAxisMaster,               -- [out]
         localDataRxAxisSlave  => ethDataRxAxisSlave,                -- [in]
         localDataTxAxisMaster => ethDataTxAxisMaster,               -- [in]
         localDataTxAxisSlave  => ethDataTxAxisSlave,                -- [out]
         remoteRxAxisMasters   => ethRemoteRxAxisMasters,            -- [out]
         remoteRxAxisSlaves    => ethRemoteRxAxisSlaves,             -- [in]
         remoteTxAxisMasters   => ethRemoteTxAxisMasters,            -- [in]
         remoteTxAxisSlaves    => ethRemoteTxAxisSlaves);            -- [out]

   -------------------------------------
   -- Data Mux
   -- Route data to PGP or ETH if master
   -------------------------------------
   ADDR_0 : if (RING_ADDR_0_G) generate
      dataRxAxisMaster    <= ethDataRxAxisMaster;
      ethDataRxAxisSlave  <= dataRxAxisSlave;
      ethDataTxAxisMaster <= dataTxAxisMaster;
      dataTxAxisSlave     <= ethDataTxAxisSlave;
   end generate ADDR_0;

   NOT_ADDR_0 : if (not RING_ADDR_0_G) generate
      dataRxAxisMaster    <= pgpDataRxAxisMaster;
      pgpDataRxAxisSlave  <= dataRxAxisSlave;
      pgpDataTxAxisMaster <= dataTxAxisMaster;
      dataTxAxisSlave     <= pgpDataTxAxisSlave;
   end generate NOT_ADDR_0;

   -----------------------------------------------------
   -- Combine the two SRP AXIL Masters onto a single bus
   -----------------------------------------------------
   U_AxiLiteCrossbar_MUX : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 2,
         NUM_MASTER_SLOTS_G => 1,
         MASTERS_CONFIG_G   => (
            0               => (
               baseAddr     => (others => '0'),
               addrBits     => 32,
               connectivity => X"FFFF")),
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,               -- [in]
         axiClkRst           => axilRst,               -- [in]
         sAxiWriteMasters    => mLocAxilWriteMasters,  -- [in]
         sAxiWriteSlaves     => mLocAxilWriteSlaves,   -- [out]
         sAxiReadMasters     => mLocAxilReadMasters,   -- [in]
         sAxiReadSlaves      => mLocAxilReadSlaves,    -- [out]
         mAxiWriteMasters(0) => mAxilWriteMaster,      -- [out]
         mAxiWriteSlaves(0)  => mAxilWriteSlave,       -- [in]
         mAxiReadMasters(0)  => mAxilReadMaster,       -- [out]
         mAxiReadSlaves(0)   => mAxilReadSlave);       -- [in]

   --------------------------------
   -- Fanout the bus from top level
   --------------------------------
   U_AxiLiteCrossbar_FANOUT : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 2,
         MASTERS_CONFIG_G   => (
            AXIL_PGP_C      => (
               baseAddr     => AXIL_BASE_ADDR_G + X"00000000",
               addrBits     => 16,
               connectivity => X"FFFF"),
            AXIL_ETH_C      => (
               baseAddr     => AXIL_BASE_ADDR_G + X"00100000",
               addrBits     => 20,
               connectivity => X"FFFF")),
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,               -- [in]
         axiClkRst           => axilRst,               -- [in]
         sAxiWriteMasters(0) => sAxilWriteMaster,      -- [in]
         sAxiWriteSlaves(0)  => sAxilWriteSlave,       -- [out]
         sAxiReadMasters(0)  => sAxilReadMaster,       -- [in]
         sAxiReadSlaves(0)   => sAxilReadSlave,        -- [out]
         mAxiWriteMasters    => sLocAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => sLocAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => sLocAxilReadMasters,   -- [out]
         mAxiReadSlaves      => sLocAxilReadSlaves);   -- [in]


end rtl;
