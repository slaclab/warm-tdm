-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Collect receive pressure and broadcast local-injection pause.
-- All ports use pgpClk with an active-high synchronous reset. Registered
-- collection and broadcast form separate open chains; transit remains enabled.
-- Startup and invalid ring status inhibit injection until health is qualified.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be copied, modified, propagated,
-- or distributed except according to the terms contained in LICENSE.txt.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library surf;
use surf.StdRtlPkg.all;

entity PgpRingFlowControl is
   generic (
      TPD_G            : time     := 1 ns;
      RING_ADDR_0_G    : boolean  := false;
      QUALIFY_CYCLES_G : positive := 4096);
   port (
      -- PGP clock domain
      pgpClk         : in  sl;
      pgpRst         : in  sl;

      -- One pressure bit per VC. remotePause is the predecessor's collection,
      -- carried in PGP status; remoteLinkData carries its broadcast and health.
      rxLinkGood     : in  sl;
      txLinkGood     : in  sl;
      localPause     : in  slv(1 downto 0);
      remotePause    : in  slv(1 downto 0);
      remoteLinkData : in  slv(7 downto 0);

      -- Registered ring status and local admission control
      collectPause   : out slv(1 downto 0);
      txLinkData     : out slv(7 downto 0);
      injectionPause : out slv(1 downto 0);
      address        : out slv(2 downto 0));
end entity PgpRingFlowControl;

architecture rtl of PgpRingFlowControl is

   -- Link-data encoding, regenerated at each hop:
   --   7    : this node implements ring flow control
   --   6    : healthy chain from the coordinator through this node
   --   5    : coordinator has qualified the ring; broadcast is valid
   --   4:3  : broadcast pause for VC1:VC0
   --   2:0  : this node's ring address
   -- Collection travels separately in collectPause. Only local injection is
   -- gated by injectionPause; already admitted transit traffic must drain.
   type RegType is record
      qualify        : natural range 0 to QUALIFY_CYCLES_G;
      txLinkData     : slv(7 downto 0);
      collectPause   : slv(1 downto 0);
      injectionPause : slv(1 downto 0);
   end record;
   -- x98 advertises protocol support, but no health/validity, and pauses both
   -- VCs. The same conservative defaults apply while a link is unqualified.
   constant REG_INIT_C : RegType := (
      qualify        => 0,
      txLinkData     => x"98",
      collectPause   => "11",
      injectionPause => "11");
   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

begin

   comb : process(all) is
      variable v       : RegType;
      variable healthy : sl;
   begin
      v := r;

      -- Rebuild status on every cycle so a failed health/validity check cannot
      -- retain an earlier permission to inject. Only qualification persists.
      v.txLinkData     := x"98";
      v.injectionPause := "11";
      v.collectPause   := localPause;
      healthy          := rxLinkGood and txLinkGood;

      if RING_ADDR_0_G then
         -- The coordinator opens the collection chain: start with local
         -- pressure only, then use the returning OR in the broadcast below.
         -- Feeding remotePause into collectPause here would latch any pause
         -- around the ring even after every receiver had drained.
         v.txLinkData(2 downto 0) := "000";
         -- Seed health independently of returning broadcast validity. Requiring
         -- validity here would prevent an all-reset ring from ever starting.
         v.txLinkData(6) := healthy;
         if healthy = '1' and remoteLinkData(7 downto 6) = "11" then
            -- Require a continuous healthy return for QUALIFY_CYCLES_G pgpClk
            -- cycles, allowing address/status to settle around the ring. The
            -- counter saturates; a broken or incompatible chain restarts it.
            if r.qualify < QUALIFY_CYCLES_G then
               v.qualify := r.qualify + 1;
            else
               v.txLinkData(5)          := '1';
               v.txLinkData(4 downto 3) := localPause or remotePause;
               v.injectionPause         := localPause or remotePause;
            end if;
         else
            v.qualify := 0;
         end if;
      else
         -- Addressing follows physical ring order (three-bit modulo-eight
         -- increment). Each follower extends the health and collection chains.
         v.txLinkData(2 downto 0) := slv(unsigned(remoteLinkData(2 downto 0)) + 1);
         healthy                  := healthy and remoteLinkData(7) and remoteLinkData(6);
         v.txLinkData(6)          := healthy;
         v.collectPause           := localPause or remotePause;
         if healthy = '1' and remoteLinkData(5) = '1' then
            -- Relay the coordinator's broadcast unchanged. Its deassertion
            -- must reach this node before the broadcast can release injection.
            v.txLinkData(5 downto 3) := remoteLinkData(5 downto 3);
            -- Collection pressure stops injection before waiting for another
            -- trip through the coordinator. Never OR broadcast into collection:
            -- keeping the two chains separate is what lets pressure clear.
            v.injectionPause := localPause or remotePause or remoteLinkData(4 downto 3);
         end if;
      end if;
      if healthy /= '1' then
         -- Propagate pressure as well as invalid health downstream, including
         -- when a predecessor does not advertise this protocol.
         v.collectPause := "11";
      end if;

      if pgpRst = '1' then
         v := REG_INIT_C;
      end if;
      -- Status, address and admission change together after a pgpClk edge.
      -- PgpCore provides the CDC for consumers in the application clock domain.
      rin            <= v;
      txLinkData     <= r.txLinkData;
      address        <= r.txLinkData(2 downto 0);
      collectPause   <= r.collectPause;
      injectionPause <= r.injectionPause;
   end process;

   seq : process(pgpClk) is
   begin
      if rising_edge(pgpClk) then
         r <= rin after TPD_G;
      end if;
   end process;

end architecture rtl;
