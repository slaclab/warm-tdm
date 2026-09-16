-------------------------------------------------------------------------------
-- Title      : AdcAccumulator+AdcDsp cocotb compare wrapper (bit-exact golden)
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Standard   : VHDL'08
-------------------------------------------------------------------------------
-- Description:
-- Stage-2 wrapper for the whole-path bit-exact re-qualification of the
-- accumulator split (docs/plans/pid-cosim-verification/). It instantiates the
-- CURRENT post-split datapath -- AdcAccumulator -> AdcDsp -- exactly as
-- DataPath.vhd wires them, behind the SAME flattened cocotb port set as the
-- pre-split capture wrapper (AdcDspPresplitCaptureWrapper). Driving both with the
-- shared stimulus (tests/warm_tdm/adc_dsp/_pid_bitexact.py) and comparing the
-- captured mAxil SQ1-FB-DAC write transactions proves the split preserved
-- behavior bit-for-bit.
--
-- The raw ADC stream + timing + sq1FbDac feed AdcAccumulator; its accumOut/
-- accumValid feed AdcDsp. The AdcAccumulator baseline RAM AXI-Lite port is left
-- unconnected so the baseline stays at its 0 reset default (matching the capture
-- bench, which also leaves the pre-split baseline RAM at 0); the external S_AXIL
-- bus configures AdcDsp's PID coefficients only. AdcDsp is built with
-- SIMULATION_G => true so its stream FIFOs infer under GHDL.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be copied, modified, propagated,
-- or distributed except according to the terms contained in the LICENSE.txt file.
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

entity AdcDspAccumCompareWrapper is
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

      -- Raw ADC sample stream: one 14-bit sample left-justified in tData(15:2)
      ADC_TDATA  : in slv(15 downto 0) := (others => '0');
      ADC_TVALID : in sl               := '0';

      -- Delayed SQ1 feedback DAC code (offset binary)
      SQ1FB_DAC : in slv(13 downto 0) := (others => '0');

      -- Real PID-debug FIFO output, consumed without backpressure.
      DEBUG_TDATA  : out slv(63 downto 0);
      DEBUG_TVALID : out sl;
      DEBUG_TLAST  : out sl;
      DEBUG_TKEEP  : out slv(7 downto 0);

      -- Unfiltered reconstructed feedback (signed integer DAC-code units).
      PID_TDATA  : out slv(31 downto 0);
      PID_TVALID : out sl;
      PID_TKEEP  : out slv(3 downto 0);
      PID_TID    : out slv(7 downto 0);

      -- AXI-Lite register bus (flat, driven by cocotbext-axi AxiLiteMaster) ->
      -- AdcDsp PID coefficients.
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
      S_AXIL_RREADY  : in  sl               := '0';

      -- Captured mAxil SQ1-FB-DAC write transactions (the observable)
      DAC_WR_VALID : out sl;
      DAC_WR_ADDR  : out slv(7 downto 0);
      DAC_WR_DATA  : out slv(31 downto 0));
end entity AdcDspAccumCompareWrapper;

architecture rtl of AdcDspAccumCompareWrapper is

   signal timingRxData : LocalTimingType := LOCAL_TIMING_INIT_C;

   signal accumResult : AdcAccumResultType := ADC_ACCUM_RESULT_INIT_C;
   signal accumValid  : sl                 := '0';

   signal axisReady : AxiStreamSlaveType := AXI_STREAM_SLAVE_FORCE_C;
   signal debugMaster : AxiStreamMasterType;
   signal pidMaster : AxiStreamMasterType;

   signal axilClk         : sl;
   signal axilRst         : sl;
   signal axilReadMaster  : AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
   signal axilReadSlave   : AxiLiteReadSlaveType   := AXI_LITE_READ_SLAVE_INIT_C;
   signal axilWriteMaster : AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
   signal axilWriteSlave  : AxiLiteWriteSlaveType  := AXI_LITE_WRITE_SLAVE_INIT_C;

   -- AdcAccumulator baseline-RAM AXI-Lite left idle (baseline stays 0).
   signal accumAxilReadMaster  : AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
   signal accumAxilReadSlave   : AxiLiteReadSlaveType;
   signal accumAxilWriteMaster : AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
   signal accumAxilWriteSlave  : AxiLiteWriteSlaveType;

   signal sq1FbReadMaster  : AxiLiteReadMasterType  := AXI_LITE_READ_MASTER_INIT_C;
   signal sq1FbReadSlave   : AxiLiteReadSlaveType   := AXI_LITE_READ_SLAVE_INIT_C;
   signal sq1FbWriteMaster : AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
   signal sq1FbWriteSlave  : AxiLiteWriteSlaveType  := AXI_LITE_WRITE_SLAVE_INIT_C;

begin

   DEBUG_TDATA  <= debugMaster.tData(63 downto 0);
   DEBUG_TVALID <= debugMaster.tValid;
   DEBUG_TLAST  <= debugMaster.tLast;
   DEBUG_TKEEP  <= debugMaster.tKeep(7 downto 0);
   PID_TDATA  <= pidMaster.tData(31 downto 0);
   PID_TVALID <= pidMaster.tValid;
   PID_TKEEP  <= pidMaster.tKeep(3 downto 0);
   PID_TID    <= pidMaster.tId(7 downto 0);

   ----------------------------------------------------------------------------
   -- AXI-Lite shim: flat AXI -> surf record (drives AdcDsp coefficients)
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
   -- Decoded timing view (shared by accumulator and DSP, as in DataPath)
   ----------------------------------------------------------------------------
   timingRxData <= toLocalTimingType(TIMING_RX_DATA);

   ----------------------------------------------------------------------------
   -- Current ADC accumulation front-end
   ----------------------------------------------------------------------------
   U_AdcAccumulator : entity warm_tdm.AdcAccumulator
      generic map (
         TPD_G           => TPD_G,
         SIMULATION_G    => true,
         ROW_ADDR_BITS_G => ROW_ADDR_BITS_G)
      port map (
         clk             => clk,
         rst             => rst,
         timingRxData    => timingRxData,
         adcValid        => ADC_TVALID,
         adcData         => ADC_TDATA,
         sq1FbDac        => SQ1FB_DAC,
         accumOut        => accumResult,
         accumValid      => accumValid,
         axilReadMaster  => accumAxilReadMaster,
         axilReadSlave   => accumAxilReadSlave,
         axilWriteMaster => accumAxilWriteMaster,
         axilWriteSlave  => accumAxilWriteSlave);

   ----------------------------------------------------------------------------
   -- Internal SQ1 feedback RAM sink for the DAC-write AXI-Lite master; its
   -- decoded write sideband is the captured observable.
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
         axiWrValid     => DAC_WR_VALID,
         axiWrStrobe    => open,
         axiWrAddr      => DAC_WR_ADDR,
         axiWrData      => DAC_WR_DATA);

   ----------------------------------------------------------------------------
   -- Current fixed-point PID core (consumes the decoded accumulation)
   ----------------------------------------------------------------------------
   U_DUT : entity warm_tdm.AdcDsp
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
         accumIn          => accumResult,
         accumValid       => accumValid,
         sAxilReadMaster  => axilReadMaster,
         sAxilReadSlave   => axilReadSlave,
         sAxilWriteMaster => axilWriteMaster,
         sAxilWriteSlave  => axilWriteSlave,
         mAxilReadMaster  => sq1FbReadMaster,
         mAxilReadSlave   => sq1FbReadSlave,
         mAxilWriteMaster => sq1FbWriteMaster,
         mAxilWriteSlave  => sq1FbWriteSlave,
         pidStreamMaster  => pidMaster,
         pidStreamSlave   => axisReady,
         axisClk          => clk,
         axisRst          => rst,
         pidDebugMaster   => debugMaster,
         pidDebugSlave    => axisReady);

end architecture rtl;
