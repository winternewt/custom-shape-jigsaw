"""Voronoi cellular automaton — the heart of the generator.

Faithful port of the ``Automata`` class in ``index.html`` (lines 241-775): mask fill (custom
border), grid seeding, Voronoi growth, corner detection and boundary edge tracing. The grids
are numpy-backed (see :mod:`custom_shape_jigsaw.grids`); the recursive ``findedgestep`` is
rewritten as an explicit loop so large grids cannot overflow Python's recursion limit.

Coordinates here are integer grid indices. ``grid`` holds the piece id owning each cell
(positive). During a growth step, just-claimed cells are temporarily marked negative so they
are not re-claimed within the same step, then set positive when the step commits.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from custom_shape_jigsaw import grids
from custom_shape_jigsaw.rng import Rng
from custom_shape_jigsaw.svg_input import BorderSample

logger = logging.getLogger(__name__)

# 4-connected neighbourhood used by the mask flood fill.
_CROSS = ((-1, 0), (1, 0), (0, 1), (0, -1))

# Corner-detection quadrant lookup (index.html:462). Each entry's first offset is the primary.
_CORNER_LOOKUP = (
    ((1, 1), (0, 1), (1, 0)),
    ((-1, -1), (0, -1), (-1, 0)),
    ((1, -1), (0, -1), (1, 0)),
    ((-1, 1), (0, 1), (-1, 0)),
)


@dataclass
class SeedPoint:
    row: int
    col: int
    val: int


@dataclass
class Corner:
    row: int
    col: int
    onborder: bool


@dataclass
class CornerSnap:
    """A border corner snapped to the nearest real border point (grid coordinate space)."""

    row: int
    col: int
    x: float
    y: float


class Automata:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.columns = cols
        self.max_growth_dist = 0.0
        self.empty_cells = 0

        self.grid = grids.int_grid(rows, cols)
        self.maskgrid = grids.int_grid(rows, cols)
        self.lockedgrid = grids.int_grid(rows, cols)
        # cornergrid is (rows+1, cols+1): edge tracing addresses col+1 / row+1 (index.html:465).
        self.cornergrid = grids.int_grid(rows + 1, cols + 1)
        # Nearest-border-point payload per cell, stored as two float grids (NaN = empty).
        self.borderdist_rx = grids.float_grid(rows, cols)
        self.borderdist_ry = grids.float_grid(rows, cols)

        self.seedpoints: list[SeedPoint] = []
        self._seed_by_val: dict[int, SeedPoint] = {}
        self.cornertable: list[CornerSnap] = []

    @property
    def piece_count(self) -> int:
        return len(self.seedpoints)

    # -- neighbourhood -----------------------------------------------------------------
    def neighbor_coords(self, row: int, col: int) -> list[tuple[int, int]]:
        """The up-to-8 in-bounds neighbours (3x3 minus centre), in JS iteration order."""
        coords = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                pr = row + di
                pc = col + dj
                if 0 <= pr < self.rows and 0 <= pc < self.columns:
                    coords.append((pr, pc))
        return coords

    # -- mask fill (custom border) -----------------------------------------------------
    def fill_mask(self, samples: list[BorderSample]) -> None:
        """Mark border cells then flood-fill inside/outside via even/odd region growth.

        Direct port of ``fillmask`` (index.html:259-333), including the faithfulness quirk that
        the local ``outside`` flag is never reassigned, so ``regnum`` increments by 1 each pass.
        """
        rows, cols = self.rows, self.columns
        grid = self.maskgrid
        for s in samples:
            if 0 <= s.gy < rows and 0 <= s.gx < cols:
                self.borderdist_rx[s.gy, s.gx] = s.rx + 0.5
                self.borderdist_ry[s.gy, s.gx] = s.ry + 0.5
                grid[s.gy, s.gx] = 1

        regnum = 3
        grown = True
        while grown:
            grown = False
            for i in range(-1, rows + 1):
                for j in range(-1, cols + 1):
                    oob = i < 0 or j < 0 or i > rows - 1 or j > cols - 1
                    if not (oob or (1 < grid[i, j] < regnum)):
                        continue
                    stack = [(i, j)]
                    while stack:
                        pr, pc = stack.pop()
                        for dr, dc in _CROSS:
                            ii = pr + dr
                            jj = pc + dc
                            if 0 <= ii < rows and 0 <= jj < cols:
                                if not grid[ii, jj]:
                                    stack.append((ii, jj))
                                if grid[ii, jj] < 2:
                                    grid[ii, jj] = regnum
                                    grown = True
            # Local `outside` is always True in the JS, so the increment is always +1.
            regnum += 1

        grids.mod2_inplace(grid)
        for s in samples:
            if 0 <= s.gy < rows and 0 <= s.gx < cols:
                grid[s.gy, s.gx] = 1

    # -- seeding -----------------------------------------------------------------------
    def grid_seed(self, gsize: int, randlen: float, rng: Rng) -> None:
        """Place jittered Voronoi seed points on a regular grid (index.html:334)."""
        self.seedpoints = []
        self._seed_by_val = {}
        val = 1
        half = gsize / 2.0
        i = half
        while i <= self.rows - half:
            j = half
            while j <= self.columns - half:
                # Both uniforms are drawn before the mask check, so the RNG advances regardless.
                row = math.floor(i + rng.uniform(-half * randlen, half * randlen)) % self.rows
                col = math.floor(j + rng.uniform(-half * randlen, half * randlen)) % self.columns
                if row < 0:
                    row += self.rows
                if col < 0:
                    col += self.columns
                if not self.maskgrid[row, col]:
                    self.grid[row, col] = val
                    sp = SeedPoint(row=row, col=col, val=val)
                    self.seedpoints.append(sp)
                    self._seed_by_val[val] = sp
                    val += 1
                j += gsize
            i += gsize
        logger.info("Seeded %d Voronoi cells (gsize=%d, noise=%g)", val - 1, gsize, randlen)

    def count_empty(self) -> int:
        return grids.count_empty(self.grid, self.maskgrid)

    # -- growth ------------------------------------------------------------------------
    def grow(self, row: int, col: int, growth: list[tuple[int, int, int]]) -> None:
        """Claim empty neighbours of the seed-owned cell at (row, col) within the radius."""
        current = int(self.grid[row, col])
        seed = self._seed_by_val[current]
        grown: list[tuple[int, int]] = []
        growable = False
        for nr, nc in self.neighbor_coords(row, col):
            if self.maskgrid[nr, nc]:
                continue
            if not self.grid[nr, nc]:  # empty
                growable = True
                dist = math.sqrt((nr - seed.row) ** 2 + (nc - seed.col) ** 2)
                if dist < self.max_growth_dist:
                    growth.append((nr, nc, current))
                    grown.append((nr, nc))
        if not growable:
            self.lockedgrid[row, col] = 1
        # Don't grow into a single pure-diagonal neighbour (index.html:563).
        if len(grown) == 1 and grown[0][0] != row and grown[0][1] != col:
            grown = []
            growth.pop()
        for gr, gc in grown:
            self.grid[gr, gc] = -current

    def step(self, radius: float, rng: Rng) -> int:
        """One growth pass over the whole grid; returns the number of cells claimed."""
        growth: list[tuple[int, int, int]] = []
        # These three draws are unused (their results are immediately overwritten in the JS),
        # but they advance the shared RNG every step and must be replicated for parity.
        rng.uniform(0, self.rows)
        rng.uniform(0, self.columns)
        rng.rbool()

        self.max_growth_dist = radius
        for i in range(self.rows):
            for j in range(self.columns):
                if self.grid[i, j] > 0 and not self.lockedgrid[i, j]:
                    self.grow(i, j, growth)
        for gr, gc, gval in growth:
            self.grid[gr, gc] = gval
        return len(growth)

    def grow_regions(self, rng: Rng) -> None:
        """Run the growth loop until every cell is claimed or growth stalls (index.html:912)."""
        radius = 0.0
        self.empty_cells = self.count_empty()
        stale = 0
        while True:
            grown = self.step(radius, rng)
            self.empty_cells -= grown
            radius += 1
            stale = stale + 1 if grown == 0 else 0
            if not (self.empty_cells and stale < 10):
                break
        logger.info("Growth complete (radius=%g, remaining empties=%d)", radius, self.empty_cells)

    # -- corners -----------------------------------------------------------------------
    def _mindist_closest(self, corner: Corner) -> tuple[float, float, float] | None:
        """Nearest sampled border point to ``corner`` among it and its neighbours."""
        candidates = self.neighbor_coords(corner.row, corner.col)
        candidates.append((corner.row, corner.col))
        mind = 1e12
        cp: tuple[float, float] | None = None
        for nr, nc in candidates:
            if not (0 <= nr < self.rows and 0 <= nc < self.columns):
                continue
            rx = self.borderdist_rx[nr, nc]
            if math.isnan(rx):
                continue
            ry = self.borderdist_ry[nr, nc]
            d = math.hypot(rx - corner.col, ry - corner.row)
            if d < mind:
                mind = d
                cp = (float(rx), float(ry))
        if cp is None:
            return None
        return mind, cp[0], cp[1]

    def find_corners(self, has_border: bool) -> list[Corner]:
        """Find grid points where >=3 regions (incl. outside=0) meet (index.html:461)."""
        rows, cols = self.rows, self.columns
        self.cornergrid = grids.int_grid(rows + 1, cols + 1)
        corners: list[Corner] = []
        for i in range(-1, rows + 1):
            for j in range(-1, cols + 1):
                cand: list[Corner] = []
                for le in _CORNER_LOOKUP:
                    if i < 0 or j < 0 or j >= cols or i >= rows:
                        distinct = [0]
                    else:
                        distinct = [int(self.grid[i, j])]
                    for dr, dc in le:
                        ii = i + dr
                        jj = j + dc
                        if ii < 0 or jj < 0 or ii >= rows or jj >= cols:
                            if 0 not in distinct:
                                distinct.append(0)
                        else:
                            val = int(self.grid[ii, jj])
                            if val not in distinct:
                                distinct.append(val)
                    if len(distinct) > 2:
                        c = le[0]
                        cr = c[0] if c[0] > 0 else 0
                        cc = c[1] if c[1] > 0 else 0
                        cand.append(Corner(row=i + cr, col=j + cc, onborder=(0 in distinct)))
                for cc in cand:
                    if not self.cornergrid[cc.row, cc.col]:
                        self.cornergrid[cc.row, cc.col] = 1
                        corners.append(cc)

        self.cornertable = []
        if has_border:
            for c in corners:
                if c.onborder:
                    result = self._mindist_closest(c)
                    if result is not None:
                        _, x, y = result
                    else:
                        x, y = float(c.col), float(c.row)
                    self.cornertable.append(CornerSnap(row=c.row, col=c.col, x=x, y=y))
        logger.info("Found %d corners (%d on border)", len(corners),
                    sum(1 for c in corners if c.onborder))
        return corners

    # -- edges -------------------------------------------------------------------------
    def _find_edge_step(self, edge: list[tuple[int, int]], row: int, col: int, pdir: str) -> None:
        """Iterative port of the tail-recursive ``findedgestep`` (index.html:579).

        Walks the boundary between two differing regions one cell at a time. Direction priority
        is E, W, N, S; the first eligible direction advances, hitting another corner stops.
        """
        rows, cols = self.rows, self.columns
        grid = self.grid
        cg = self.cornergrid
        first = True
        while True:
            if row < 0 or col < 0 or row >= rows or col >= cols:
                return
            if not first and cg[row, col] == 1:
                return
            first = False

            if "E" in pdir:
                v1 = int(grid[row, col])
                v2 = 0 if row - 1 < 0 else int(grid[row - 1, col])
                if v1 and v2 and v1 != v2:
                    tr, tc = row, col + 1
                    if cg[tr, tc] < 2:
                        if cg[tr, tc] == 0:
                            cg[tr, tc] = 2
                        edge.append((tr, tc))
                        row, col, pdir = tr, tc, "NSE"
                        continue
                    return
            if "W" in pdir:
                v1 = 0 if col - 1 < 0 else int(grid[row, col - 1])
                v2 = 0 if (row - 1 < 0 or col - 1 < 0) else int(grid[row - 1, col - 1])
                if v1 and v2 and v1 != v2:
                    tr, tc = row, col - 1
                    if cg[tr, tc] < 2:
                        if cg[tr, tc] == 0:
                            cg[tr, tc] = 2
                        edge.append((tr, tc))
                        row, col, pdir = tr, tc, "NSW"
                        continue
                    return
            if "N" in pdir:
                v1 = 0 if row - 1 < 0 else int(grid[row - 1, col])
                v2 = 0 if (row - 1 < 0 or col - 1 < 0) else int(grid[row - 1, col - 1])
                if v1 and v2 and v1 != v2:
                    tr, tc = row - 1, col
                    if cg[tr, tc] < 2:
                        if cg[tr, tc] == 0:
                            cg[tr, tc] = 2
                        edge.append((tr, tc))
                        row, col, pdir = tr, tc, "NEW"
                        continue
                    return
            if "S" in pdir:
                v1 = int(grid[row, col])
                v2 = 0 if col - 1 < 0 else int(grid[row, col - 1])
                if v1 and v2 and v1 != v2:
                    tr, tc = row + 1, col
                    if cg[tr, tc] < 2:
                        if cg[tr, tc] == 0:
                            cg[tr, tc] = 2
                        edge.append((tr, tc))
                        row, col, pdir = tr, tc, "SEW"
                        continue
                    return
            return

    def find_edges(self, corners: list[Corner]) -> list[list[tuple[int, int]]]:
        """Trace all region-boundary edges from every corner (index.html:681)."""
        edgepaths: list[list[tuple[int, int]]] = []
        shortedges: list[list[tuple[int, int]]] = []
        for c in corners:
            for d in ("N", "S", "E", "W"):
                edge: list[tuple[int, int]] = [(c.row, c.col)]
                self._find_edge_step(edge, c.row, c.col, d)
                if len(edge) <= 1:
                    continue
                if len(edge) == 2:
                    a, b = edge[0], edge[1]
                    duplicate = any(
                        (s[0] == a and s[1] == b) or (s[1] == a and s[0] == b) for s in shortedges
                    )
                    if not duplicate:
                        edgepaths.append(edge)
                        shortedges.append(edge)
                else:
                    edgepaths.append(edge)
        logger.info("Traced %d boundary edges", len(edgepaths))
        return edgepaths
