-------------------------------------------------------------------------------
-- Title      : ADC Sample Accumulator
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Free-running accumulator front-end for the PID DSP pipeline.
-- Accumulates (ADC - baseline) samples over the timing sample window and
-- outputs a completed result record on lastSample. Operates independently
-- of the downstream PID computation, enabling pipelined row processing.
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

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;

entity AdcAccumulator is
   generic (
      TPD_G           : time    := 1 ns;
      ROW_ADDR_BITS_G : integer := 7);
   port (
      clk             : in  sl;
      rst             : in  sl;
      timingRxData    : in  LocalTimingType;
      adcValid        : in  sl;
      adcData         : in  slv(15 downto 0);
      sq1FbDac        : in  slv(13 downto 0);
      -- Output
      accumOut        : out AdcAccumResultType;
      accumValid      : out sl;
      -- AXI-Lite for baseline RAM
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
end entity AdcAccumulator;

architecture rtl of AdcAccumulator is

   type StateType is (
      IDLE_S,
      WAIT_FIRST_SAMPLE_S,
      ACCUMULATE_S,
      OUTPUT_S);

   type RegType is record
      state      : StateType;
      accumOut   : AdcAccumResultType;
      accumValid : sl;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state      => IDLE_S,
      accumOut   => ADC_ACCUM_RESULT_INIT_C,
      accumValid => '0');

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal baselineRamOut : slv(15 downto 0);

begin

   U_AxiDualPortRam_Baseline : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "xpm",
         MEMORY_TYPE_G    => "block",
         READ_LATENCY_G   => 1,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_G,
         DATA_WIDTH_G     => 16)
      port map (
         axiClk         => clk,              -- [in]
         axiRst         => rst,              -- [in]
         axiReadMaster  => axilReadMaster,   -- [in]
         axiReadSlave   => axilReadSlave,    -- [out]
         axiWriteMaster => axilWriteMaster,  -- [in]
         axiWriteSlave  => axilWriteSlave,   -- [out]
         clk            => clk,              -- [in]
         rst            => rst,              -- [in]
         addr           => timingRxData.rowIndex(ROW_ADDR_BITS_G-1 downto 0),  -- [in]
         dout           => baselineRamOut);   -- [out]

   comb : process (adcData, adcValid, baselineRamOut, r, rst, sq1FbDac, timingRxData) is
      variable v          : RegType;
      variable adcSample  : signed(13 downto 0);
      variable baseline   : signed(13 downto 0);
   begin
      v := r;

      v.accumValid := '0';

      case r.state is
         when IDLE_S =>
            if (timingRxData.rowStrobe = '1') then
               v.accumOut.accumError      := (others => '0');
               v.accumOut.numSamples      := (others => '0');
               v.accumOut.sq1FbDac        := sq1FbDac;
               v.accumOut.seqStart        := timingRxData.rowSeqStart;
               v.accumOut.daqReadoutStart := timingRxData.daqReadoutStart;
               v.state                    := WAIT_FIRST_SAMPLE_S;
            end if;

         when WAIT_FIRST_SAMPLE_S =>
            if (timingRxData.firstSample = '1') then
               v.state := ACCUMULATE_S;
            end if;

         when ACCUMULATE_S =>
            if (adcValid = '1') then
               adcSample := signed(adcData(15 downto 2));
               baseline  := signed(baselineRamOut(15 downto 2));

               v.accumOut.accumError := r.accumOut.accumError + resize(adcSample - baseline, 32);
               v.accumOut.numSamples := r.accumOut.numSamples + 1;

               if (timingRxData.lastSample = '1') then
                  v.state := OUTPUT_S;
               end if;
            end if;

         when OUTPUT_S =>
            v.accumOut.rowIndex := timingRxData.rowIndex;
            v.accumValid        := '1';
            v.state             := IDLE_S;
      end case;

      if (rst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      accumOut   <= r.accumOut;
      accumValid <= r.accumValid;

   end process comb;

   seq : process (clk) is
   begin
      if (rising_edge(clk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
