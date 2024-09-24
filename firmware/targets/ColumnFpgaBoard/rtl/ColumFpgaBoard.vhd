-------------------------------------------------------------------------------
-- Title      : Warm TDM Row Module
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Top level of ColumnFpgaBoard
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
use surf.Ad9681Pkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;


entity ColumnFpgaBoard is

   generic (
      TPD_G                   : time             := 1 ns;
      SIMULATION_G            : boolean          := false;
      SIMULATE_PGP_G          : boolean          := true;
      SIM_PGP_PORT_NUM_G      : integer          := 0;
      SIM_ETH_SRP_PORT_NUM_G  : integer          := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer          := 9000;
      BUILD_INFO_G            : BuildInfoType;
      RING_ADDR_0_G           : boolean          := false;
      ETH_10G_G               : boolean          := false;
      DHCP_G                  : boolean          := false;
      IP_ADDR_G               : slv(31 downto 0) := x"0B03A8C0";  -- 192.168.3.11
      MAC_ADDR_G              : slv(47 downto 0) := x"0B_00_16_56_00_08");
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

      -- Boot PROM interface
      bootCsL  : out sl;
      bootMosi : out sl;
      bootMiso : in  sl;

      -- Local I2C PROM
      locScl     : inout sl;
      locSda     : inout sl;
      tempAlertL : in    sl;

      -- Power Monitor I2C
      pwrScl : inout sl;
      pwrSda : inout sl;

      -- SFP I2C
      sfpScl : inout slv(1 downto 0);
      sfpSda : inout slv(1 downto 0);

      -- VR Synchronization
      pwrSyncA : out sl := '0';
      pwrSyncB : out sl := '0';
      pwrSyncC : out sl := '1';

      -- LEMO IO
      lemoIn  : in  slv(1 downto 0);
      lemoOut : out slv(1 downto 0);

      -- Status LEDs
      leds           : out slv(7 downto 0) := "00000000";
      conRxGreenLed  : out sl              := '1';
      conRxYellowLed : out sl              := '1';
      conTxGreenLed  : out sl              := '1';
      conTxYellowLed : out sl              := '1';

      -- XADC
      localThermistorP : in slv(5 downto 0);
      localThermistorN : in slv(5 downto 0);

      ampPdB : out slv(7 downto 0) := (others => '1');

      -- ADC Data - LVDS
      adcFClkP : in  slv(1 downto 0);
      adcFClkN : in  slv(1 downto 0);
      adcDClkP : in  slv(1 downto 0);
      adcDClkN : in  slv(1 downto 0);
      adcChP   : in  slv8Array(1 downto 0);
      adcChN   : in  slv8Array(1 downto 0);
      adcClkP  : out sl;
      adcClkN  : out sl;

      -- ADC Config - 1.8V
      adcSclk : out   sl;
      adcSdio : inout sl;
      adcCsb  : out   sl;
      adcSync : out   sl;

      -- Fast DAC Interfaces - 3.3V
      sq1BiasDb    : out slv(13 downto 0);
      sq1BiasWrt   : out slv(3 downto 0);
      sq1BiasClk   : out slv(3 downto 0);
      sq1BiasSel   : out slv(3 downto 0);
      sq1BiasReset : out slv(3 downto 0);

      sq1FbDb    : out slv(13 downto 0);
      sq1FbWrt   : out slv(3 downto 0);
      sq1FbClk   : out slv(3 downto 0);
      sq1FbSel   : out slv(3 downto 0);
      sq1FbReset : out slv(3 downto 0);

      saFbDb    : out slv(13 downto 0);
      saFbWrt   : out slv(3 downto 0);
      saFbClk   : out slv(3 downto 0);
      saFbSel   : out slv(3 downto 0);
      saFbReset : out slv(3 downto 0);

      auxDb    : out slv(13 downto 0);
      auxWrt   : out slv(3 downto 0);
      auxClk   : out slv(3 downto 0);
      auxSel   : out slv(3 downto 0);
      auxReset : out slv(3 downto 0);



      ----------------------------------------------------------------------------------------------
      -- Front End Connector IO
      ----------------------------------------------------------------------------------------------
      feThermistorP : in slv(1 downto 0);
      feThermistorN : in slv(1 downto 0);

      -- ASIC I2C
      feI2cScl : inout slv(3 downto 0);
      feI2cSda : inout slv(3 downto 0);

      -- Asic Reset
      resetB : out sl;

      -- VR Synchronization
      feVrSyncA : out sl;
      feVrSyncB : out sl;

      -- DAC SPI
      feDacMosi   : out sl;
      feDacMiso   : in  sl;
      feDacSclk   : out sl;
      feDacSyncB  : out slv(2 downto 0);
      feDacLdacB  : out slv(2 downto 0) := (others => '1');
      feDacResetB : out slv(2 downto 0) := (others => '1');

      -- TES Delatch
      tesDelatch : out slv(7 downto 0) := (others => '0')

      );

end entity ColumnFpgaBoard;

architecture rtl of ColumnFpgaBoard is

   constant NUM_AXIL_MASTERS_C  : integer := 9;
   constant AXIL_ADC_CONFIG_C   : integer := 0;
   constant AXIL_DATA_PATH_C    : integer := 1;
   constant AXIL_SQ1_BIAS_DAC_C : integer := 2;
   constant AXIL_SQ1_FB_DAC_C   : integer := 3;
   constant AXIL_SA_FB_DAC_C    : integer := 4;
   constant AXIL_AUX_DAC_C      : integer := 5;
   constant AXIL_FE_SPI_C       : integer := 6;
   constant AXIL_FE_I2C_C       : integer := 7;
   constant AXIL_TES_DELATCH_C  : integer := 8;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_ADC_CONFIG_C   => (
         baseAddr         => APP_BASE_ADDR_C + X"00200000",
         addrBits         => 16,
         connectivity     => X"FFFF"),
      AXIL_DATA_PATH_C    => (
         baseAddr         => APP_BASE_ADDR_C + X"00300000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SQ1_BIAS_DAC_C => (
         baseAddr         => APP_BASE_ADDR_C + X"00400000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SQ1_FB_DAC_C   => (
         baseAddr         => APP_BASE_ADDR_C + X"00500000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_SA_FB_DAC_C    => (
         baseAddr         => APP_BASE_ADDR_C + X"00600000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_AUX_DAC_C      => (
         baseAddr         => APP_BASE_ADDR_C + X"00700000",
         addrBits         => 20,
         connectivity     => X"FFFF"),
      AXIL_FE_SPI_C       => (
         baseAddr         => APP_BASE_ADDR_C + X"00800000",
         addrBits         => 16,
         connectivity     => X"FFFF"),
      AXIL_FE_I2C_C       => (
         baseAddr         => APP_BASE_ADDR_C + X"10000000",
         addrBits         => 24,
         connectivity     => X"FFFF"),
      AXIL_TES_DELATCH_C  => (
         baseAddr         => APP_BASE_ADDR_C + X"20000000",
         addrBits         => 8,
         connectivity     => X"FFFF"));

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

   signal sq1FbAxilWriteMaster : AxiLiteWriteMasterType;
   signal sq1FbAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal sq1FbAxilReadMaster  : AxiLiteReadMasterType;
   signal sq1FbAxilReadSlave   : AxiLiteReadSlaveType;

   signal i2cAxilWriteMasters : AxiLiteWriteMasterArray(3 downto 0);
   signal i2cAxilWriteSlaves  : AxiLiteWriteSlaveArray(3 downto 0);
   signal i2cAxilReadMasters  : AxiLiteReadMasterArray(3 downto 0);
   signal i2cAxilReadSlaves   : AxiLiteReadSlaveArray(3 downto 0);



   -- Data Streams
   signal axisClk          : sl;
   signal axisRst          : sl;
   signal dataTxAxisMaster : AxiStreamMasterType;
   signal dataTxAxisSlave  : AxiStreamSlaveType;
   signal dataRxAxisMaster : AxiStreamMasterType;
   signal dataRxAxisSlave  : AxiStreamSlaveType := AXI_STREAM_SLAVE_FORCE_C;

   -- Timing clocks and data
   signal timingRxClk125 : sl;
   signal timingRxRst125 : sl;
   signal timingRxData   : LocalTimingType;
   signal sq1FbDacs      : Slv14Array(7 downto 0);

   signal adc : Ad9681SerialType;

   signal tesDelatchInt : slv(31 downto 0);

begin

   -------------------------------------------------------------------------------------------------
   -- Shared logic
   -- PGP, Ethernet, Timing, AxiVersion, Etc
   -------------------------------------------------------------------------------------------------
   U_WarmTdmCore_1 : entity warm_tdm.WarmTdmCore2
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
         MAC_ADDR_G              => MAC_ADDR_G)
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
         xbarTimingSel    => xbarTimingSel,       -- [out]
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
         locScl           => locScl,              -- [inout]
         locSda           => locSda,              -- [inout]
         tempAlertL       => tempAlertL,          -- [in]
         pwrScl           => pwrScl,              -- [inout]
         pwrSda           => pwrSda,              -- [inout]
         sfpScl           => sfpScl,              -- [inout]
         sfpSda           => sfpSda,              -- [inout]
         pwrSyncA         => pwrSyncA,            -- [out]
         pwrSyncB         => pwrSyncB,            -- [out]
         pwrSyncC         => pwrSyncC,            -- [out]
         localThermistorP => localThermistorP,    -- [in]
         localThermistorN => localThermistorN,    -- [in]
         feThermistorP    => feThermistorP,       -- [in]
         feThermistorN    => feThermistorN,       -- [in]
         ampPdB           => ampPdB,              -- [out]
         leds             => leds,                -- [out]
         conRxGreenLed    => conRxGreenLed,       -- [out]
         conRxYellowLed   => conRxYellowLed,      -- [out]
         conTxGreenLed    => conTxGreenLed,       -- [out]
         conTxYellowLed   => conTxYellowLed,      -- [out]
         axilClk          => axilClk,             -- [out]
         axilRst          => axilRst,             -- [out]
         axilWriteMaster  => srpAxilWriteMaster,  -- [out]
         axilWriteSlave   => srpAxilWriteSlave,   -- [in]
         axilReadMaster   => srpAxilReadMaster,   -- [out]
         axilReadSlave    => srpAxilReadSlave,    -- [in]
         axisClk          => axisClk,             -- [out]
         axisRst          => axisRst,             -- [out]
         dataTxAxisMaster => dataTxAxisMaster,    -- [in]
         dataTxAxisSlave  => dataTxAxisSlave,     -- [out]
         dataRxAxisMaster => dataRxAxisMaster,    -- [out]
         dataRxAxisSlave  => dataRxAxisSlave,     -- [in]
         timingRxClk125   => timingRxClk125,      -- [out]
         timingRxRst125   => timingRxRst125,      -- [out]
         timingRxData     => timingRxData);       -- [out]


   -------------------------------------------------------------------------------------------------
   -- Main crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_Main : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 2,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,               -- [in]
         axiClkRst           => axilRst,               -- [in]
         sAxiWriteMasters(0) => srpAxilWriteMaster,    -- [in]
         sAxiWriteMasters(1) => sq1FbAxilWriteMaster,  -- [in]
         sAxiWriteSlaves(0)  => srpAxilWriteSlave,     -- [out]
         sAxiWriteSlaves(1)  => sq1FbAxilWriteSlave,   --[out]
         sAxiReadMasters(0)  => srpAxilReadMaster,     -- [in]
         sAxiReadMasters(1)  => sq1FbAxilReadMaster,   -- [in]
         sAxiReadSlaves(0)   => srpAxilReadSlave,      -- [out]
         sAxiReadSlaves(1)   => sq1FbAxilReadSlave,    -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,   -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,    -- [in]
         mAxiReadMasters     => locAxilReadMasters,    -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);    -- [in]

   -------------------------------------------------------------------------------------------------
   -- FE SPI Bias
   -------------------------------------------------------------------------------------------------
   U_FE_SPI : entity surf.AxiSpiMaster
      generic map (
         TPD_G             => TPD_G,
         ADDRESS_SIZE_G    => 8,
         DATA_SIZE_G       => 16,
         MODE_G            => "WO",
         SHADOW_EN_G       => true,
         CPHA_G            => '1',
         CPOL_G            => '0',
         CLK_PERIOD_G      => 1.0/AXIL_CLK_FREQ_C,              --6.4e-9,
         SPI_SCLK_PERIOD_G => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         SPI_NUM_CHIPS_G   => 3)
      port map (
         axiClk         => axilClk,                             -- [in]
         axiRst         => axilRst,                             -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_FE_SPI_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_FE_SPI_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_FE_SPI_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_FE_SPI_C),   -- [out]
         coreSclk       => feDacSclk,                           -- [out]
         coreSDin       => feDacMiso,                           -- [in]
         coreSDout      => feDacMosi,                           -- [out]
         coreMCsb       => feDacSyncB);                         -- [out]

   -------------------------------------------------------------------------------------------------
   -- FE I2C
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_I2C : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 4,
         MASTERS_CONFIG_G   => genAxiLiteConfig(4, AXIL_XBAR_CFG_C(AXIL_FE_I2C_C).baseAddr, 24, 20))
      port map (
         axiClk              => axilClk,                             -- [in]
         axiClkRst           => axilRst,                             -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(AXIL_FE_I2C_C),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(AXIL_FE_I2C_C),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(AXIL_FE_I2C_C),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(AXIL_FE_I2C_C),    -- [out]
         mAxiWriteMasters    => i2cAxilWriteMasters,                 -- [out]
         mAxiWriteSlaves     => i2cAxilWriteSlaves,                  -- [in]
         mAxiReadMasters     => i2cAxilReadMasters,                  -- [out]
         mAxiReadSlaves      => i2cAxilReadSlaves);                  -- [in]

   GEN_FE_I2C : for i in 3 downto 0 generate
      U_AxiI2cRegMaster_FE_I2C : entity surf.AxiI2cRegMaster
         generic map (
            TPD_G            => TPD_G,
            DEVICE_MAP_G     => (
               0             => MakeI2cAxiLiteDevType(  -- 24LC64FT
                  i2cAddress => "1010000",
                  dataSize   => 8,
                  addrSize   => 16,
                  endianness => '1')),
            I2C_SCL_FREQ_G   => ite(SIMULATION_G, 2.0e6, 100.0E+3),
            I2C_MIN_PULSE_G  => ite(SIMULATION_G, 50.0e-9, 100.0E-9),
            AXI_CLK_FREQ_G   => AXIL_CLK_FREQ_C)
         port map (
            axiClk         => axilClk,                  -- [in]
            axiRst         => axilRst,                  -- [in]
            axiReadMaster  => i2cAxilReadMasters(i),    -- [in]
            axiReadSlave   => i2cAxilReadSlaves(i),     -- [out]
            axiWriteMaster => i2cAxilWriteMasters(i),   -- [in]
            axiWriteSlave  => i2cAxilWriteSlaves(i),    -- [out]
            scl            => feI2cScl(i),              -- [inout]
            sda            => feI2cSda(i));             -- [inout]
   end generate GEN_FE_I2C;

   -------------------------------------------------------------------------------------------------
   -- TES Bias Delatch
   -------------------------------------------------------------------------------------------------
   U_AxiLiteRegs_1 : entity surf.AxiLiteRegs
      generic map (
         TPD_G           => TPD_G,
         NUM_WRITE_REG_G => 1,
         NUM_READ_REG_G  => 1)
      port map (
         axiClk           => axilClk,                                  -- [in]
         axiClkRst        => axilRst,                                  -- [in]
         axiReadMaster    => locAxilReadMasters(AXIL_TES_DELATCH_C),   -- [in]
         axiReadSlave     => locAxilReadSlaves(AXIL_TES_DELATCH_C),    -- [out]
         axiWriteMaster   => locAxilWriteMasters(AXIL_TES_DELATCH_C),  -- [in]
         axiWriteSlave    => locAxilWriteSlaves(AXIL_TES_DELATCH_C),   -- [out]
         writeRegister(0) => tesDelatchInt);                           -- [out]

   tesDelatch <= tesDelatchInt(7 downto 0);



   -------------------------------------------------------------------------------------------------
   -- ADC Config
   -------------------------------------------------------------------------------------------------
   U_Ad9249Config_1 : entity surf.Ad9681Config
      generic map (
         TPD_G             => TPD_G,
         NUM_CHIPS_G       => 1,
         SCLK_PERIOD_G     => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         AXIL_CLK_PERIOD_G => 1.0/AXIL_CLK_FREQ_C)                   --6.4E-9)
      port map (
         axilClk         => axilClk,                                 -- [in]
         axilRst         => axilRst,                                 -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_ADC_CONFIG_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_ADC_CONFIG_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_ADC_CONFIG_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_ADC_CONFIG_C),   -- [out]
--         adcPdwn(0)      => adcPdwn,                                 -- [out]
         adcSclk         => adcSclk,                                 -- [out]
         adcSdio         => adcSdio,                                 -- [inout]
         adcCsb(0)       => adcCsb);                                 -- [out]


   -------------------------------------------------------------------------------------------------
   -- ADC Data Path
   -------------------------------------------------------------------------------------------------
   adc.fClkP <= adcFClkP;
   adc.fClkN <= adcFClkN;
   adc.dClkP <= adcDClkP;
   adc.dClkN <= adcDClkN;
   adc.chP   <= adcChP;
   adc.chN   <= adcChN;

   -------------------------------------------------------------------------------------------------
   -- Use timing rx clock as ADC sampling clock
   -------------------------------------------------------------------------------------------------
   U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
      generic map (
         TPD_G => TPD_G)
      port map (
         clkIn   => timingRxClk125,     -- [in]
         clkOutP => adcClkP,            -- [out]
         clkOutN => adcClkN);           -- [out]


   -------------------------------------------------------------------------------------------------
   -- Data Path
   -------------------------------------------------------------------------------------------------
   U_DataPath_1 : entity warm_tdm.DataPath
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => SIMULATION_G,
         NEGATE_ADC_G     => false,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_DATA_PATH_C).baseAddr,
         SQ1FB_RAM_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_FB_DAC_C).baseAddr,
         IODELAY_GROUP_G  => "IODELAY0")
      port map (
         adc              => adc,                                    -- [in]
         timingRxClk125   => timingRxClk125,                         -- [in]
         timingRxRst125   => timingRxRst125,                         -- [in]
         timingRxData     => timingRxData,                           -- [in]
         sq1FbDacs        => sq1FbDacs,                              --[in]
         axisClk          => axisClk,                                -- [in]
         axisRst          => axisRst,                                -- [in]
         axisMaster       => dataTxAxisMaster,                       -- [out]
         axisSlave        => dataTxAxisSlave,                        -- [in]
         axilClk          => axilClk,                                -- [in]
         axilRst          => axilRst,                                -- [in]
         sAxilReadMaster  => locAxilReadMasters(AXIL_DATA_PATH_C),   -- [in]
         sAxilReadSlave   => locAxilReadSlaves(AXIL_DATA_PATH_C),    -- [out]
         sAxilWriteMaster => locAxilWriteMasters(AXIL_DATA_PATH_C),  -- [in]
         sAxilWriteSlave  => locAxilWriteSlaves(AXIL_DATA_PATH_C),   -- [out]
         mAxilReadMaster  => sq1FbAxilReadMaster,                    -- [out]
         mAxilReadSlave   => sq1FbAxilReadSlave,                     -- [in]
         mAxilWriteMaster => sq1FbAxilWriteMaster,                   -- [out]
         mAxilWriteSlave  => sq1FbAxilWriteSlave);                   -- [in]



   -------------------------------------------------------------------------------------------------
   -- Fast DAC drivers
   -------------------------------------------------------------------------------------------------
   U_FastDacDriver_SQ1_BIAS : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_BIAS_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125,                            -- [in]
         timingRxRst125  => timingRxRst125,                            -- [in]
         timingRxData    => timingRxData,                              -- [in]
         dacDb           => sq1BiasDb,                                 -- [out]
         dacWrt          => sq1BiasWrt,                                -- [out]
         dacClk          => sq1BiasClk,                                -- [out]
         dacSel          => sq1BiasSel,                                -- [out]
         dacReset        => sq1BiasReset,                              -- [out]
         axilClk         => axilClk,                                   -- [in]
         axilRst         => axilRst,                                   -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_SQ1_BIAS_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SQ1_BIAS_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_SQ1_BIAS_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SQ1_BIAS_DAC_C));   -- [out]

   U_FastDacDriver_SQ1_FB : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_FB_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125,                          -- [in]
         timingRxRst125  => timingRxRst125,                          -- [in]
         timingRxData    => timingRxData,                            -- [in]
         dacOut          => sq1FbDacs,                               -- [out]
         dacDb           => sq1FbDb,                                 -- [out]
         dacWrt          => sq1FbWrt,                                -- [out]
         dacClk          => sq1FbClk,                                -- [out]
         dacSel          => sq1FbSel,                                -- [out]
         dacReset        => sq1FbReset,                              -- [out]
         axilClk         => axilClk,                                 -- [in]
         axilRst         => axilRst,                                 -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_SQ1_FB_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SQ1_FB_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_SQ1_FB_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SQ1_FB_DAC_C));   -- [out]

   U_FastDacDriver_SA_FB : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SA_FB_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125,                         -- [in]
         timingRxRst125  => timingRxRst125,                         -- [in]
         timingRxData    => timingRxData,                           -- [in]
         dacDb           => saFbDb,                                 -- [out]
         dacWrt          => saFbWrt,                                -- [out]
         dacClk          => saFbClk,                                -- [out]
         dacSel          => saFbSel,                                -- [out]
         dacReset        => saFbReset,                              -- [out]
         axilClk         => axilClk,                                -- [in]
         axilRst         => axilRst,                                -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_SA_FB_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SA_FB_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_SA_FB_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SA_FB_DAC_C));   -- [out]

   U_FastDacDriver_AUX : entity warm_tdm.FastDacDriver
      generic map (
         TPD_G            => TPD_G,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_AUX_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125,                       -- [in]
         timingRxRst125  => timingRxRst125,                       -- [in]
         timingRxData    => timingRxData,                         -- [in]
         dacDb           => auxDb,                                -- [out]
         dacWrt          => auxWrt,                               -- [out]
         dacClk          => auxClk,                               -- [out]
         dacSel          => auxSel,                               -- [out]
         dacReset        => auxReset,                             -- [out]
         axilClk         => axilClk,                              -- [in]
         axilRst         => axilRst,                              -- [in]
         axilWriteMaster => locAxilWriteMasters(AXIL_AUX_DAC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_AUX_DAC_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(AXIL_AUX_DAC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_AUX_DAC_C));   -- [out]



end architecture rtl;
