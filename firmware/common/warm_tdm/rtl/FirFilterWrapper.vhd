-------------------------------------------------------------------------------
-- Title      : FIR Filter Wrapper
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
use surf.AxiStreamPkg.all;

entity FirFilterWrapper is
   generic (
      TPD_G : time := 1 ns);
   port (
      dataClk         : in  sl;
      dataRst         : in  sl;
      sDataAxisMaster : in  AxiStreamMasterType;
      mDataAxisMaster : out AxiStreamMasterType);
end FirFilterWrapper;

architecture rtl of FirFilterWrapper is


   component FirFilter
      port (
         aclk                            : in  sl;
         s_axis_data_tvalid              : in  sl;
         s_axis_data_tready              : out sl;
         s_axis_data_tdata               : in  slv(15 downto 0);
         s_axis_config_tvalid            : in  sl;
         s_axis_config_tready            : out sl;
         s_axis_config_tdata             : in  slv(7 downto 0);
         s_axis_reload_tvalid            : in  sl;
         s_axis_reload_tready            : out sl;
         s_axis_reload_tlast             : in  sl;
         s_axis_reload_tdata             : in  slv(15 downto 0);
         m_axis_data_tvalid              : out sl;
         m_axis_data_tdata               : out slv(15 downto 0);
         event_s_reload_tlast_missing    : out sl;
         event_s_reload_tlast_unexpected : out sl);
   end component;

   signal configAxisMaster : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal configAxisSlave  : AxiStreamSlaveType;
   signal reloadAxisMaster : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal reloadAxisSlave  : AxiStreamSlaveType;


begin


   FirFilterInst : FirFilter
      port map (
         aclk                            => dataClk,
         s_axis_data_tvalid              => sDataAxisMaster.tvalid,
         s_axis_data_tready              => open,
         s_axis_data_tdata               => sDataAxisMaster.tData(15 downto 0),
         s_axis_config_tvalid            => configAxisMaster.tValid,
         s_axis_config_tready            => configAxisSlave.tReady,
         s_axis_config_tdata             => configAxisMaster.tData(7 downto 0),
         s_axis_reload_tvalid            => reloadAxisMaster.tvalid,
         s_axis_reload_tready            => reloadAxisSlave.tReady,
         s_axis_reload_tlast             => reloadAxisMaster.tLast,
         s_axis_reload_tdata             => reloadAxisMaster.tData(15 downto 0),
         m_axis_data_tvalid              => mDataAxisMaster.tvalid,
         m_axis_data_tdata               => mDataAxisMaster.tData(15 downto 0),
         event_s_reload_tlast_missing    => open,
         event_s_reload_tlast_unexpected => open);


end architecture rtl;



-- INST_TAG_END ------ End INSTANTIATION Template ---------
