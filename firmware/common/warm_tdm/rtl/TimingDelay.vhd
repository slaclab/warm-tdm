-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
-------------------------------------------------------------------------------
-- This file is part of . It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of , including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity TimingDelay is

   generic (
      TPD_G   : time    := 1 ns;
      DELAY_G : integer := 20);

   port (
      clk             : in  sl;
      rst             : in  sl;
      timingIn        : in  LocalTimingType;
      timingOut       : out LocalTimingType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C
      );

end entity TimingDelay;

architecture rtl of TimingDelay is

   signal slvIn  : slv(TIMING_NUM_BITS_C -1 downto 0);
   signal slvOut : slv(TIMING_NUM_BITS_C-1 downto 0);

   type RegType is record
      delay          : slv(6 downto 0);
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record;

   constant REG_INIT_C : RegType := (
      delay          => toSlv(DELAY_G, 7),
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

begin

   comb : process (axilReadMaster, axilWriteMaster, r, rst) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.delay);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      if (rst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      axilReadSlave  <= r.axilReadSlave;
      axilWriteSlave <= r.axilWriteSlave;

   end process;


   seq : process (clk) is
   begin
      if (rising_edge(clk)) then
         r <= rin after TPD_G;
      end if;
   end process;

   slvIn <= toSlv(timingIn);

   U_SlvDelay_1 : entity surf.SlvDelay
      generic map (
         TPD_G        => TPD_G,
         SRL_EN_G     => true,
         DELAY_G      => 128,
         REG_OUTPUT_G => true,
         WIDTH_G      => TIMING_NUM_BITS_C)
      port map (
         clk   => clk,                  -- [in]
--         rst   => rst,                  -- [in]
         en    => '1',                  -- [in]
         delay => r.delay,              -- [in]
         din   => slvIn,                -- [in]
         dout  => slvOut);              -- [out]

--    U_SlvFixedDelay_1 : entity surf.SlvFixedDelay
--       generic map (
--          TPD_G         => TPD_G,
--          XIL_DEVICE_G  => "7SERIES",
--          DELAY_STYLE_G => "srl",
--          DELAY_G       => DELAY_G,
--          WIDTH_G       => TIMING_NUM_BITS_C)
--       port map (
--          clk  => clk,                   -- [in]
--          din  => slvIn,                 -- [in]
--          dout => slvOut);               -- [out]

   timingout <= toLocalTimingType(slvOut);

end architecture rtl;
