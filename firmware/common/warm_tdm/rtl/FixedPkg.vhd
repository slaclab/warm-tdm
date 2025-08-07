library ieee;
use ieee.std_logic_1164.all;

package FixedPkg is new ieee.fixed_generic_pkg generic map (
   fixed_round_style => IEEE.fixed_float_types.fixed_truncate,
   fixed_overflow_style => IEEE.fixed_float_types.fixed_saturate,
   fixed_guard_bits => 0);
