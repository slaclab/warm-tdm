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

entity ColumnAu25p is
   generic (
      TPD_G                   : time                 := 1 ns;
      SIMULATION_G            : boolean              := false;
      SIMULATE_PGP_G          : boolean              := true;
      SIM_PGP_PORT_NUM_G      : integer              := 0;
      SIM_ETH_SRP_PORT_NUM_G  : integer              := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer              := 9000;
      BUILD_INFO_G            : BuildInfoType;
      RING_ADDR_0_G           : boolean              := false;
      ETH_10G_G               : boolean              := true;
      DHCP_G                  : boolean              := false;
      IP_ADDR_G               : slv(31 downto 0)     := x"0B03A8C0";
      MAC_ADDR_G              : slv(47 downto 0)     := x"0B_00_16_56_00_08";
      GEN_ADC_FILTER_G        : boolean              := false;
      ROW_ADDR_BITS_G         : integer range 3 to 8 := 8);
   port (
      gtRefClk0P : in sl;
      gtRefClk0N : in sl;
      gtRefClk1P : in sl;
      gtRefClk1N : in sl;
      pgpTxP : out slv(1 downto 0);
      pgpTxN : out slv(1 downto 0);
      pgpRxP : in  slv(1 downto 0);
      pgpRxN : in  slv(1 downto 0);
      xbarDataSel   : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarClkSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarMgtSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarTimingSel : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      timingRxClkP  : in  sl;
      timingRxClkN  : in  sl;
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      timingTxClkP  : out sl;
      timingTxClkN  : out sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl;
      sfp0TxP : out sl;
      sfp0TxN : out sl;
      sfp0RxP : in  sl;
      sfp0RxN : in  sl;
      bootCsL  : out sl;
      bootMosi : out sl;
      bootMiso : in  sl;
      locScl     : inout sl;
      locSda     : inout sl;
      tempAlertL : in    sl;
      pwrScl : inout sl;
      pwrSda : inout sl;
      sfpScl : inout slv(1 downto 0);
      sfpSda : inout slv(1 downto 0);
      anaPwrEn : out sl := '1';
      pwrSyncA : out sl := '0';
      pwrSyncB : out sl := '0';
      pwrSyncC : out sl := '1';
      lemoIn  : in  slv(1 downto 0);
      lemoOut : out slv(1 downto 0);
      leds           : out slv(7 downto 0) := "00000000";
      conRxGreenLed  : out sl              := '1';
      conRxYellowLed : out sl              := '1';
      conTxGreenLed  : out sl              := '1';
      conTxYellowLed : out sl              := '1';
      localThermistorP : in slv(5 downto 0);
      localThermistorN : in slv(5 downto 0);
      ampPdB : out slv(7 downto 0) := (others => '1');
      adcFClkP : in  slv(1 downto 0);
      adcFClkN : in  slv(1 downto 0);
      adcDClkP : in  slv(1 downto 0);
      adcDClkN : in  slv(1 downto 0);
      adcChP   : in  slv8Array(1 downto 0);
      adcChN   : in  slv8Array(1 downto 0);
      adcClkP  : out sl;
      adcClkN  : out sl;
      adcSclk : out   sl;
      adcSdio : inout sl;
      adcCsb  : out   sl;
      adcSync : out   sl;
      adcPdwn : out   sl := '0';
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
      feThermistorP : in slv(1 downto 0);
      feThermistorN : in slv(1 downto 0);
      tesDacSclk  : out sl;
      tesDacDin   : out sl;
      tesDacLdacL : out sl := '0';
      tesDacCsL   : out slv(7 downto 0);
      resetB : out sl := '1';
      fePwrSyncA : out sl;
      fePwrSyncB : out sl;
      feDacMosi   : out sl;
      feDacMiso   : in  sl;
      feDacSclk   : out sl;
      feDacSyncB  : out slv(2 downto 0);
      feDacLdacB  : out slv(2 downto 0) := (others => '1');
      feDacResetB : out slv(2 downto 0) := (others => '1');
      tesDelatch : out slv(7 downto 0) := (others => '0'));
end entity ColumnAu25p;

architecture rtl of ColumnAu25p is

   constant AXIL_CLK_FREQ_C : real := 156.25E+6;

   constant NUM_AXIL_MASTERS_C  : integer := 10;
   constant AXIL_ADC_CONFIG_C   : integer := 0;
   constant AXIL_DATA_PATH_C    : integer := 1;
   constant AXIL_SQ1_BIAS_DAC_C : integer := 2;
   constant AXIL_SQ1_FB_DAC_C   : integer := 3;
   constant AXIL_SA_FB_DAC_C    : integer := 4;
   constant AXIL_AUX_DAC_C      : integer := 5;
   constant AXIL_FE_SPI_C       : integer := 6;
   constant AXIL_FE_I2C_C       : integer := 7;
   constant AXIL_FE_TES_SPI_C   : integer := 8;
   constant AXIL_TES_DELATCH_C  : integer := 9;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_ADC_CONFIG_C   => (baseAddr => APP_BASE_ADDR_C + X"00200000", addrBits => 16, connectivity => X"FFFF"),
      AXIL_DATA_PATH_C    => (baseAddr => APP_BASE_ADDR_C + X"01000000", addrBits => 24, connectivity => X"FFFF"),
      AXIL_SQ1_BIAS_DAC_C => (baseAddr => APP_BASE_ADDR_C + X"00400000", addrBits => 20, connectivity => X"FFFF"),
      AXIL_SQ1_FB_DAC_C   => (baseAddr => APP_BASE_ADDR_C + X"00500000", addrBits => 20, connectivity => X"FFFF"),
      AXIL_SA_FB_DAC_C    => (baseAddr => APP_BASE_ADDR_C + X"00600000", addrBits => 20, connectivity => X"FFFF"),
      AXIL_AUX_DAC_C      => (baseAddr => APP_BASE_ADDR_C + X"00700000", addrBits => 20, connectivity => X"FFFF"),
      AXIL_FE_SPI_C       => (baseAddr => APP_BASE_ADDR_C + X"00800000", addrBits => 16, connectivity => X"FFFF"),
      AXIL_TES_DELATCH_C  => (baseAddr => APP_BASE_ADDR_C + X"00900000", addrBits => 9, connectivity => X"FFFF"),
      AXIL_FE_I2C_C       => (baseAddr => APP_BASE_ADDR_C + X"08000000", addrBits => 27, connectivity => X"FFFF"),
      AXIL_FE_TES_SPI_C   => (baseAddr => APP_BASE_ADDR_C + X"00901000", addrBits => 12, connectivity => X"FFFF"));

   signal axilClk : sl;
   signal axilRst : sl;

   signal adcFilterEn : slv(7 downto 0);

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

   signal axisClk          : sl;
   signal axisRst          : sl;
   signal dataTxAxisMaster : AxiStreamMasterType;
   signal dataTxAxisSlave  : AxiStreamSlaveType;
   signal dataRxAxisMaster : AxiStreamMasterType;
   signal dataRxAxisSlave  : AxiStreamSlaveType := AXI_STREAM_SLAVE_FORCE_C;

   signal timingRxClk125 : sl;
   signal timingRxRst125 : sl;
   signal timingRxData   : LocalTimingType;
   signal sq1FbDacs      : Slv14Array(7 downto 0);

   signal adc : Ad9681SerialType;

   signal tesDelatchInt  : slv(31 downto 0);
   signal tesDacLdacLInt : slv(31 downto 0);
   signal tesDacPwrUpLdacL : sl;

   constant INI_WRITE_REG_C : Slv32Array(1 downto 0) := (0 => X"00000000", 1 => X"FFFFFFFF");

begin

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
         FPGA_FAMILY_G           => "ULTRASCALE_PLUS",
         DHCP_G                  => DHCP_G,
         IP_ADDR_G               => IP_ADDR_G,
         MAC_ADDR_G              => MAC_ADDR_G)
      port map (
         gtRefClk0P       => gtRefClk0P,
         gtRefClk0N       => gtRefClk0N,
         gtRefClk1P       => gtRefClk1P,
         gtRefClk1N       => gtRefClk1N,
         pgpTxP           => pgpTxP,
         pgpTxN           => pgpTxN,
         pgpRxP           => pgpRxP,
         pgpRxN           => pgpRxN,
         xbarDataSel      => xbarDataSel,
         xbarClkSel       => xbarClkSel,
         xbarMgtSel       => xbarMgtSel,
         xbarTimingSel    => xbarTimingSel,
         timingRxClkP     => timingRxClkP,
         timingRxClkN     => timingRxClkN,
         timingRxDataP    => timingRxDataP,
         timingRxDataN    => timingRxDataN,
         timingTxClkP     => timingTxClkP,
         timingTxClkN     => timingTxClkN,
         timingTxDataP    => timingTxDataP,
         timingTxDataN    => timingTxDataN,
         sfp0TxP          => sfp0TxP,
         sfp0TxN          => sfp0TxN,
         sfp0RxP          => sfp0RxP,
         sfp0RxN          => sfp0RxN,
         bootCsL          => bootCsL,
         bootMosi         => bootMosi,
         bootMiso         => bootMiso,
         locScl           => locScl,
         locSda           => locSda,
         tempAlertL       => tempAlertL,
         pwrScl           => pwrScl,
         pwrSda           => pwrSda,
         sfpScl           => sfpScl,
         sfpSda           => sfpSda,
         anaPwrEn         => anaPwrEn,
         pwrSyncA         => pwrSyncA,
         pwrSyncB         => pwrSyncB,
         pwrSyncC         => pwrSyncC,
         localThermistorP => localThermistorP,
         localThermistorN => localThermistorN,
         feThermistorP    => feThermistorP,
         feThermistorN    => feThermistorN,
         asicResetB       => resetB,
         ampPdB           => ampPdB,
         adcFilterEn      => adcFilterEn,
         leds             => leds,
         conRxGreenLed    => conRxGreenLed,
         conRxYellowLed   => conRxYellowLed,
         conTxGreenLed    => conTxGreenLed,
         conTxYellowLed   => conTxYellowLed,
         axilClk          => axilClk,
         axilRst          => axilRst,
         axilWriteMaster  => srpAxilWriteMaster,
         axilWriteSlave   => srpAxilWriteSlave,
         axilReadMaster   => srpAxilReadMaster,
         axilReadSlave    => srpAxilReadSlave,
         axisClk          => axisClk,
         axisRst          => axisRst,
         dataTxAxisMaster => dataTxAxisMaster,
         dataTxAxisSlave  => dataTxAxisSlave,
         dataRxAxisMaster => dataRxAxisMaster,
         dataRxAxisSlave  => dataRxAxisSlave,
         timingRxClk125   => timingRxClk125,
         timingRxRst125   => timingRxRst125,
         timingRxData     => timingRxData);

   U_AxiLiteCrossbar_Main : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 2,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,
         axiClkRst           => axilRst,
         sAxiWriteMasters(0) => srpAxilWriteMaster,
         sAxiWriteMasters(1) => sq1FbAxilWriteMaster,
         sAxiWriteSlaves(0)  => srpAxilWriteSlave,
         sAxiWriteSlaves(1)  => sq1FbAxilWriteSlave,
         sAxiReadMasters(0)  => srpAxilReadMaster,
         sAxiReadMasters(1)  => sq1FbAxilReadMaster,
         sAxiReadSlaves(0)   => srpAxilReadSlave,
         sAxiReadSlaves(1)   => sq1FbAxilReadSlave,
         mAxiWriteMasters    => locAxilWriteMasters,
         mAxiWriteSlaves     => locAxilWriteSlaves,
         mAxiReadMasters     => locAxilReadMasters,
         mAxiReadSlaves      => locAxilReadSlaves);

   U_FE_SPI : entity surf.AxiSpiMaster
      generic map (
         TPD_G             => TPD_G,
         ADDRESS_SIZE_G    => 8,
         DATA_SIZE_G       => 16,
         MODE_G            => "WO",
         SHADOW_EN_G       => true,
         CPHA_G            => '1',
         CPOL_G            => '0',
         CLK_PERIOD_G      => 1.0/AXIL_CLK_FREQ_C,
         SPI_SCLK_PERIOD_G => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         SPI_NUM_CHIPS_G   => 3)
      port map (
         axiClk         => axilClk,
         axiRst         => axilRst,
         axiReadMaster  => locAxilReadMasters(AXIL_FE_SPI_C),
         axiReadSlave   => locAxilReadSlaves(AXIL_FE_SPI_C),
         axiWriteMaster => locAxilWriteMasters(AXIL_FE_SPI_C),
         axiWriteSlave  => locAxilWriteSlaves(AXIL_FE_SPI_C),
         coreSclk       => feDacSclk,
         coreSDin       => feDacMiso,
         coreSDout      => feDacMosi,
         coreMCsb       => feDacSyncB);

   U_AxiSpiMaster_FE_TES_DACS : entity surf.AxiSpiMaster
      generic map (
         TPD_G             => TPD_G,
         ADDRESS_SIZE_G    => 0,
         DATA_SIZE_G       => 16,
         MODE_G            => "WO",
         SHADOW_EN_G       => true,
         SHADOW_MEM_TYPE_G => "distributed",
         CPHA_G            => '0',
         CPOL_G            => '0',
         CLK_PERIOD_G      => 1.0/AXIL_CLK_FREQ_C,
         SPI_SCLK_PERIOD_G => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         SPI_NUM_CHIPS_G   => 8)
      port map (
         axiClk         => axilClk,
         axiRst         => axilRst,
         axiReadMaster  => locAxilReadMasters(AXIL_FE_TES_SPI_C),
         axiReadSlave   => locAxilReadSlaves(AXIL_FE_TES_SPI_C),
         axiWriteMaster => locAxilWriteMasters(AXIL_FE_TES_SPI_C),
         axiWriteSlave  => locAxilWriteSlaves(AXIL_FE_TES_SPI_C),
         coreSclk       => tesDacSclk,
         coreSDin       => '0',
         coreSDout      => tesDacDin,
         coreMCsb       => tesDacCsL);

   U_AxiLiteRegs_1 : entity surf.AxiLiteRegs
      generic map (
         TPD_G           => TPD_G,
         NUM_WRITE_REG_G => 2,
         NUM_READ_REG_G  => 1,
         INI_WRITE_REG_G => INI_WRITE_REG_C)
      port map (
         axiClk           => axilClk,
         axiClkRst        => axilRst,
         axiReadMaster    => locAxilReadMasters(AXIL_TES_DELATCH_C),
         axiReadSlave     => locAxilReadSlaves(AXIL_TES_DELATCH_C),
         axiWriteMaster   => locAxilWriteMasters(AXIL_TES_DELATCH_C),
         axiWriteSlave    => locAxilWriteSlaves(AXIL_TES_DELATCH_C),
         writeRegister(0) => tesDelatchInt,
         writeRegister(1) => tesDacLdacLInt);

   tesDelatch <= tesDelatchInt(7 downto 0);

   U_PwrUpRst_1 : entity surf.PwrUpRst
      generic map (TPD_G => TPD_G, OUT_POLARITY_G => '0', DURATION_G => 10)
      port map (clk => axilClk, rstOut => tesDacPwrUpLdacL);

   tesDacLdacL <= tesDacPwrUpLdacL when tesDacPwrUpLdacL = '0' else tesDacLdacLInt(0);

   U_Ad9249Config_1 : entity surf.Ad9681Config
      generic map (
         TPD_G             => TPD_G,
         NUM_CHIPS_G       => 1,
         SCLK_PERIOD_G     => ite(SIMULATION_G, 100.0e-9, 1.0E-6),
         AXIL_CLK_PERIOD_G => 1.0/AXIL_CLK_FREQ_C)
      port map (
         axilClk         => axilClk,
         axilRst         => axilRst,
         axilReadMaster  => locAxilReadMasters(AXIL_ADC_CONFIG_C),
         axilReadSlave   => locAxilReadSlaves(AXIL_ADC_CONFIG_C),
         axilWriteMaster => locAxilWriteMasters(AXIL_ADC_CONFIG_C),
         axilWriteSlave  => locAxilWriteSlaves(AXIL_ADC_CONFIG_C),
         adcSclk         => adcSclk,
         adcSdio         => adcSdio,
         adcCsb(0)       => adcCsb);

   adc.fClkP <= adcFClkP;
   adc.fClkN <= adcFClkN;
   adc.dClkP <= adcDClkP;
   adc.dClkN <= adcDClkN;
   adc.chP   <= adcChP;
   adc.chN   <= adcChN;

   U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
      generic map (TPD_G => TPD_G)
      port map (
         clkIn   => timingRxClk125,
         clkOutP => adcClkP,
         clkOutN => adcClkN);

   U_DataPath_1 : entity warm_tdm.DataPath
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => SIMULATION_G,
         GEN_ADC_FILTER_G => GEN_ADC_FILTER_G,
         ROW_ADDR_BITS_G  => ROW_ADDR_BITS_G,
         NEGATE_ADC_G     => false,
         INVERT_SQ1FB_G   => false,
         AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_DATA_PATH_C).baseAddr,
         SQ1FB_RAM_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_FB_DAC_C).baseAddr,
         IODELAY_GROUP_G  => "IODELAY0")
      port map (
         adc              => adc,
         timingRxClk125   => timingRxClk125,
         timingRxRst125   => timingRxRst125,
         timingRxData     => timingRxData,
         sq1FbDacs        => sq1FbDacs,
         axisClk          => axisClk,
         axisRst          => axisRst,
         axisMaster       => dataTxAxisMaster,
         axisSlave        => dataTxAxisSlave,
         axilClk          => axilClk,
         axilRst          => axilRst,
         adcFilterEn      => adcFilterEn,
         sAxilReadMaster  => locAxilReadMasters(AXIL_DATA_PATH_C),
         sAxilReadSlave   => locAxilReadSlaves(AXIL_DATA_PATH_C),
         sAxilWriteMaster => locAxilWriteMasters(AXIL_DATA_PATH_C),
         sAxilWriteSlave  => locAxilWriteSlaves(AXIL_DATA_PATH_C),
         mAxilReadMaster  => sq1FbAxilReadMaster,
         mAxilReadSlave   => sq1FbAxilReadSlave,
         mAxilWriteMaster => sq1FbAxilWriteMaster,
         mAxilWriteSlave  => sq1FbAxilWriteSlave);

   U_FastDacDriver_SQ1_BIAS : entity warm_tdm.FastDacDriver
      generic map (TPD_G => TPD_G, SIMULATION_G => SIMULATION_G,
                   AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_BIAS_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125, timingRxRst125 => timingRxRst125,
         timingRxData    => timingRxData,
         dacDb => sq1BiasDb, dacWrt => sq1BiasWrt, dacClk => sq1BiasClk,
         dacSel => sq1BiasSel, dacReset => sq1BiasReset,
         axilClk => axilClk, axilRst => axilRst,
         axilWriteMaster => locAxilWriteMasters(AXIL_SQ1_BIAS_DAC_C),
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SQ1_BIAS_DAC_C),
         axilReadMaster  => locAxilReadMasters(AXIL_SQ1_BIAS_DAC_C),
         axilReadSlave   => locAxilReadSlaves(AXIL_SQ1_BIAS_DAC_C));

   U_FastDacDriver_SQ1_FB : entity warm_tdm.FastDacDriver
      generic map (TPD_G => TPD_G, SIMULATION_G => SIMULATION_G,
                   AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SQ1_FB_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125, timingRxRst125 => timingRxRst125,
         timingRxData    => timingRxData, dacOut => sq1FbDacs,
         dacDb => sq1FbDb, dacWrt => sq1FbWrt, dacClk => sq1FbClk,
         dacSel => sq1FbSel, dacReset => sq1FbReset,
         axilClk => axilClk, axilRst => axilRst,
         axilWriteMaster => locAxilWriteMasters(AXIL_SQ1_FB_DAC_C),
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SQ1_FB_DAC_C),
         axilReadMaster  => locAxilReadMasters(AXIL_SQ1_FB_DAC_C),
         axilReadSlave   => locAxilReadSlaves(AXIL_SQ1_FB_DAC_C));

   U_FastDacDriver_SA_FB : entity warm_tdm.FastDacDriver
      generic map (TPD_G => TPD_G, SIMULATION_G => SIMULATION_G,
                   AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_SA_FB_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125, timingRxRst125 => timingRxRst125,
         timingRxData    => timingRxData,
         dacDb => saFbDb, dacWrt => saFbWrt, dacClk => saFbClk,
         dacSel => saFbSel, dacReset => saFbReset,
         axilClk => axilClk, axilRst => axilRst,
         axilWriteMaster => locAxilWriteMasters(AXIL_SA_FB_DAC_C),
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SA_FB_DAC_C),
         axilReadMaster  => locAxilReadMasters(AXIL_SA_FB_DAC_C),
         axilReadSlave   => locAxilReadSlaves(AXIL_SA_FB_DAC_C));

   U_FastDacDriver_AUX : entity warm_tdm.FastDacDriver
      generic map (TPD_G => TPD_G, SIMULATION_G => SIMULATION_G,
                   AXIL_BASE_ADDR_G => AXIL_XBAR_CFG_C(AXIL_AUX_DAC_C).baseAddr)
      port map (
         timingRxClk125  => timingRxClk125, timingRxRst125 => timingRxRst125,
         timingRxData    => timingRxData,
         dacDb => auxDb, dacWrt => auxWrt, dacClk => auxClk,
         dacSel => auxSel, dacReset => auxReset,
         axilClk => axilClk, axilRst => axilRst,
         axilWriteMaster => locAxilWriteMasters(AXIL_AUX_DAC_C),
         axilWriteSlave  => locAxilWriteSlaves(AXIL_AUX_DAC_C),
         axilReadMaster  => locAxilReadMasters(AXIL_AUX_DAC_C),
         axilReadSlave   => locAxilReadSlaves(AXIL_AUX_DAC_C));

   -- Unused I2C slave port
   locAxilReadSlaves(AXIL_FE_I2C_C)  <= AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
   locAxilWriteSlaves(AXIL_FE_I2C_C) <= AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;

   fePwrSyncA <= '0';
   fePwrSyncB <= '0';
   lemoOut    <= "00";

end architecture rtl;
