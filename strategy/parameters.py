"""Strategy parameters specification for Auto Range Detector [QuantAlgo]."""

from dataclasses import dataclass, field
from typing import List
from core.enums import BoundaryBasis, TouchDefinition, BreakConfirmation, RangeAnchoring


@dataclass
class RangeDetectorParameters:
    # Scan Scaling
    scan_scaling: str = "Base + 2x + 3x" # "Base only", "Base + 2x", "Base + 2x + 3x"
    base_scan_length: int = 20
    
    # Boundary Basis
    boundary_basis: BoundaryBasis = BoundaryBasis.PERCENTILE_BAND
    boundary_percentile: float = 90.0
    
    # Signal Timing
    signal_timing: str = "Bar close"
    
    # Volatility Baseline
    atr_length: int = 200
    
    # Compression & Calibration
    compression_percentile: float = 40.0
    calibration_lookback: int = 500
    
    # Rotation & Crossings
    min_rotation_rate: float = 0.18
    
    # Touches
    touch_definition: TouchDefinition = TouchDefinition.WICK_REACHES
    min_boundary_touches: int = 2
    touch_tolerance_atr: float = 0.10
    
    # Drift & Containment
    max_drift: float = 0.45
    min_containment: float = 0.70
    
    # Anchoring
    range_anchoring: RangeAnchoring = RangeAnchoring.EXTEND_TO_CONTAINMENT
    anchor_lookback: int = 300
    
    # Confirmation & Overshoot
    minimum_range_bars: int = 10
    absorb_overshoot: bool = True
    overshoot_tolerance_atr: float = 0.25
    
    # Breakout & Deviations
    break_confirmation: BreakConfirmation = BreakConfirmation.CLOSE_BEYOND
    breakout_buffer_atr: float = 0.15
    merge_deviations: bool = True
    deviation_window: int = 10
    cooldown_bars: int = 3
    max_range_age: int = 0 # 0 = unlimited

    @property
    def scan_scales(self) -> List[int]:
        if self.scan_scaling == "Base only":
            return [self.base_scan_length]
        elif self.scan_scaling == "Base + 2x":
            return [self.base_scan_length, self.base_scan_length * 2]
        else: # "Base + 2x + 3x"
            return [self.base_scan_length, self.base_scan_length * 2, self.base_scan_length * 3]
