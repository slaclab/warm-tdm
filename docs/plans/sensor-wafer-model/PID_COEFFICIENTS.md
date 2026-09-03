# Fixed-Point PID Coefficients for the Sensor-Wafer Simulation

## Scope and conclusion

This note derives starting fixed-point SQ1 feedback-loop coefficients for the
sensor-wafer model in `GroupTb`. It follows the complete static signal path that
is currently modeled:

```text
AdcDsp SQ1FB code
  -> AD9767 DAC
  -> column-FEB SQ1-feedback amplifier and cryogenic load
  -> SQ1/FAS MUX network
  -> SSA
  -> two-stage column-FEB SA signal amplifier
  -> ADA4932 ADC driver
  -> AD9681 conversion
  -> AdcDsp row-window accumulator
```

For the default 128-sample timing window, the recommended first closed-loop
trial is:

| Term | Hardware coefficient | Q1.23 register value |
| --- | ---: | ---: |
| P | `0.0009765625` (`2^-10`) | 8192 |
| I | `0.0001220703125` (`2^-13`) | 1024 |
| D | 0 | 0 |

These values assume the tuning procedures put the loop on the expected branch,
where the local plant slope is negative. They are deliberately starting values,
not calibrated constants. The authoritative coefficients should be calculated
from a small end-to-end perturbation around the tuned operating point.

## Important limitation: there is no useful reset operating point

`GroupTb` supplies model and timing defaults, but reset does not establish a
tuned SQUID operating point. The small-signal gain depends on:

- SSA and SQ1 bias currents;
- SSA and SQ1 feedback phases;
- which row and, for a two-level MUX, which bank is selected;
- the local slope selected by SA/SQ1 tuning; and
- the ADC baseline and offset.

Consequently there is no unique PID coefficient at reset. The values above use
a representative selected-row, tuned-slope operating point and the default
synthetic device parameters. They must be verified after simulated tuning.

The ideal low-inductance SQUID equation also has a sharp onset where
`abs(Ibias) = Ic(phi)`. Its mathematical slope becomes singular at that boundary.
A tuning algorithm that chooses the numerically largest slope can therefore
land on a discretization-dependent model cusp. PID identification should use a
finite central difference over several DAC codes and should reject points that
cross this boundary.

## Fixed-point controller implemented by `AdcDsp`

During each row visit, `AdcDsp` forms the sum

```text
E[k] = sum(adc_sample - baseline), over N samples
```

and calculates

```text
delta_u[k] = P * E[k] + I * S[k]
u[k+1]     = u[k] + delta_u[k]
S[k+1]     = S[k] + E[k]
```

where `u` is the signed SQ1-feedback DAC code and `S` is the per-row integral
state. The I contribution uses the integral state from before the current error
is added. P, I, and D are signed Q1.23 values (`sfixed(0 downto -23)`).

This is an incremental, or velocity-form, actuator update: even with `I = 0`,
the proportional correction is accumulated into `u`. P-only operation therefore
already removes a constant static error in the ideal model. The explicit I term
adds a second integration and should be kept substantially smaller than P.

## Modeled warm-electronics gain

### SQ1-feedback DAC and FEB output amplifier

The AD9767 model uses a 2 kOhm `FSADJ`, giving

```text
IOUTFS = (1.2 / 2000) * 32 = 19.2 mA
d(IdacP - IdacN)/d(code) = 2 * IOUTFS / 16384
                           = 2.34375 uA/code
```

The column-FEB differential amplifier model contributes

```text
24.9 * (402 + 100) / 100 = 124.998 V/A
```

and its implemented source/load network gives an SQ1-feedback current slope at
the wafer of approximately

```text
d(Isq1fb)/d(code) = 18.1303 nA/code = 0.0181303 uA/code.
```

This number follows the VHDL model exactly, including both modeled output
impedances and the default 200 Ohm wafer load. It is not substituted from the
similar, but not identical, Python front-end conversion model.

### SSA voltage through the FEB and ADC

The two stages of `ColumnFebSaBiasAmp` have differential gains

```text
Gfeb1 = 1 + 2*(100/40.2)             = 5.975124
Gfeb2 = 1 + 100/402 + 100/21         = 6.010661
Gfeb  = Gfeb1 * Gfeb2                = 35.914447.
```

The ADA4932 model then contributes `3660/1000 = 3.66`. The AD9681 model spans
16384 codes over 2 V, or 8192 codes/V. Thus

```text
d(ADC code)/d(Vssa)
  = 35.914447 * 3.66 * 8192
  = 1.076813e6 codes/V.
```

The SA offset DAC changes the DC operating point but not this small-signal gain.
The ADC FIR is bypassed at reset. None of the present FEB models includes a
frequency response, slew rate, analog noise, or a settling pole; their response
is instantaneous.

## Nominal nonlinear plant slope

Numerically evaluating the default `WAFER` (`1x32`) MUX model around a selected
row and a smooth tuned slope gives roughly

```text
g = d(ADC code)/d(SQ1FB DAC code) = -4 to -5.
```

The range covers representative SQ1 biases from about 20 to 75 uA with an SSA
bias near 60 uA. BICEP3, NIST-50-row, and BA4 topology changes move this gain,
but remain of the same order with the current common synthetic electrical
parameters. The sign is negative on the branch selected by the current tuning
conventions. If an observed finite-difference slope is positive, all feedback
coefficients must change sign.

## P-only derivation

Let `e[k]` be the mean ADC error in one row window. Then `E[k] = N*e[k]`, and let

```text
g = d(e)/d(u), in ADC codes per SQ1FB DAC code.
```

For P-only control, the error pole per visit to that row is

```text
z = 1 + N*g*P.
```

Stability requires

```text
-2 < N*g*P < 0.
```

For negative `g`, P must be positive. A desired pole `r` gives

```text
P = (r - 1)/(N*g).
```

For `N = 128`, `g = -4`, and `r = 0.5`, this gives
`P = 0.0009765625`, exactly `2^-10` and exactly representable in Q1.23.

## PI derivation

Using the accumulated window error and the integral state as the state vector,
the local linear update is

```text
[ E[k+1] ]   [ 1 + L*P   L*I ] [ E[k] ]
[ S[k+1] ] = [    1       1  ] [ S[k] ]

L = N*g.
```

The characteristic polynomial is

```text
z^2 - (2 + L*P)z + (1 + L*P - L*I) = 0.
```

For negative `g`, the basic discrete-time stability conditions include

```text
P > 0
0 < I < P
4 + L*(2*P - I) > 0.
```

A convenient design is to place both poles at `r`. This gives

```text
P = 2*(1-r)/(-N*g)
I = (1-r)^2/(-N*g).
```

Choosing `r = 0.75`, `N = 128`, and `g = -4` produces the recommended pair:

```text
P = 0.0009765625
I = 0.0001220703125 = P/8.
```

Across the estimated `g = -4 to -5` range, these coefficients give real poles
from approximately `0.75/0.75` to `0.55/0.83`. This is conservative enough for
a first simulation while still converging over a modest number of row visits.

The integral state is only 18 bits wide. A large sustained initial error can
overflow it before the loop converges, especially when the loop is enabled far
from its tuned lock point. Clear the PID state after changing I and before each
closed-loop trial, start close to the tuned point, and inspect the PID-debug
stream for integral growth or actuator limiting.

## Scaling with the sample-window length

Because the firmware uses a sum rather than an average, changing only the number
of samples requires all hardware coefficients to scale as `1/N` to preserve the
same dynamics per row visit:

```text
P(Nnew) = P(Nref) * Nref/Nnew
I(Nnew) = I(Nref) * Nref/Nnew
D(Nnew) = D(Nref) * Nref/Nnew.
```

For the recommended normalized gains

```text
Pmean = N*P = 0.125
Imean = N*I = 0.015625,
```

the corresponding hardware values are:

| Samples N | P coefficient | P raw | I coefficient | I raw |
| ---: | ---: | ---: | ---: | ---: |
| 64 | 0.001953125 | 16384 | 0.000244140625 | 2048 |
| 128 | 0.0009765625 | 8192 | 0.0001220703125 | 1024 |
| 250 | 0.0005000000 | 4194 | 0.0000625000 | 524 |
| 256 | 0.00048828125 | 4096 | 0.00006103515625 | 512 |

This scaling preserves poles per visit to a row. It does not preserve a fixed
wall-clock bandwidth if the row period or number of active rows also changes.
For a desired continuous settling time, first choose

```text
r = exp(-Trow_revisit/tau)
```

and then use the pole-placement equations above. `Trow_revisit` includes the
row dwell time and the complete active-row sequence. Any change to the tuned
plant slope `g`, analog gain, filtering, or operating point also requires new
identification; sample-count scaling alone cannot correct those changes.

## Python interface for normalized gains

`TimingTx.SampleCount` reports the implemented accumulator count:

```text
SampleCount = SampleEndTime - SampleStartTime.
```

At Group scope, the following per-column variables present gains on the mean
ADC error rather than the firmware's error sum:

- `PidP_Gain`
- `PidI_Gain`
- `PidD_Gain`
- `PidSampleCount` (read-only)

For example, the recommended starting values are set with:

```python
columns = group.NumColumns.get()
group.PidP_Gain.set([0.125] * columns)
group.PidI_Gain.set([0.015625] * columns)
group.PidD_Gain.set([0.0] * columns)
```

The linked variables divide by the coordinator's current `PidSampleCount` when
writing the per-column `AdcDsp` coefficients. `Session.setup_mux()` preserves
these normalized gains when it changes the sample window and rewrites the
hardware coefficients for the new `N`.

The normalization is intentionally at Group scope rather than inside
`AdcDsp.py`. In a multi-column-board Group, only column board 0 is the timing
coordinator. An `AdcDsp` on another board cannot infer the effective sample
window from that board's dormant local `TimingTx` register values. The Group and
Session layers know which timing source is authoritative.

Direct writes to `SampleStartTime` or `SampleEndTime` do not cause a linked
variable setter to run and therefore cannot rewrite coefficients automatically.
After changing those registers directly, reapply `PidP_Gain`, `PidI_Gain`, and
`PidD_Gain`, or use `Session.setup_mux()`.

## Required end-to-end verification

The next VCS GroupTb regression should:

1. run SA, FAS, and SQ1 tuning to establish a valid operating point;
2. disable the feedback loop and clear its per-row state;
3. perturb one row's SQ1FB by a small symmetric number of DAC codes;
4. calculate `g` from the mean ADC values on either side;
5. calculate P and I from a requested pole or settling time;
6. enable PI and apply a deterministic per-pixel TES step;
7. check convergence, overshoot, actuator limits, and flux-jump behavior; and
8. repeat with several sample-window lengths to verify `1/N` scaling.

The perturbation should be large enough to rise above ADC quantization but
small enough to remain on one smooth SQUID branch. A sweep over perturbations of
2, 4, and 8 DAC codes is a reasonable initial check.
