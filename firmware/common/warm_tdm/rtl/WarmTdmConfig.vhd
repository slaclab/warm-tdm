-------------------------------------------------------------------------------
-- Title      : Warm TDM Configuration Registers
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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.WarmTdmPkg.all;

entity WarmTdmConfig is

   generic (
      TPD_G           : time    := 1 ns;
      SIMULATION_G    : boolean := false;
      AXIL_CLK_FREQ_G : real    := 125.0e6);
   port (
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;

      -- Status inputs
      timingRxClkLocked : in sl;

      -- Output ports
      tempAlertL  : in  sl;
      ledEn       : out sl              := '1';
      anaPwrEn    : out sl              := '1';
      asicResetB  : out sl;
      ampPdB      : out slv(7 downto 0) := (others => '1');
      adcFilterEn : out slv(7 downto 0) := (others => '0')

      );

end entity WarmTdmConfig;

architecture rtl of WarmTdmConfig is

   type RegType is record
      anaPwrEn       : sl;
      anaPwrEnAxi    : sl;
      asicReset      : sl;
      adcFilterEn    : slv(7 downto 0);
      ledEn          : sl;
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record;

   constant REG_INIT_C : RegType := (
      anaPwrEn       => '0',
      anaPwrEnAxi    => '1',
      asicReset      => '1',
      adcFilterEn    => (others => '0'),
      ledEn          => '1',
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal timingRxClkLockedSync : sl;

begin

   U_Synchronizer_1 : entity surf.Synchronizer
      generic map (
         TPD_G => TPD_G)
      port map (
         clk     => axilClk,                 -- [in]
         rst     => axilRst,                 -- [in]
         dataIn  => timingRxClkLocked,       -- [in]
         dataOut => timingRxClkLockedSync);  -- [out]

   -------------------------------------------------------------------------------------------------
   -- Reset ASIC at startup
   -------------------------------------------------------------------------------------------------
--    U_PwrUpRst_1 : entity surf.PwrUpRst
--       generic map (
--          TPD_G          => TPD_G,
--          SIM_SPEEDUP_G  => SIMULATION_G,
--          OUT_POLARITY_G => '0',
-- --         USE_DSP_G      => USE_DSP_G,
--          DURATION_G     => ite(SIMULATION_G, 1250, 5*125000000))
--       port map (
--          arst   => r.asicReset,         -- [in]
--          clk    => axilClk,             -- [in]
--          rstOut => asicResetB);         -- [out]


   comb : process (axilReadMaster, axilRst, axilWriteMaster, r, tempAlertL, timingRxClkLockedSync) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.anaPwrEnAxi);
      axiSlaveRegisterR(axilEp, X"00", 1, r.anaPwrEn);
      axiSlaveRegister(axilEp, X"14", 0, v.ledEn);
      axiSlaveRegisterR(axilEp, X"18", 0, tempAlertL);
      axiSlaveRegister(axilEp, X"20", 0, v.asicReset);
      axiSlaveRegister(axilEp, X"24", 0, v.adcFilterEn);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      -- Turn on analog power on startup once rx clock is locked
      if (r.anaPwrEn = '0' and r.anaPwrEnAxi = '1' and timingRxClkLockedSync = '1') then
         v.anaPwrEn := '1';
      end if;

      if (r.anaPwrEnAxi = '0') then
         v.anaPwrEn := '0';
      end if;

      if (axilRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      axilWriteSlave <= r.axilWriteSlave;
      axilReadSlave  <= r.axilReadSlave;

      ledEn       <= r.ledEn;
      anaPwrEn    <= r.anaPwrEn;
      adcFilterEn <= r.adcFilterEn;

   end process;

   seq : process (axilClk) is
   begin
      if (rising_edge(axilClk)) then
         r <= rin after TPD_G;
      end if;
   end process;

   asicResetB <= '0' when r.asicReset = '1' else 'Z';

end architecture rtl;
