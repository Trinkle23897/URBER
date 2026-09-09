#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include "routing_types.hpp"

// Dynamic prefix counts of unrouted terminals; no path search or repair.
struct TerminalCounts {
  int width = 0, height = 0;
  std::vector<int> tree;
  void reset(int w, int h) {
    width = w;
    height = h;
    tree.assign(size_t(w + 1) * (h + 1), 0);
  }
  void add(int x, int y, int delta) {
    for (int i = x; i <= width; i += i & -i)
      for (int j = y; j <= height; j += j & -j)
        tree[size_t(i) * (height + 1) + j] += delta;
  }
  int prefix(int x, int y, long long &work) const {
    int count = 0;
    for (int i = std::min(x, width); i > 0; i -= i & -i)
      for (int j = std::min(y, height); j > 0; j -= j & -j) {
        count += tree[size_t(i) * (height + 1) + j];
        ++work;
      }
    return count;
  }
};

class Router {
public:
  int N, M, d, gx, gy, region = -1;
  std::vector<uint64_t> occupied;
  std::vector<int> owner;
  std::vector<bool> routed;
  std::vector<Path> paths;
  std::vector<Point> masks;
  std::vector<int> rows[4], cols[4];
  int sizes[4] = {}, tx_current = 0, ty_current = 0;
  long long total = 0;
  bool port_priority, revised;
  Point frontier{0, 0};
  long long decision_work = 0;
  TerminalCounts counts[4];
  Router(int n, int m, int pitch, bool prioritize_ports = false,
         bool revised_rules = false)
      : N(n), M(m), d(pitch), gx((n + 1) * pitch), gy((m + 1) * pitch),
        occupied((uint64_t(gx + 1) * (gy + 1) + 63) / 64),
        owner((n + 1) * (m + 1)), routed(owner.size(), false),
        port_priority(prioritize_ports), revised(revised_rules) {
    for (int k = 0; k < 4; ++k) {
      rows[k].resize(M + 1);
      cols[k].resize(N + 1);
      if (revised)
        counts[k].reset((N + 1) / 2, (M + 1) / 2);
    }
    for (int x = 1; x <= N; ++x)
      for (int y = 1; y <= M; ++y) {
        int k = assignment(x, y);
        owner[x * (M + 1) + y] = k;
        ++sizes[k];
        ++cols[k][k & 1 ? N + 1 - x : x];
        ++rows[k][k & 2 ? M + 1 - y : y];
        if (revised)
          counts[k].add(k & 1 ? N + 1 - x : x, k & 2 ? M + 1 - y : y, 1);
      }
  }
  // Section III-C: the nine terminal assignment rules, including odd axes.
  int assignment(int x, int y) const {
    // Match the innermost horizontal-axis terminal to the adjacent central
    // column.
    int phase = revised ? (N / 2) % 2 : 0;
    int a = 2 * x - (N + 1), b = 2 * y - (M + 1);
    if (a && b)
      return (a > 0) + 2 * (b > 0);
    if (!a && b < 0)
      return y % 2 ? 0 : 1;
    if (!a && b > 0)
      return (M - y) % 2 ? 2 : 3;
    if (a < 0 && !b)
      return (x + phase) % 2 ? 2 : 0;
    if (a > 0 && !b)
      return (N - x + phase) % 2 ? 3 : 1;
    return ((N >= M && M % 4 == 1) || (N < M && N % 4 == 3)) ? 0 : 1;
  }
  Point global(Point p) const {
    if (region >= 0) {
      if (region & 1)
        p.x = gx - p.x;
      if (region & 2)
        p.y = gy - p.y;
    }
    return p;
  }
  uint64_t index(Point p) const { return uint64_t(p.y) * (gx + 1) + p.x; }
  bool blocked_global(Point p) const {
    if (p.x < 0 || p.y < 0 || p.x > gx || p.y > gy)
      return true;
    auto k = index(p);
    return (occupied[k / 64] >> (k % 64)) & 1;
  }
  bool blocked(Point p) const { return blocked_global(global(p)); }
  void set_global(Point p, bool v = true) {
    auto k = index(p);
    if (v)
      occupied[k / 64] |= uint64_t(1) << (k % 64);
    else
      occupied[k / 64] &= ~(uint64_t(1) << (k % 64));
  }
  int terminal_global(Point p) const {
    if (p.x <= 0 || p.x >= gx || p.y <= 0 || p.y >= gy || p.x % d || p.y % d)
      return -1;
    return p.x / d * (M + 1) + p.y / d;
  }
  int terminal(Point p) const { return terminal_global(global(p)); }
  bool available(Point p) const {
    int t = terminal(p);
    return t >= 0 && !routed[t] && (region < 0 || owner[t] == region);
  }
  // Algorithm 1. Store turns only, but make every decision on the fine grid.
  Path rule1(Point target, Point start, bool column) const {
    Point p = start;
    Path c{p};
    int previous = -1;
    int side = column ? sign(target.x - start.x) : sign(target.y - start.y);
    if (blocked(p))
      return {};
    for (int steps = 0; steps < gx + gy + 2; ++steps) {
      if (available(p)) {
        if (!(c.back() == p))
          c.push_back(p);
        return c;
      }
      Point q = p, r = p;
      if (column) {
        q.y++;
        r.x += side;
      } else {
        q.x++;
        r.y += side;
      }
      bool noncol = column ? p.x != target.x : p.y != target.y;
      int dir;
      if (noncol && !blocked(r)) {
        dir = 0;
      } else if (!blocked(q)) {
        dir = 1;
      } else
        return {};
      if (previous != -1 && previous != dir)
        c.push_back(p);
      p = dir == 0 ? r : q;
      previous = dir;
    }
    return {};
  }
  void commit(Path c) {
    if (c.empty())
      throw std::runtime_error("empty channel");
    Point local_start = c.front();
    for (auto &p : c)
      p = global(p);
    int t = terminal_global(c.back());
    if (t < 0 || routed[t])
      throw std::runtime_error(
          "endpoint already routed region=" + std::to_string(region) +
          " point=" + std::to_string(c.back().x) + "," +
          std::to_string(c.back().y) +
          " paths=" + std::to_string(paths.size()));
    if (region >= 0 && owner[t] != region)
      throw std::runtime_error("wrong region: " + std::to_string(region) +
                               " terminal " + std::to_string(c.back().x / d) +
                               "," + std::to_string(c.back().y / d));
    for (size_t i = 0; i < c.size(); ++i) {
      Point p = c[i];
      if (i) {
        auto a = c[i - 1];
        int dx = sign(p.x - a.x), dy = sign(p.y - a.y);
        p = {a.x + dx, a.y + dy};
        while (!(p == c[i])) {
          if (blocked_global(p))
            throw std::runtime_error("channel intersection");
          set_global(p);
          p.x += dx;
          p.y += dy;
        }
      }
      if (blocked_global(p))
        throw std::runtime_error("channel intersection at corner");
      set_global(p);
    }
    int k = owner[t], x = c.back().x / d, y = c.back().y / d;
    --cols[k][k & 1 ? N + 1 - x : x];
    --rows[k][k & 2 ? M + 1 - y : y];
    if (revised)
      counts[k].add(k & 1 ? N + 1 - x : x, k & 2 ? M + 1 - y : y, -1);
    if (region >= 0) {
      if (local_start.y == 0)
        tx_current = std::min(tx_current, local_start.x - 1);
      if (local_start.x == 0)
        ty_current = std::min(ty_current, local_start.y - 1);
    }
    total += length(c);
    routed[t] = true;
    paths.push_back(std::move(c));
  }
  // Algorithm 2: alternate the escape direction for a row or column.
  bool rule2(bool column, int n, int lim, int delta) {
    int tl = n * d - delta, tr = tl + 1;
    for (int i = 1; i <= lim; ++i) {
      Point s = column ? Point{n * d, i * d} : Point{i * d, n * d};
      if (!available(s))
        break;
      bool left = (i + delta) % 2;
      int t = left ? tl : tr;
      Point start = column ? Point{t, 0} : Point{0, t};
      if (blocked(start))
        break;
      auto c = rule1(s, start, column);
      if (c.empty())
        return false;
      commit(c);
      if (left)
        --tl;
      else
        ++tr;
    }
    return true;
  }
  // Algorithm 3. A 180-degree copy supplies the other two central boundaries.
  void balance_axes() {
    if (!revised || M % 2 == 0 || 3LL * N < 4LL * M)
      return;
    int pending[4] = {}, capacity[4] = {};
    int mid = (M + 1) / 2;
    for (int x = 1; x <= N; ++x)
      for (int y = 1; y <= M; ++y) {
        int t = x * (M + 1) + y;
        if (!routed[t] && !(y == mid && 2 * x != N + 1))
          ++pending[owner[t]];
      }
    for (int k = 0; k < 4; ++k) {
      region = k;
      capacity[k] = external(true) + external(false);
    }
    region = -1;
    std::vector<int> remaining_axis;
    for (int x = N / 2; x >= 1; --x)
      if (!routed[x * (M + 1) + mid])
        remaining_axis.push_back(x);
    int cur = 0;
    if (remaining_axis.size() % 2 &&
        capacity[0] + capacity[3] - pending[0] - pending[3] <
            capacity[1] + capacity[2] - pending[1] - pending[2])
      cur = 2;
    auto assign = [&](int x, int k) {
      int t = x * (M + 1) + mid;
      if (routed[t])
        return;
      int old = owner[t];
      --sizes[old];
      ++sizes[k];
      --cols[old][old & 1 ? N + 1 - x : x];
      --rows[old][mid];
      ++cols[k][k & 1 ? N + 1 - x : x];
      ++rows[k][mid];
      counts[old].add(old & 1 ? N + 1 - x : x, mid, -1);
      counts[k].add(k & 1 ? N + 1 - x : x, mid, 1);
      owner[t] = k;
    };
    for (int x : remaining_axis) {
      assign(x, cur);
      assign(N + 1 - x, 3 - cur);
      cur = 2 - cur;
    }
  }

  int central_limit() const {
    if (!revised || 3LL * N < 4LL * M)
      return N / 2;
    if (M == 2 * d + 1)
      return (N + 1 + (N % 4 == 3)) / 3;
    return N / 2 - (N % 2 == 0);
  }
  bool central() {
    int ln = N / 2, lm = M / 2;
    if (N % 2) {
      if (!rule2(true, (N + 1) / 2, std::min(2 * d - 1, lm), 0))
        return false;
    } else {
      if (!rule2(true, N / 2, std::min(d, lm), 0) ||
          !rule2(true, N / 2 + 1, lm, 1))
        return false;
    }
    if (M % 2) {
      if (!rule2(false, (M + 1) / 2, std::min(2 * d - 1, central_limit()), 1))
        return false;
    } else {
      if (!rule2(false, M / 2 + 1, std::min(d, ln), 1) ||
          !rule2(false, M / 2, ln, 0))
        return false;
    }
    auto count = paths.size();
    for (size_t i = 0; i < count; ++i) {
      Path c = paths[i];
      for (auto &p : c)
        p = {gx - p.x, gy - p.y};
      commit(c);
    }
    return true;
  }
  void mask(Point p) {
    auto q = global(p);
    if (!blocked_global(q)) {
      set_global(q);
      masks.push_back(q);
    }
  }
  void add_masks() {
    // Figure 13: the d grid points ending at an excluded central-axis terminal.
    // Retain previous occupancy so removing masks cannot erase routed channels.
    for (int x = 1; x <= (N + 1) / 2; ++x)
      for (int y = 1; y <= (M + 1) / 2; ++y) {
        Point p{x * d, y * d};
        int t = terminal(p);
        if (routed[t] || owner[t] == region)
          continue;
        if (N % 2 && x == (N + 1) / 2)
          for (int z = 0; z < d; ++z)
            mask({p.x, p.y - z});
        if (M % 2 && y == (M + 1) / 2)
          for (int z = 0; z < d; ++z)
            mask({p.x - z, p.y});
      }
  }
  void clear_masks() {
    for (auto p : masks)
      set_global(p, false);
    masks.clear();
  }
  Point remaining() {
    Point max = revised ? frontier : Point{(N + 1) / 2, (M + 1) / 2};
    while (max.x > 0 && !cols[region][max.x])
      --max.x;
    while (max.y > 0 && !rows[region][max.y])
      --max.y;
    if (revised)
      frontier = max;
    return max;
  }
  int external(bool column) const {
    int bound = (column ? gx : gy) / 2;
    for (int t = 1; t <= bound; ++t)
      if (blocked(column ? Point{t, 0} : Point{0, t}))
        return t - 1;
    return bound;
  }
  // Price a boundary-port choice by its effect on the remaining terminals.
  // The estimate ignores intersections and shared ports; it is not an oracle.
  bool choose_column(const Path &cx, const Path &cy, Point n, int tx, int ty) {
    long long lx = length(cx), ly = length(cy);
    if (n.x > 2 * std::min(N, M) || n.y > 2 * std::min(N, M))
      return lx <= ly;
    auto cost = [](Point p, int a, int b) -> long long {
      return std::min(p.y + std::max(0, p.x - a), p.x + std::max(0, p.y - b));
    };
    Point px = cx.back(), py = cy.back();
    const auto &c = counts[region];
    auto prefix = [&](int x, int y) { return c.prefix(x, y, decision_work); };
    int x0 = (tx + d - 1) / d, y0 = (ty + d - 1) / d;
    int x_limit = ty > tx ? c.width : (ty - 1) / d;
    int y_limit = tx > ty ? c.height : (tx - 1) / d;
    int loss_x = prefix(c.width, y_limit) - prefix(x0 - 1, y_limit);
    int loss_y = prefix(x_limit, c.height) - prefix(x_limit, y0 - 1);
    long long ax = lx + loss_x - cost(px, tx - 1, ty);
    long long ay = ly + loss_y - cost(py, tx, ty - 1);
    return ax != ay ? ax < ay : (lx != ly ? lx < ly : tx >= ty);
  }
  // Algorithm 4. Baseline alpha = 1.1; the optional candidate uses alpha = 1.
  bool general(int k) {
    region = k;
    frontier = {(N + 1) / 2, (M + 1) / 2};
    tx_current = external(true);
    ty_current = external(false);
    add_masks();
    while (true) {
      auto n = remaining();
      if (!n.x || !n.y) {
        clear_masks();
        return true;
      }
      int tx = tx_current, ty = ty_current;
      if (tx <= 0 || ty <= 0)
        return false;
      int f =
          port_priority
              ? (tx > ty ? 1 : (ty > tx ? -1 : 0))
              : (10LL * tx > 11LL * ty ? 1 : (10LL * ty > 11LL * tx ? -1 : 0));
      // Peel the long strip first. Only the O(min(N,M)^2) corner may
      // compare two channels; all other channel searches are committed.
      if (revised && (n.x > 2 * std::min(N, M) || n.y > 2 * std::min(N, M)))
        f = n.x > n.y ? 1 : -1;
      auto before = paths.size();
      if (f != 1 && n.y * d <= ty) {
        if (!rule2(false, n.y, std::min(n.x, n.y), 0))
          return false;
      } else if (f != -1 && n.x * d <= tx) {
        if (!rule2(true, n.x, std::min(n.x, n.y), 0))
          return false;
      } else {
        auto cx = revised && f == -1 ? Path{}
                                     : rule1({n.x * d, M * d}, {tx, 0}, true);
        auto cy = revised && f == 1 ? Path{}
                                    : rule1({N * d, n.y * d}, {0, ty}, false);
        if ((f != 1 && cy.empty()) || (f != -1 && cx.empty()))
          return false;
        if (revised) {
          bool column = f ? f == 1 : choose_column(cx, cy, n, tx, ty);
          commit(column ? cx : cy);
        } else if (f == 1 || (f == 0 && length(cx) <= length(cy))) {
          commit(cx);
          // The two tentative channels may reach the same terminal. The paper
          // leaves this case implicit; never commit the same terminal twice.
          if (f == 0 && available(cy.back()) &&
              distance(cy.back(), {0, ty}) <= distance(cy.back(), {tx, 0}))
            commit(cy);
        } else {
          commit(cy);
          if (f == 0 && available(cx.back()) &&
              distance(cx.back(), {tx, 0}) <= distance(cx.back(), {0, ty}))
            commit(cx);
        }
      }
      if (paths.size() == before)
        return false;
    }
  }
  // Algorithm 5: reuse opposite regions only when their terminal counts match.
  bool run() {
    if (!central())
      return false;
    balance_axes();
    size_t central_count = paths.size();
    for (int k = 0; k < 4; ++k) {
      if (k > 1 && sizes[k] == sizes[3 - k]) {
        region = -1;
        auto count = paths.size();
        for (size_t i = central_count; i < count; ++i)
          if (owner[terminal_global(paths[i].back())] == 3 - k) {
            Path c = paths[i];
            for (auto &p : c)
              p = {gx - p.x, gy - p.y};
            commit(c);
          }
      } else if (!general(k))
        return false;
    }
    return paths.size() == size_t(N) * M;
  }
  void write(const std::string &file) const {
    std::ofstream out(file);
    out.exceptions(std::ios::failbit | std::ios::badbit);
    out << "{\"N\":" << N << ",\"M\":" << M << ",\"d\":" << d
        << ",\"total_length\":" << total << ",\"paths\":[";
    for (size_t i = 0; i < paths.size(); ++i) {
      if (i)
        out << ',';
      out << '[';
      for (size_t j = 0; j < paths[i].size(); ++j) {
        if (j)
          out << ',';
        out << '[' << paths[i][j].x << ',' << paths[i][j].y << ']';
      }
      out << ']';
    }
    out << "]}\n";
    out.flush();
  }
};
