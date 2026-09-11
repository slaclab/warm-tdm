-------------------------------------------------------------------------------
-- Title      : Warm TDM Support package
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
use ieee.numeric_std.all;


library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;


library warm_tdm;

package WarmTdmPkg is

   constant AXIL_CLK_FREQ_C : real := 125.0E6;

   constant APP_BASE_ADDR_C : slv(31 downto 0) := X"C0000000";

   constant DATA_AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 8, tDestBits => 4, tUserBits => 2);

   --constant SQ1FB_DATA_AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 2, tDestBits => 8);

   -- Data from AdcDsp to filter and downsampler (fixed-point integer, 24-bit)
   constant PID_DATA_AXIS_CFG_C : AxiStreamConfigType := (
      TSTRB_EN_C    => true,
      TDATA_BYTES_C => 3,
      TDEST_BITS_C  => 8,
      TID_BITS_C    => 8,
      TKEEP_MODE_C  => TKEEP_NORMAL_C,
      TUSER_BITS_C  => 8,
      TUSER_MODE_C  => TUSER_NORMAL_C);

   -- Data from AdcDspFp to filter (IEEE 754 float32, 32-bit)
   constant PID_DATA_FP_AXIS_CFG_C : AxiStreamConfigType := (
      TSTRB_EN_C    => true,
      TDATA_BYTES_C => 4,
      TDEST_BITS_C  => 8,
      TID_BITS_C    => 8,
      TKEEP_MODE_C  => TKEEP_NORMAL_C,
      TUSER_BITS_C  => 8,
      TUSER_MODE_C  => TUSER_NORMAL_C);

   constant DOWNSAMPLE_DATA_AXIS_CFG_C : AxiStreamConfigType := (
      TSTRB_EN_C => true,
      TDATA_BYTES_C => 8,
      TDEST_BITS_C => 8,
      TID_BITS_C => 8,
      TKEEP_MODE_C => TKEEP_NORMAL_C,
      TUSER_BITS_C => 8,
      TUSER_MODE_C => TUSER_NORMAL_C);

   type AdcAccumResultType is record
      accumError      : signed(31 downto 0);
      numSamples      : unsigned(7 downto 0);
      rowIndex        : slv(7 downto 0);
      sq1FbDac        : slv(13 downto 0);
      seqStart        : sl;
      daqReadoutStart : sl;
   end record AdcAccumResultType;

   constant ADC_ACCUM_RESULT_INIT_C : AdcAccumResultType := (
      accumError      => (others => '0'),
      numSamples      => (others => '0'),
      rowIndex        => (others => '0'),
      sq1FbDac        => (others => '0'),
      seqStart        => '0',
      daqReadoutStart => '0');

end package;

