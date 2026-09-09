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
  bool port_priority;
  Router(int n, int m, int pitch, bool prioritize_ports = false)
      : N(n), M(m), d(pitch), gx((n + 1) * pitch), gy((m + 1) * pitch),
        occupied((uint64_t(gx + 1) * (gy + 1) + 63) / 64),
        owner((n + 1) * (m + 1)), routed(owner.size(), false),
        port_priority(prioritize_ports) {
    for (int k = 0; k < 4; ++k) {
      rows[k].resize(M + 1);
      cols[k].resize(N + 1);
    }
    for (int x = 1; x <= N; ++x)
      for (int y = 1; y <= M; ++y) {
        int k = assignment(x, y);
        owner[x * (M + 1) + y] = k;
        ++sizes[k];
        ++cols[k][k & 1 ? N + 1 - x : x];
        ++rows[k][k & 2 ? M + 1 - y : y];
      }
  }
  // Section III-C: the nine terminal assignment rules, including odd axes.
  int assignment(int x, int y) const {
    int a = 2 * x - (N + 1), b = 2 * y - (M + 1);
    if (a && b)
      return (a > 0) + 2 * (b > 0);
    if (!a && b < 0)
      return y % 2 ? 0 : 1;
    if (!a && b > 0)
      return (M - y) % 2 ? 2 : 3;
    if (a < 0 && !b)
      return x % 2 ? 2 : 0;
    if (a > 0 && !b)
      return (N - x) % 2 ? 3 : 1;
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
      if (!rule2(false, (M + 1) / 2, std::min(2 * d - 1, ln), 1))
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
  Point remaining() const {
    Point max{(N + 1) / 2, (M + 1) / 2};
    while (max.x > 0 && !cols[region][max.x])
      --max.x;
    while (max.y > 0 && !rows[region][max.y])
      --max.y;
    return max;
  }
  int external(bool column) const {
    int bound = (column ? gx : gy) / 2;
    for (int t = 1; t <= bound; ++t)
      if (blocked(column ? Point{t, 0} : Point{0, t}))
        return t - 1;
    return bound;
  }
  // Algorithm 4. Baseline alpha = 1.1; the optional candidate uses alpha = 1.
  bool general(int k) {
    region = k;
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
      auto before = paths.size();
      if (f != 1 && n.y * d <= ty) {
        if (!rule2(false, n.y, std::min(n.x, n.y), 0))
          return false;
      } else if (f != -1 && n.x * d <= tx) {
        if (!rule2(true, n.x, std::min(n.x, n.y), 0))
          return false;
      } else {
        auto cx = rule1({n.x * d, M * d}, {tx, 0}, true);
        auto cy = rule1({N * d, n.y * d}, {0, ty}, false);
        if ((f != 1 && cy.empty()) || (f != -1 && cx.empty()))
          return false;
        if (f == 1 || (f == 0 && length(cx) <= length(cy))) {
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
#include "residual_repair.hpp"

// A simple feasible seed when the pitch fits half the shorter dimension.
// Adjacent columns occupy disjoint strips; the two row halves escape in
// opposite directions. It is only used if all rule-based candidates fail.
std::vector<Path> fan_routes(int n, int m, int d) {
  bool transpose = n < m;
  if (transpose)
    std::swap(n, m);
  std::vector<Path> paths;
  if (d < (m + 1) / 2)
    return paths;
  for (int x = 1; x <= n; ++x)
    for (int y = 1; y <= m; ++y) {
      bool bottom = y <= (m + 1) / 2;
      int offset = bottom ? 1 - y : m - y;
      int port = x * d + offset;
      Path path{{port, bottom ? 0 : (m + 1) * d}};
      if (offset)
        path.push_back({port, y * d});
      path.push_back({x * d, y * d});
      if (transpose)
        for (auto &point : path)
          std::swap(point.x, point.y);
      paths.push_back(std::move(path));
    }
  return paths;
}
#include "verify.hpp"

int main(int argc, char **argv) {
  if (argc < 4) {
    std::cerr << "usage: urber N M d [paths.json] [--improved | --polish]\n";
    return 2;
  }
  try {
    int n = std::stoi(argv[1]), m = std::stoi(argv[2]), d = std::stoi(argv[3]);
    if (n < 1 || m < 1 || d < 1 ||
        (n + 1LL) * (m + 1LL) > std::numeric_limits<int>::max() ||
        (n + m + 2LL) * d + 2 > std::numeric_limits<int>::max())
      throw std::invalid_argument(
          "require N,M >= 1, d >= 1 and grid coordinates fitting int32");
    bool improved = false;
    bool polish = false;
    std::string output;
    for (int i = 4; i < argc; ++i)
      if (std::string(argv[i]) == "--improved")
        improved = true;
      else if (std::string(argv[i]) == "--polish")
        improved = polish = true;
      else if (output.empty())
        output = argv[i];
      else
        throw std::invalid_argument("only one output path is accepted");
    // Use one orientation for a rectangle and its transpose, including the
    // residual search's scan/queue order. Convert only the final geometry back.
    bool canonical_transposed = improved && n < m;
    if (canonical_transposed)
      std::swap(n, m);
    auto start = std::chrono::steady_clock::now();
    Router router(n, m, d);
    bool thin = std::min(n, m) <= 2;
    bool ok = false;
    if (thin) {
      // Every terminal is one pitch from a distinct nearest boundary port.
      router.paths = fan_routes(n, m, d);
      for (const auto &path : router.paths)
        router.total += length(path);
      ok = true;
    } else {
      try {
        ok = router.run();
      } catch (const std::runtime_error &error) {
        if (!improved)
          throw;
        std::cerr << "discarding initial candidate: " << error.what() << '\n';
      }
    }
    bool selected_port_priority = false;
    bool selected_transposed = false;
    bool selected_fan = thin;
    for (int variant = 1; improved && !thin && variant < 4; ++variant) {
      bool priority = variant & 1, transposed = variant & 2;
      Router candidate(transposed ? m : n, transposed ? n : m, d, priority);
      bool candidate_ok = false;
      try {
        candidate_ok = candidate.run();
        if (candidate_ok && (!ok || candidate.total < router.total)) {
          if (transposed)
            for (auto &path : candidate.paths)
              for (auto &point : path)
                std::swap(point.x, point.y);
          verify(n, m, d, candidate.paths, candidate.total);
        }
      } catch (const std::runtime_error &error) {
        std::cerr << "discarding candidate: " << error.what() << '\n';
        candidate_ok = false;
      }
      if (candidate_ok && (!ok || candidate.total < router.total)) {
        router.paths = std::move(candidate.paths);
        router.total = candidate.total;
        ok = true;
        selected_port_priority = priority;
        selected_transposed = transposed;
      }
    }
    if (!ok && improved) {
      auto paths = fan_routes(n, m, d);
      if (!paths.empty()) {
        router.total = 0;
        for (const auto &path : paths)
          router.total += length(path);
        router.paths = std::move(paths);
        verify(n, m, d, router.paths, router.total);
        ok = selected_fan = true;
      }
    }
    int exchanges = 0;
    long long residual_work = 0;
    bool certified = false, budget_limited = false;
    if (ok && polish) {
      if (1LL * (router.gx + 1) * (router.gy + 1) >=
          std::numeric_limits<int>::max() / 2)
        throw std::invalid_argument(
            "--polish requires fewer than 2^30 grid cells");
      const long long grid_cells = 1LL * (router.gx + 1) * (router.gy + 1);
      long long remaining_work = 8192 * grid_cells;
      budget_limited = true;
      std::vector<long long> labels;
      while (remaining_work >= 2 * grid_cells) {
        Residual residual(n, m, d, router.paths);
        residual.labels = std::move(labels);
        long long gain = 0;
        int allowance = int(std::min(1024LL, remaining_work / grid_cells - 1));
        bool changed = residual.improve(allowance, true, gain);
        labels = std::move(residual.labels);
        residual_work += residual.work;
        // Charge one G unit for each O(G) rebuild/verification as well as the
        // actual relaxations. This bounds both total queue work and restarts.
        remaining_work -= residual.work + grid_cells;
        if (!changed) {
          certified = residual.exhausted;
          budget_limited = !certified;
          break;
        }
        auto paths = residual.paths();
        long long total = 0;
        for (const auto &path : paths)
          total += length(path);
        verify(n, m, d, paths, total, false);
        if (total >= router.total)
          throw std::runtime_error(
              "residual exchange failed to decrease length");
        router.paths = std::move(paths);
        router.total = total;
        ++exchanges;
      }
    }
    if (canonical_transposed) {
      for (auto &path : router.paths)
        for (auto &point : path)
          std::swap(point.x, point.y);
      std::swap(n, m);
      std::swap(router.N, router.M);
      std::swap(router.gx, router.gy);
    }
    double time =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
            .count();
    if (ok) {
      router.occupied.clear();
      router.occupied.shrink_to_fit();
      verify(n, m, d, router.paths, router.total, !polish);
    }
    if (ok && !output.empty())
      router.write(output);
    std::cout << "{\"N\":" << n << ",\"M\":" << m << ",\"d\":" << d
              << ",\"success\":" << (ok ? "true" : "false")
              << ",\"verified\":" << (ok ? "true" : "false")
              << ",\"routed\":" << router.paths.size()
              << ",\"total_length\":" << router.total << ",\"seconds\":" << time
              << ",\"improved\":" << (improved ? "true" : "false")
              << ",\"selected_port_priority\":"
              << (selected_port_priority ? "true" : "false")
              << ",\"selected_transposed\":"
              << (selected_transposed ? "true" : "false")
              << ",\"selected_fan\":" << (selected_fan ? "true" : "false")
              << ",\"canonical_transposed\":"
              << (canonical_transposed ? "true" : "false")
              << ",\"polished\":" << (polish ? "true" : "false")
              << ",\"exchanges\":" << exchanges
              << ",\"residual_work\":" << residual_work
              << ",\"residual_optimality_certified\":"
              << (certified ? "true" : "false")
              << ",\"budget_limited\":" << (budget_limited ? "true" : "false")
              << "}\n";
    return ok ? 0 : 1;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
