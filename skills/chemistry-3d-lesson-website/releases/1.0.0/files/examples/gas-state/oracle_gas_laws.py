#!/usr/bin/env python3
"""Independent gas-law oracle example for tests; do not import production code here."""

from __future__ import annotations

import argparse
import math
import random

R_L_ATM_PER_MOL_K = 0.082057366080960


def require_positive(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")


def celsius_to_kelvin(celsius: float) -> float:
    kelvin = celsius + 273.15
    require_positive(kelvin=kelvin)
    return kelvin


def boyle_pressure(p1: float, v1: float, v2: float) -> float:
    require_positive(p1=p1, v1=v1, v2=v2)
    return p1 * v1 / v2


def charles_volume(v1: float, t1_k: float, t2_k: float) -> float:
    require_positive(v1=v1, t1_k=t1_k, t2_k=t2_k)
    return v1 * t2_k / t1_k


def gay_lussac_pressure(p1: float, t1_k: float, t2_k: float) -> float:
    require_positive(p1=p1, t1_k=t1_k, t2_k=t2_k)
    return p1 * t2_k / t1_k


def combined_pressure(p1: float, v1: float, t1_k: float, v2: float, t2_k: float) -> float:
    require_positive(p1=p1, v1=v1, t1_k=t1_k, v2=v2, t2_k=t2_k)
    return p1 * v1 * t2_k / (t1_k * v2)


def avogadro_volume(v1: float, n1: float, n2: float) -> float:
    require_positive(v1=v1, n1=n1, n2=n2)
    return v1 * n2 / n1


def ideal_pressure(n: float, t_k: float, v: float, r: float = R_L_ATM_PER_MOL_K) -> float:
    require_positive(n=n, t_k=t_k, v=v, r=r)
    return n * r * t_k / v


def dalton_total(*partial_pressures: float) -> float:
    if not partial_pressures:
        raise ValueError("at least one partial pressure is required")
    for index, value in enumerate(partial_pressures):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"partial_pressures[{index}] must be finite and non-negative")
    return sum(partial_pressures)


def relative_error(expected: float, actual: float) -> float:
    denominator = max(abs(expected), 1e-15)
    return abs(expected - actual) / denominator


def self_test(samples: int, seed: int, tolerance: float) -> None:
    rng = random.Random(seed)
    maximum_error = 0.0
    for _ in range(samples):
        p1 = rng.uniform(0.2, 5.0)
        v1 = rng.uniform(0.2, 20.0)
        v2 = rng.uniform(0.2, 20.0)
        p2 = boyle_pressure(p1, v1, v2)
        maximum_error = max(maximum_error, relative_error(p1 * v1, p2 * v2))

        t1 = rng.uniform(150.0, 800.0)
        t2 = rng.uniform(150.0, 800.0)
        v_charles = charles_volume(v1, t1, t2)
        maximum_error = max(maximum_error, relative_error(v1 / t1, v_charles / t2))

        p_gay = gay_lussac_pressure(p1, t1, t2)
        maximum_error = max(maximum_error, relative_error(p1 / t1, p_gay / t2))

        n = rng.uniform(0.01, 4.0)
        p_ideal = ideal_pressure(n, t1, v1)
        maximum_error = max(maximum_error, relative_error(R_L_ATM_PER_MOL_K, p_ideal * v1 / (n * t1)))

    if maximum_error > tolerance:
        raise AssertionError(f"maximum relative error {maximum_error} exceeded {tolerance}")
    print(f"Gas-law oracle self-test passed: {samples} randomized states; max relative error={maximum_error:.3e}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--tolerance", type=float, default=1e-12)
    args = parser.parse_args()
    if args.self_test:
        self_test(args.samples, args.seed, args.tolerance)
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
