-------------------------------------------------------------------------------
-- Title      : CommonModeFilter 
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiLitePkg.all;
use surf.Ad9681Pkg.all;

entity CommonModeFilter is

   generic (
      TPD_G : time := 1 ns);
   port (
      -- Timing interface
      adcClk : in sl;
      adcRst : in sl;

      -- Adc Input Streams
      adcInStreams : in AxiStreamMasterArray(7 downto 0);

      -- Filtered Output Streams
      adcOutStreams : out AxiStreamMasterArray(7 downto 0);

      -- Local register access
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

end entity CommonModeFilter;

architecture rtl of CommonModeFilter is

begin

   comb : process (r) is
   begin

      ----------------------------------------------------------------------------------------------
      -- Compute the pedastal for each channel
      ----------------------------------------------------------------------------------------------
      if adcInStreams(0).tValid = '1' then
         for i in 7 downto 0 loop
            average      := signed(r.average(i));
            avgDiv       := shift_right(average, 8);
            sample       := signed(adcInStreams(i).tData(15 downto 0));
            sample       := shift_left(sample, 16-8);
            average      := average - avgDiv + sample;
            v.average(i) := slv(average);
         end loop;
      end if;

      ----------------------------------------------------------------------------------------------
      -- Subtract the pedastal
      ----------------------------------------------------------------------------------------------
      v.adcDlyPed(0).tValid := '0';
      if adcInStreams(0).tValid = '1' then
         for i in 7 downto 0 loop
            sample                  := signed(adcInStreams(i).tData(15 downto 0));
            v.pedastalSubtracted(i) := sample - shift_right(r.average(i), 16);
            v.adcDlyPed(i)          := adcInStreams(i);
            v.adcDlyPed(i).tValid   := '1';
         end loop;
      end if;

      ----------------------------------------------------------------------------------------------
      -- Compute the common mode signal
      ----------------------------------------------------------------------------------------------
      v.adcDlyCom(0).tvalid := '0';
      if (r.adcDlyPed(0).tvalid = '1') then
         v.commonMode := (others => '0');
         for i in 7 downto 0 loop
            v.commonMode := v.commonMode + shift_right(r.pedastalSubtracted(i), 3);
         end loop;
         v.adcDlyCom(i)        := r.adcDlyPed(i);
         v.adcDlyCom(i).tvalid := '1';
      end if;

      ----------------------------------------------------------------------------------------
      -- Subtract common mode from delayed signals
      ----------------------------------------------------------------------------------------
      if (r.adcDlyCom(0).tValid = '1') then
         for i in 7 downto 0 loop
            v.adcOut(i)                    := r.adcDlyCom(i);  -- initial value
            sample                         := signed(r.adcDlyCom(i).tData(15 downto 0));
            v.adcOut(i).tData(15 downto 0) := slv(sample - r.commonMode);
         end loop;
      end if;



   end process comb;

end architecture rtl;
