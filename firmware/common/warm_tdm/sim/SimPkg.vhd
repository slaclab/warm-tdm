-------------------------------------------------------------------------------
-- Title      : 
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

library surf;
use surf.StdRtlPkg.all;

package SimPkg is

   -- Open-circuit voltage and series impedance of one single-ended source.
   -- This was historically named CurrentType even though it represents a
   -- Thevenin source.  Keep the legacy subtype names for existing models.
   type TheveninSourceType is record
      voltage   : real;
      impedance : real;
   end record TheveninSourceType;

   type TheveninSourceArray is array (natural range <>) of TheveninSourceType;

   subtype CurrentType is TheveninSourceType;
   subtype CurrentArray is TheveninSourceArray;

   type DifferentialSourceType is record
      p : TheveninSourceType;
      n : TheveninSourceType;
   end record DifferentialSourceType;

   type DifferentialSourceArray is array (natural range <>) of
      DifferentialSourceType;

   -- A differential pair whose terminal values are already currents or
   -- voltages.  The surrounding interface documents which SI unit applies.
   type DifferentialRealType is record
      p : real;
      n : real;
   end record DifferentialRealType;

   type DifferentialRealArray is array (natural range <>) of
      DifferentialRealType;

   type ColumnCryoDriveType is record
      tesBias     : DifferentialRealType;
      ssaBias     : DifferentialSourceType;
      ssaFeedback : DifferentialSourceType;
      sq1Bias     : DifferentialSourceType;
      sq1Feedback : DifferentialSourceType;
   end record ColumnCryoDriveType;

   type ColumnCryoDriveArray is array (natural range <>) of
      ColumnCryoDriveType;

   type ColumnCryoSenseType is record
      ssaVoltage : DifferentialRealType;
   end record ColumnCryoSenseType;

   type ColumnCryoSenseArray is array (natural range <>) of
      ColumnCryoSenseType;

   constant ZERO_THEVENIN_SOURCE_C : TheveninSourceType :=
      (voltage => 0.0, impedance => 0.0);
   constant ZERO_DIFFERENTIAL_SOURCE_C : DifferentialSourceType :=
      (p => ZERO_THEVENIN_SOURCE_C, n => ZERO_THEVENIN_SOURCE_C);
   constant ZERO_DIFFERENTIAL_REAL_C : DifferentialRealType :=
      (p => 0.0, n => 0.0);
   constant ZERO_COLUMN_CRYO_DRIVE_C : ColumnCryoDriveType := (
      tesBias     => ZERO_DIFFERENTIAL_REAL_C,
      ssaBias     => ZERO_DIFFERENTIAL_SOURCE_C,
      ssaFeedback => ZERO_DIFFERENTIAL_SOURCE_C,
      sq1Bias     => ZERO_DIFFERENTIAL_SOURCE_C,
      sq1Feedback => ZERO_DIFFERENTIAL_SOURCE_C);
   constant ZERO_COLUMN_CRYO_SENSE_C : ColumnCryoSenseType := (
      ssaVoltage => ZERO_DIFFERENTIAL_REAL_C);

   function current (
      c    : CurrentType;
      load : real := 0.0)
      return real;

   function currentDiff (
      p    : CurrentType;
      n    : CurrentType;
      load : real := 0.0)
      return real;

   function currentDiff (
      source : DifferentialSourceType;
      load   : real := 0.0)
      return real;

   function differentialVoltage (
      source : DifferentialSourceType)
      return real;

   function differentialImpedance (
      source : DifferentialSourceType;
      load   : real := 0.0)
      return real;


end package SimPkg;

package body SimPkg is

   function current (
      c    : CurrentType;
      load : real := 0.0)
      return real is
   begin
      return (c.voltage / (c.impedance + load));
   end function current;

   function currentDiff (
      p    : CurrentType;
      n    : CurrentType;
      load : real := 0.0)
      return real is
   begin
      return (p.voltage - n.voltage) / (p.impedance + n.impedance + load);
   end function currentDiff;

   function currentDiff (
      source : DifferentialSourceType;
      load   : real := 0.0)
      return real is
   begin
      return currentDiff(source.p, source.n, load);
   end function currentDiff;

   function differentialVoltage (
      source : DifferentialSourceType)
      return real is
   begin
      return source.p.voltage - source.n.voltage;
   end function differentialVoltage;

   function differentialImpedance (
      source : DifferentialSourceType;
      load   : real := 0.0)
      return real is
   begin
      return source.p.impedance + source.n.impedance + load;
   end function differentialImpedance;

end package body SimPkg;
