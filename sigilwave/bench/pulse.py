"""Where the energy actually is, right now, along the drawing.

§9.4: *the pulse is the protagonist. Render a discrete travelling blob, not a
glow.* A glow is a picture of where energy is; a blob that enters, crosses,
splits, laps and dies is a picture of why it went there, and the second is the
only one that teaches anything (§2.3).

Nothing here simulates. Each edge of the network is a pair of delay lines
whose buffers *are* the wave in physical order, so this is not a visualisation
of the state, it is the state, mapped onto the polyline the player drew. That
is `Bell.wave_samples()`'s approach and it is the best thing in the previous
build; two things are done differently and both are deliberate.

**Orientation.** `DelayLine.spatial_profile()` returns index 0 as the sample
about to exit — the *far* end — and index -1 as the most recently injected
sample at the near end. So the forward line (A->B) reads B-to-A and has to be
reversed before it can be laid along a polyline that runs A-to-B, and the
backward line (B->A) already reads A-to-B and must not be. Measured: inject at
node A of a 10-sample edge, step 4 times, and the sample sits at
spatial_profile index 6 = length - 4. `Bell.wave_samples()` sums
`fwd + bwd[::-1]` and then maps index 0 onto polyline[0], which is node A, so
its render runs backwards along every edge. On a bell that is invisible,
because a struck ring is a standing wave and the sum is symmetric. Here it
would show every pulse travelling the wrong way, which is the one thing this
module exists to show correctly.

**Bucket extrema, not stride.** Sampling every k-th slot drops samples, and a
single-sample blob on a 320-sample loop would flicker in and out of existence
as it travelled. Each output point is the largest-magnitude sample in its
bucket, placed at that sample's own position, so a discrete pulse survives
downsampling and moves smoothly instead of stepping.

Both directions matter and both are here: `pulse_samples` sums them, which is
the physical displacement at a point and is what makes a reflection visibly
come back through its own tail, and `pulse_samples_directed` keeps them apart
for a renderer that wants to tint outbound and returning energy differently.
"""

import numpy as np


def pulse_samples(network, assembly, max_points_per_edge: int = 64, min_amplitude: float = 0.0) -> list:
    """[(world_x, world_y, amplitude), ...] for everything currently in flight.

    Amplitude is signed: it is the wave, not a brightness. A renderer draws
    |amplitude| as the size or alpha of the blob and may use the sign for
    colour — the sign flip on reflection off a mouth is a real, watchable
    event and throwing it away here would hide it.
    """
    out = []
    for track, total in _edge_profiles(network, assembly):
        idx, amps = _bucket_extrema(total, max_points_per_edge)
        xs, ys = _points_at(track, (idx + 0.5) / len(total))
        for x, y, amp in zip(xs, ys, amps):
            if abs(amp) >= min_amplitude:
                out.append((float(x), float(y), float(amp)))
    return out


def pulse_samples_directed(network, assembly, max_points_per_edge: int = 64, min_amplitude: float = 0.0) -> list:
    """[(world_x, world_y, amplitude, direction), ...] with the two travelling
    waves kept apart. direction is +1 for A->B along the edge's own polyline
    and -1 for B->A, so a reflection is visibly a separate blob coming back
    rather than a wobble in the sum."""
    out = []
    for track, forward, backward in _edge_profiles(network, assembly, split=True):
        for samples, direction in ((forward, 1), (backward, -1)):
            idx, amps = _bucket_extrema(samples, max_points_per_edge)
            xs, ys = _points_at(track, (idx + 0.5) / len(samples))
            for x, y, amp in zip(xs, ys, amps):
                if abs(amp) >= min_amplitude:
                    out.append((float(x), float(y), float(amp), direction))
    return out


def _edge_profiles(network, assembly, split: bool = False):
    """One row per edge: the track it was drawn along and its buffer contents
    in A->B order. `compile_graph` assigns edge ids 0..N-1 in graph.edges
    order, which is the contract this mapping rests on and the same one the
    compiler itself relies on to place couplers."""
    tracks = assembly.edge_tracks()
    for edge_id, net_edge in network.edges.items():
        if edge_id >= len(tracks):
            continue
        track = tracks[edge_id]
        if len(track[0]) < 2:
            continue
        forward = net_edge.forward.spatial_profile()[::-1]
        backward = net_edge.backward.spatial_profile()
        if split:
            yield track, forward, backward
        else:
            yield track, forward + backward


def _bucket_extrema(samples, max_points: int):
    """(indices, amplitudes) - one per bucket, at the sample that dominates
    it, so a one-sample blob survives being drawn at a coarser resolution than
    the delay line it lives in."""
    n = len(samples)
    if n == 0:
        return np.zeros(0, dtype=int), np.zeros(0)
    if n <= max_points:
        return np.arange(n), samples
    bounds = np.linspace(0, n, max_points + 1).astype(int)
    lo, hi = bounds[:-1], bounds[1:]
    keep = hi > lo
    lo, hi = lo[keep], hi[keep]
    idx = np.array([l + int(np.argmax(np.abs(samples[l:h]))) for l, h in zip(lo, hi)])
    return idx, samples[idx]


def _points_at(track, fractions):
    """Arclength -> world, vectorised over every point of one edge at once.
    np.interp is a linear walk along the polyline, which is exactly the
    interpolation a renderer wants and about twenty times cheaper than doing
    it a point at a time."""
    xs, ys, cumulative = track
    total = cumulative[-1]
    if total <= 0.0:
        n = len(fractions)
        return np.full(n, xs[0]), np.full(n, ys[0])
    s = np.clip(fractions, 0.0, 1.0) * total
    return np.interp(s, cumulative, xs), np.interp(s, cumulative, ys)
