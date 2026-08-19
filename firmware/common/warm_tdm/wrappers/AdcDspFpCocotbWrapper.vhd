-------------------------------------------------------------------------------
-- Title      : AdcDspFp cocotb wrapper (floating-point PID)
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'08
-------------------------------------------------------------------------------
-- Description:
-- Thin cocotb-facing wrapper for the floating-point AdcDspFp entity.
--
-- Structurally identical to AdcDspCocotbWrapper (same flattened accumIn /
-- accumValid / timingRxData interface), but instantiates AdcDspFp instead of
-- AdcDsp.
--
-- IMPORTANT: AdcDspFp instantiates the Xilinx FpMac, Int2Fp and Fp2Int IEEE-754
-- IP cores. GHDL cannot elaborate those primitives, so this wrapper is NOT
-- runnable under the GHDL cocotb flow -- it is intended for a Vivado XSIM
-- cosim run (XSIM can model the Xilinx FP IP). `ghdl -a` still analyzes this
-- wrapper and AdcDspFp cleanly because the IP cores are referenced through
-- VHDL `component` declarations (bound only at elaboration time). See
-- docs/_meta/rtl_regression_handoff.md for the XSIM-via-surf-cosim path.
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
use ieee.numeric_std.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;
use surf.AxiStreamPkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;

entity AdcDspFpCocotbWrapper is
   generic (
      TPD_G            : time                 := 1 ns;
      INVERT_SQ1FB_G   : boolean              := true;
      COLUMN_NUM_G     : integer range 0 to 7 := 0;
      ROW_ADDR_BITS_G  : integer range 3 to 8 := 7;
      AXIL_BASE_ADDR_G : slv(31 downto 0)     := (others => '0');
      SQ1FB_RAM_ADDR_G : slv(31 downto 0)     := (others => '0'));
   port (
      clk : in sl;
      rst : in sl;

      -- Flattened LocalTimingType (see TimingPkg.toLocalTimingType)
      TIMING_RX_DATA : in slv(TIMING_NUM_BITS_C-1 downto 0) := (others => '0');

      -- Flattened AdcAccumResultType + valid strobe
      ACCUM_VALID             : in sl               := '0';
      ACCUM_ERROR             : in slv(31 downto 0)  := (others => '0');
      ACCUM_NUM_SAMPLES       : in slv(7 downto 0)   := (others => '0');
      ACCUM_ROW_INDEX         : in slv(7 downto 0)   := (others => '0');
      ACCUM_SQ1FB_DAC         : in slv(13 downto 0)  := (others => '0');
      ACCUM_SEQ_START         : in sl               := '0';
      ACCUM_DAQ_READOUT_START : in sl               := '0';

      -- AXI-Lite register bus (flat, driven by cocotbext-axi AxiLiteMaster)
      S_AXIL_AWADDR  : in  slv(15 downto 0) := (others => '0');
      S_AXIL_AWPROT  : in  slv(2 downto 0)  := (others => '0');
      S_AXIL_AWVALID : in  sl               := '0';
      S_AXIL_AWREADY : out sl;
      S_AXIL_WDATA   : in  slv(31 downto 0) := (others => '0');
      S_AXIL_WSTRB   : in  slv(3 downto 0)  := (others => '0');
      S_AXIL_WVALID  : in  sl               := '0';
      S_AXIL_WREADY  : out sl;
      S_AXIL_BRESP   : out slv(1 downto 0);
      S_AXIL_BVALID  : out sl;
      S_AXIL_BREADY  : in  sl               := '0';
      S_AXIL_ARADDR  : in  slv(15 downto 0) := (others => '0');
      S_AXIL_ARPROT  : in  slv(2 downto 0)  := (others => '0');
      S_AXIL_ARVALID : in  sl               := '0';
      S_AXIL_ARREADY : out sl;
      S_AXIL_RDATA   : out slv(31 downto 0);
      S_AXIL_RRESP   : out slv(1 downto 0);
      S_AXIL_RVALID  : out sl;
      S_AXIL_RREADY  : in  sl               := '0');
end entity AdcDspFpCocotbWrapper;

architecture rtl of AdcDspFpCocotbWrapper is

   signal timingRxData : LocalTimingType    := LOCAL_TIMING_INIT_C;
   signal accumIn      : AdcAccumResultType  := ADC_ACCUM_RESULT_INIT_C;

   signal axisReady : AxiStreamSlaveType := AXI_STREAM_SLAVE_FORCE_C;

   signal axilClk         : sl;
   signal axilRst         : sl;
   signal axilReadMaster  : AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
   signal axilReadSlave   : AxiLiteReadSlaveType   := AXI_LITE_READ_SLAVE_INIT_C;
   signal axilWriteMaster : AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
   signal axilWriteSlave  : AxiLiteWriteSlaveType  := AXI_LITE_WRITE_SLAVE_INIT_C;

   signal sq1FbReadMaster  : AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
   signal sq1FbReadSlave   : AxiLiteReadSlaveType   := AXI_LITE_READ_SLAVE_INIT_C;
   signal sq1FbWriteMaster : AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
   signal sq1FbWriteSlave  : AxiLiteWriteSlaveType  := AXI_LITE_WRITE_SLAVE_INIT_C;

begin

   ----------------------------------------------------------------------------
   -- AXI-Lite shim: flat AXI -> surf record
   ----------------------------------------------------------------------------
   U_SAxilShim : entity surf.SlaveAxiLiteIpIntegrator
      generic map (
         EN_ERROR_RESP => true,
         HAS_WSTRB     => 1,
         FREQ_HZ       => 125000000,
         ADDR_WIDTH    => 16)
      port map (
         S_AXI_ACLK      => clk,
         S_AXI_ARESETN   => not rst,
         S_AXI_AWADDR    => S_AXIL_AWADDR,
         S_AXI_AWPROT    => S_AXIL_AWPROT,
         S_AXI_AWVALID   => S_AXIL_AWVALID,
         S_AXI_AWREADY   => S_AXIL_AWREADY,
         S_AXI_WDATA     => S_AXIL_WDATA,
         S_AXI_WSTRB     => S_AXIL_WSTRB,
         S_AXI_WVALID    => S_AXIL_WVALID,
         S_AXI_WREADY    => S_AXIL_WREADY,
         S_AXI_BRESP     => S_AXIL_BRESP,
         S_AXI_BVALID    => S_AXIL_BVALID,
         S_AXI_BREADY    => S_AXIL_BREADY,
         S_AXI_ARADDR    => S_AXIL_ARADDR,
         S_AXI_ARPROT    => S_AXIL_ARPROT,
         S_AXI_ARVALID   => S_AXIL_ARVALID,
         S_AXI_ARREADY   => S_AXIL_ARREADY,
         S_AXI_RDATA     => S_AXIL_RDATA,
         S_AXI_RRESP     => S_AXIL_RRESP,
         S_AXI_RVALID    => S_AXIL_RVALID,
         S_AXI_RREADY    => S_AXIL_RREADY,
         axilClk         => axilClk,
         axilRst         => axilRst,
         axilReadMaster  => axilReadMaster,
         axilReadSlave   => axilReadSlave,
         axilWriteMaster => axilWriteMaster,
         axilWriteSlave  => axilWriteSlave);

   ----------------------------------------------------------------------------
   -- Decoded timing and accumulation views
   ----------------------------------------------------------------------------
   timingRxData <= toLocalTimingType(TIMING_RX_DATA);

   accumIn.accumError      <= signed(ACCUM_ERROR);
   accumIn.numSamples      <= unsigned(ACCUM_NUM_SAMPLES);
   accumIn.rowIndex        <= ACCUM_ROW_INDEX;
   accumIn.sq1FbDac        <= ACCUM_SQ1FB_DAC;
   accumIn.seqStart        <= ACCUM_SEQ_START;
   accumIn.daqReadoutStart <= ACCUM_DAQ_READOUT_START;

   ----------------------------------------------------------------------------
   -- Internal SQ1 feedback RAM sink for the DAC-write AXI-Lite master
   ----------------------------------------------------------------------------
   U_Sq1FbSinkRam : entity surf.AxiDualPortRam
      generic map (
         TPD_G          => TPD_G,
         SYNTH_MODE_G   => "inferred",
         MEMORY_TYPE_G  => "distributed",
         READ_LATENCY_G => 1,
         AXI_WR_EN_G    => true,
         SYS_WR_EN_G    => false,
         COMMON_CLK_G   => true,
         ADDR_WIDTH_G   => 8,
         DATA_WIDTH_G   => 32)
      port map (
         axiClk         => clk,
         axiRst         => rst,
         axiReadMaster  => sq1FbReadMaster,
         axiReadSlave   => sq1FbReadSlave,
         axiWriteMaster => sq1FbWriteMaster,
         axiWriteSlave  => sq1FbWriteSlave,
         clk            => clk,
         rst            => rst,
         dout           => open,
         axiWrValid     => open,
         axiWrStrobe    => open,
         axiWrAddr      => open,
         axiWrData      => open);

   ----------------------------------------------------------------------------
   -- DUT hookup (floating-point PID; requires XSIM for FP IP cores)
   ----------------------------------------------------------------------------
   U_DUT : entity warm_tdm.AdcDspFp
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => true,
         INVERT_SQ1FB_G   => INVERT_SQ1FB_G,
         COLUMN_NUM_G     => COLUMN_NUM_G,
         ROW_ADDR_BITS_G  => ROW_ADDR_BITS_G,
         AXIL_BASE_ADDR_G => AXIL_BASE_ADDR_G,
         SQ1FB_RAM_ADDR_G => SQ1FB_RAM_ADDR_G)
      port map (
         timingRxClk125   => clk,
         timingRxRst125   => rst,
         timingRxData     => timingRxData,
         accumIn          => accumIn,
         accumValid       => ACCUM_VALID,
         sAxilReadMaster  => axilReadMaster,
         sAxilReadSlave   => axilReadSlave,
         sAxilWriteMaster => axilWriteMaster,
         sAxilWriteSlave  => axilWriteSlave,
         mAxilReadMaster  => sq1FbReadMaster,
         mAxilReadSlave   => sq1FbReadSlave,
         mAxilWriteMaster => sq1FbWriteMaster,
         mAxilWriteSlave  => sq1FbWriteSlave,
         pidStreamMaster  => open,
         pidStreamSlave   => axisReady,
         axisClk          => clk,
         axisRst          => rst,
         pidDebugMaster   => open,
         pidDebugSlave    => axisReady);

end architecture rtl;
