# An explicit optimal fan at high pitch

**Theorem.** Let `N >= M >= 1` and `d >= ceil(M/2)`. Under the equally spaced rectangular-terminal model with unique boundary exits and vertex-disjoint grid paths, the construction below minimizes total length. Allowing nonmonotone paths cannot improve that value. Transposition handles `N < M`.

This theorem does not cover `2*d < min(N,M)` and does not assert that `d` is a minimum feasible pitch. The [implementation](../src/pure/pure_fan.cpp) uses explicit paths, a formula, and the independent verifier; it contains no flow solver.

## 1. Assignment and optimal value

Define

\[
h=\lceil M/2\rceil,\quad q=\lfloor M/2\rfloor,\quad
c_x=\min(x,N+1-x),\quad r_y=\min(y,M+1-y),
\]
\[
t_x=\min(c_x,h),\quad b_x=\min(h,c_x-1),\quad
u_x=\min(q,c_x-1),\quad g(k)=\lfloor k^2/4\rfloor.
\]

Assign each terminal to a nearest side. Break horizontal/vertical ties toward the left or right side; break top/bottom ties toward the bottom. The center of an odd square goes left.

Each row sends `r_y` terminals to each horizontal side, except the middle row of an odd square sends `r_y-1` to the right. Each column sends `b_x` terminals down and `u_x` up. These groups partition the terminals.

Let `epsilon=1` for an odd square and `0` otherwise. The claimed optimum is

\[
L^*=d\sum_{x=1}^{N}t_x(M+1-t_x)
    +2\sum_{y=1}^{M}g(r_y)
    +\sum_{x=1}^{N}\bigl(g(b_x)+g(u_x)\bigr)
    -\epsilon\lfloor h/2\rfloor.
\]

The first term is total perpendicular distance to the nearest side. The remaining terms account for distinct exit offsets.

## 2. Paths within one group

Use local coordinates with boundary `u=0` and terminals `(i*d,0)`, `i=1,...,k`. Every group satisfies `k <= h <= d`.

Assign exit offsets in order `0,+1,-1,+2,-2,...`. For path `i`, let `a=floor(i/2)`, with sign `s=+1` for even `i` and `s=-1` for odd `i`. Start at `(0,s*a)`. For `j=0,...,a-1`, define

\[
v_j=a-j,\qquad
w_j=(e_i+2j)d+a-j,
\]

where `e_i=2` for odd `i` and `1` for even `i`. Visit `(w_j,s*v_j)`, then `(w_j,s*(v_j-1))`, and finally `(i*d,0)`. For `a=0`, connect directly.

Each path is monotone in `u` and toward zero in `v`. Its length is `i*d+floor(i/2)`, so the group's total offset cost is `sum floor(i/2)=g(k)`.

For paths of the same sign, horizontal intervals at each nonzero `v` level are staggered and separated by at least one grid unit. Opposite-sign paths can meet only at `v=0`. Path `i>1` occupies only `[(i-1)d+1,i*d]` on that axis, while the first occupies `[0,d]`; these intervals are disjoint. All nonzero offsets have magnitude less than `d`, and no path passes through another terminal on the axis.

## 3. Disjointness between groups

Each group lies in a strip with offset range

\[
[-\lfloor(k-1)/2\rfloor,\ \lfloor k/2\rfloor].
\]

Adjacent projection lines are `d` apart and `k<=d`, so adjacent groups on one side are disjoint. Opposite left/right groups in a row have total terminal count at most `N`, leaving at least one pitch interval between them. The odd-square center correction preserves this property. Top/bottom groups are similarly separated because `b_x+u_x<=M`.

Consider a left-side group in row `y` and a bottom-side group in column `x`. The former extends at most to `r_y*d` and stays strictly above `(y-1)d`. The latter stays strictly to the right of `(x-1)d` and extends at most to `b_x*d <= (x-1)d`. If their horizontal ranges overlap, then `x<=r_y<=y`; consequently the bottom group stays at or below `(y-1)d`, below the left group. The other corners follow by the same reflected separation argument.

Thus all paths are vertex-disjoint, exits are unique, and paths do not touch the boundary internally. Summing their lengths gives `L*`.

## 4. A lower bound for every legal routing

The following argument uses only endpoint/exit inequalities, without invoking a solver.

Give each left/right projection `y*d` height `A_y=floor(r_y/2)`, and each bottom/top projection `x*d` height `B_x=floor(t_x/2)`. On each side define a nonnegative exit weight

\[
\beta(p)=\max_j(a_j-|p-jd|)_+,
\]

using that side's heights `a_j`. Projection centers are `d` apart, and neighboring heights sum to at most `h<=d`. Positive supports do not overlap. A height-`a` integer tent has total weight `a^2`. These supports do not reach the corners, so the four sides can be summed independently.

For terminal `s=(x*d,y*d)`, define

\[
\alpha_s=\min\{d c_x+A_y,\ d r_y+B_x\}.
\]

Every boundary exit `p` satisfies

\[
\operatorname{dist}_1(s,p)+\beta(p)\ge\alpha_s.
\]

For example, a bottom exit at horizontal distance `z` from the terminal's column projection satisfies `z+beta(p)>=B_x`; adding the perpendicular distance establishes the inequality. The other sides are analogous.

Paths are at least their endpoint Manhattan distances, and exits cannot repeat. Hence every legal routing satisfies

\[
L\ge\sum_s\alpha_s-\sum_{p\text{ on the boundary}}\beta(p).
\]

If `c_x<=r_y`, then

\[
d(r_y-c_x)\ge\lfloor r_y/2\rfloor-\lfloor c_x/2\rfloor,
\]

so the horizontal term realizes `alpha_s`. The vertical case is analogous. This matches the nearest-side assignment in Section 1, with equal values on ties.

For every assigned group, its load `k` and height `a` satisfy `k` in `{2a-1,2a,2a+1}`:

- Left/right groups: `k=r_y`, `a=floor(r_y/2)`.
- Top/bottom groups with `c_x<=h`: `k=c_x-1`, `a=floor(c_x/2)`.
- Columns with `c_x>h`: loads `h` and `q`, with height `floor(h/2)`.
- The corrected right group in an odd square: `k=h-1`, `a=floor(h/2)`.

In each case, `k*a-a^2=g(k)`. The lower bound is therefore the nearest-side distance plus all group offset costs, exactly `L*`. Section 3 constructs a legal routing of that length, proving optimality.

## 5. Complexity

The length formula takes `O(N+M)` time. Each path has a constant-size parametric description (side, group, rank, and pitch), so a compressed construction takes `O(NM)` time and space. Expanding all bends takes `O(NM^2)` time and space when `N>=M`.

The supplied C++ program expands the bends and runs the independent fine-grid verifier. The verifier uses `O(G)` time and space; the complete executable should not be described as a strict `O(NM)` implementation.
