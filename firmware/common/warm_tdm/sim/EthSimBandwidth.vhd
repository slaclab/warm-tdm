-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Share one simulated Ethernet payload budget across SRP and data.
-- Instantiate once per direction for a full-duplex link. This models payload
-- throughput, not Ethernet/RSSI packet overhead, latency, or retransmission.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be copied, modified, propagated,
-- or distributed except according to the terms contained in LICENSE.txt.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;

entity EthSimBandwidth is
   generic (
      TPD_G           : time := 1 ns;
      AXIS_CONFIG_G   : AxiStreamConfigType;
      AXIS_CLK_FREQ_G : real;
      PAYLOAD_RATE_G  : real);
   port (
      axisClk      : in  sl;
      axisRst      : in  sl;
      sAxisMasters : in  AxiStreamMasterArray(1 downto 0);
      sAxisSlaves  : out AxiStreamSlaveArray(1 downto 0);
      mAxisMasters : out AxiStreamMasterArray(1 downto 0);
      mAxisSlaves  : in  AxiStreamSlaveArray(1 downto 0));
end entity EthSimBandwidth;

architecture rtl of EthSimBandwidth is

   signal muxMaster  : AxiStreamMasterType;
   signal muxSlave   : AxiStreamSlaveType;
   signal paceMaster : AxiStreamMasterType;
   signal paceSlave  : AxiStreamSlaveType;

begin

   -- EthCore does not transport TID. Use it internally to retain the socket
   -- identity without changing TDEST (which identifies local/remote streams).
   assert AXIS_CONFIG_G.TID_BITS_C = 0
      report "EthSimBandwidth requires an AXI Stream configuration without TID"
      severity failure;

   U_Mux : entity surf.AxiStreamMux
      generic map (
         TPD_G               => TPD_G,
         NUM_SLAVES_G        => 2,
         MODE_G              => "PASSTHROUGH",
         TID_MODE_G          => "INDEXED",
         ILEAVE_EN_G         => true,
         ILEAVE_ON_NOTVALID_G => true,
         ILEAVE_REARB_G      => (512/8)-3,
         REARB_DELAY_G       => false)
      port map (
         axisClk      => axisClk,
         axisRst      => axisRst,
         sAxisMasters => sAxisMasters,
         sAxisSlaves  => sAxisSlaves,
         mAxisMaster  => muxMaster,
         mAxisSlave   => muxSlave);

   U_Pacer : entity surf.RogueTcpStreamPacer
      generic map (
         TPD_G           => TPD_G,
         AXIS_CONFIG_G   => AXIS_CONFIG_G,
         AXIS_CLK_FREQ_G => AXIS_CLK_FREQ_G,
         PAYLOAD_RATE_G  => PAYLOAD_RATE_G)
      port map (
         axisClk     => axisClk,
         axisRst     => axisRst,
         sAxisMaster => muxMaster,
         sAxisSlave  => muxSlave,
         mAxisMaster => paceMaster,
         mAxisSlave  => paceSlave);

   -- Combinational routing leaves the pacer at the final acceptance boundary;
   -- downstream stalls cannot refill an extra queue of already paced beats.
   demux : process (paceMaster, mAxisSlaves) is
      variable masters : AxiStreamMasterArray(1 downto 0);
      variable index   : natural range 0 to 1;
   begin
      index := 0;
      if paceMaster.tId(0) = '1' then
         index := 1;
      end if;
      masters := (others => AXI_STREAM_MASTER_INIT_C);
      masters(index) := paceMaster;
      masters(index).tId := (others => '0');
      mAxisMasters <= masters;
      paceSlave <= mAxisSlaves(index);
   end process demux;

end architecture rtl;
