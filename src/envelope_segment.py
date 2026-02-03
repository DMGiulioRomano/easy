# envelope_segment.py
"""
Segment classes for Envelope system.

Design Pattern: Template Method
- Segment (ABC): defines interface
- NormalSegment: linear progression with hold at boundaries
- CyclicSegment: temporal wrapping, repeats indefinitely

Each Segment:
- Contains breakpoints in absolute time
- Delegates interpolation to InterpolationStrategy
- Knows how to evaluate() and integrate() itself
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from envelope_interpolation import InterpolationStrategy


class Segment(ABC):
    """
    Abstract base class for envelope segments.
    
    A Segment represents a portion of an envelope with:
    - Breakpoints in absolute time
    - An interpolation strategy (linear/step/cubic)
    - Context data (e.g., tangents for cubic)
    
    Template Method Pattern:
    - Subclasses implement evaluate() and integrate()
    - Common functionality (bounds, validation) here
    """
    
    def __init__(
        self,
        breakpoints: List[List[float]],
        strategy: InterpolationStrategy,
        context: Dict[str, Any] = None
    ):
        """
        Initialize segment.
        
        Args:
            breakpoints: [[t, v], ...] in absolute time, sorted
            strategy: InterpolationStrategy instance
            context: Additional data (e.g., {'tangents': [...]})
        """
        if len(breakpoints) < 1:
            raise ValueError("Segment must have at least one breakpoint")
        
        # Sort by time
        self.breakpoints = sorted(breakpoints, key=lambda p: p[0])
        self.strategy = strategy
        self.context = context or {}
        
        # Cache boundaries
        self.start_time = self.breakpoints[0][0]
        self.end_time = self.breakpoints[-1][0]
        self.duration = self.end_time - self.start_time
    
    @abstractmethod
    def evaluate(self, t: float) -> float:
        """
        Evaluate envelope at time t.
        
        Args:
            t: absolute time in seconds
            
        Returns:
            Envelope value at time t
        """
        pass
    
    @abstractmethod
    def integrate(self, from_t: float, to_t: float) -> float:
        """
        Integrate envelope between from_t and to_t.
        
        Args:
            from_t: start time (absolute)
            to_t: end time (absolute)
            
        Returns:
            Area under envelope curve
        """
        pass
    
    @property
    def is_cyclic(self) -> bool:
        """Override in subclasses."""
        return False
    
    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"start={self.start_time:.3f}, "
            f"end={self.end_time:.3f}, "
            f"strategy={self.strategy.__class__.__name__})"
        )


class NormalSegment(Segment):
    """
    Non-cyclic segment with hold behavior at boundaries.
    
    Behavior:
    - t < start_time: hold first value
    - start_time <= t <= end_time: interpolate
    - t > end_time: hold last value
    
    This is the standard envelope segment for attack/decay/release phases.
    """
    
    def evaluate(self, t: float) -> float:
        """
        Evaluate with hold at boundaries.
        
        Examples:
            seg = NormalSegment([[0, 0], [1, 10]], linear_strategy)
            seg.evaluate(-0.5) → 0    # Hold before
            seg.evaluate(0.5) → 5     # Interpolate
            seg.evaluate(1.5) → 10    # Hold after
        """
        # Hold before segment
        if t < self.start_time:
            return self.breakpoints[0][1]
        
        # Hold after segment
        if t > self.end_time:
            return self.breakpoints[-1][1]
        
        # Delegate to strategy for interpolation
        return self.strategy.evaluate(t, self.breakpoints, **self.context)
    
    def integrate(self, from_t: float, to_t: float) -> float:
        """
        Integrate with hold regions.
        
        Breakdown:
        1. Hold before segment (if from_t < start_time)
        2. Interpolated region (overlap with [start_time, end_time])
        3. Hold after segment (if to_t > end_time)
        
        Examples:
            seg = NormalSegment([[0, 0], [1, 10]], linear_strategy)
            seg.integrate(-1, 0) → 0        # Hold first value (0)
            seg.integrate(0, 1) → 5         # Triangle area
            seg.integrate(1, 2) → 10        # Hold last value (10)
            seg.integrate(-1, 2) → 15       # All three regions
        """
        if from_t >= to_t:
            return 0.0
        
        total = 0.0
        
        # Region 1: Hold BEFORE segment
        if from_t < self.start_time:
            hold_end = min(to_t, self.start_time)
            hold_value = self.breakpoints[0][1]
            total += hold_value * (hold_end - from_t)
            from_t = hold_end
        
        if from_t >= to_t:
            return total
        
        # Region 2: INTERPOLATED region (overlap with segment)
        if from_t < self.end_time:
            interp_start = max(from_t, self.start_time)
            interp_end = min(to_t, self.end_time)
            
            if interp_end > interp_start:
                total += self.strategy.integrate(
                    interp_start, interp_end,
                    self.breakpoints,
                    **self.context
                )
                from_t = interp_end
        
        if from_t >= to_t:
            return total
        
        # Region 3: Hold AFTER segment
        if from_t >= self.end_time and to_t > from_t:
            hold_value = self.breakpoints[-1][1]
            total += hold_value * (to_t - from_t)
        
        return total


class CyclicSegment(Segment):
    """
    Cyclic segment with temporal wrapping.
    
    Behavior:
    - t < start_time: hold first value (before cycle begins)
    - t >= start_time: wrap to cycle duration, repeat indefinitely
    
    The cycle repeats from start_time to end_time, then wraps back to start_time.
    
    IMPORTANT: At exact cycle boundaries (t = start_time + n*cycle_duration),
    the modulo operation wraps to start_time, NOT end_time.
    Example: if cycle is [0, 1], then:
        t=0.0 → phase=0.0 → start of cycle
        t=1.0 → phase=0.0 → wraps to start (NOT end)
        t=0.5 → phase=0.5 → middle of cycle
    
    This is consistent with standard periodic functions.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Validate cyclic segment
        if len(self.breakpoints) < 2:
            raise ValueError(
                "CyclicSegment must have at least 2 breakpoints to define a cycle"
            )
        
        # Cache cycle duration
        self.cycle_duration = self.end_time - self.start_time
        
        if self.cycle_duration <= 0:
            raise ValueError(
                f"CyclicSegment must have positive duration. "
                f"Got: {self.cycle_duration}"
            )
    
    def __repr__(self):
        return (
            f"CyclicSegment("
            f"start={self.start_time:.3f}, "
            f"cycle_dur={self.cycle_duration:.3f}, "
            f"strategy={self.strategy.__class__.__name__})"
        )
    
    @property
    def is_cyclic(self) -> bool:
        return True
    
    def evaluate(self, t: float) -> float:
        """
        Evaluate with temporal wrapping.
        
        Note: At cycle boundaries, wraps to start (not end).
        
        Examples:
            seg = CyclicSegment([[0, 0], [0.1, 1]], linear_strategy)
            seg.evaluate(0.05) → 0.5    # First cycle
            seg.evaluate(0.10) → 0.0    # Wraps to start (not 1.0!)
            seg.evaluate(0.15) → 0.5    # Second cycle
        """
        # Hold before cycle starts
        if t < self.start_time:
            return self.breakpoints[0][1]
        
        # Wrap time to cycle
        elapsed = t - self.start_time
        phase = elapsed % self.cycle_duration
        t_wrapped = self.start_time + phase
        
        # Delegate to strategy
        return self.strategy.evaluate(t_wrapped, self.breakpoints, **self.context)
    
    def integrate(self, from_t: float, to_t: float) -> float:
        """
        Integrate cyclic segment.
        
        Strategy:
        1. Calculate integral of one complete cycle
        2. Count how many full cycles fit in [from_t, to_t]
        3. Add partial cycle at start (if any)
        4. Add partial cycle at end (if any)
        
        Optimization: Pre-compute single cycle integral, multiply by count.
        
        Examples:
            seg = CyclicSegment([[0, 0], [0.1, 1]], linear_strategy)
            one_cycle = seg.integrate(0, 0.1) → 0.05  # Triangle
            seg.integrate(0, 0.3) → 0.15  # 3 cycles
            seg.integrate(0.05, 0.15) → 0.05  # Partial + partial
        """
        if from_t >= to_t:
            return 0.0
        
        total = 0.0
        
        # Hold region BEFORE cycle starts
        if from_t < self.start_time:
            hold_end = min(to_t, self.start_time)
            hold_value = self.breakpoints[0][1]
            total += hold_value * (hold_end - from_t)
            from_t = hold_end
        
        if from_t >= to_t:
            return total
        
        # CYCLIC region (from_t >= start_time)
        # Convert to relative time (elapsed from cycle start)
        rel_from = from_t - self.start_time
        rel_to = to_t - self.start_time
        
        # Calculate phase within cycle
        phase_from = rel_from % self.cycle_duration
        phase_to = rel_to % self.cycle_duration
        
        # Count full cycles between from_t and to_t
        full_cycles = int(rel_to // self.cycle_duration) - int(rel_from // self.cycle_duration)
        
        # Case 1: All within same cycle (no wrap)
        if full_cycles == 0:
            t_abs_from = self.start_time + phase_from
            t_abs_to = self.start_time + phase_to
            return total + self.strategy.integrate(
                t_abs_from, t_abs_to,
                self.breakpoints,
                **self.context
            )
        
        # Case 2: Spans multiple cycles
        
        # Pre-compute one cycle integral (optimization)
        one_cycle_integral = self.strategy.integrate(
            self.start_time,
            self.end_time,
            self.breakpoints,
            **self.context
        )
        
        # Partial cycle at START (from phase_from to end of cycle)
        if phase_from > 0:
            t_abs_from = self.start_time + phase_from
            t_abs_to = self.end_time
            total += self.strategy.integrate(
                t_abs_from, t_abs_to,
                self.breakpoints,
                **self.context
            )
            full_cycles -= 1
        
        # Full cycles in the middle
        total += full_cycles * one_cycle_integral
        
        # Partial cycle at END (from start of cycle to phase_to)
        if phase_to > 0:
            t_abs_from = self.start_time
            t_abs_to = self.start_time + phase_to
            total += self.strategy.integrate(
                t_abs_from, t_abs_to,
                self.breakpoints,
                **self.context
            )
        
        return total


# =============================================================================
# FACTORY HELPER
# =============================================================================

def create_segment(
    breakpoints: List[List[float]],
    strategy: InterpolationStrategy,
    is_cyclic: bool = False,
    context: Dict[str, Any] = None
) -> Segment:
    """
    Factory function to create appropriate segment type.
    
    Args:
        breakpoints: [[t, v], ...] in absolute time
        strategy: InterpolationStrategy instance
        is_cyclic: If True, create CyclicSegment, else NormalSegment
        context: Additional data for strategy
        
    Returns:
        NormalSegment or CyclicSegment instance
        
    Examples:
        # Normal segment
        seg = create_segment([[0, 0], [1, 10]], linear_strategy, is_cyclic=False)
        
        # Cyclic segment
        seg = create_segment([[0, 0], [0.1, 1]], linear_strategy, is_cyclic=True)
    """
    if is_cyclic:
        return CyclicSegment(breakpoints, strategy, context)
    else:
        return NormalSegment(breakpoints, strategy, context)