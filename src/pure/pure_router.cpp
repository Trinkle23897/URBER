// Bounded geometric replay, with no flow solver or residual graph dependency.
#include "../routing_types.hpp"
#include "../verify.hpp"
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

struct ReplayConfig {
  int phase, alpha, mode, tie;
};

class PureReplay {
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
  ReplayConfig rules;
  Point frontier{0, 0};
  long long replay_hard_limit = std::numeric_limits<long long>::max();
  PureReplay(int n, int m, int pitch, bool prioritize_ports,
             ReplayConfig config)
      : N(n), M(m), d(pitch), gx((n + 1) * pitch), gy((m + 1) * pitch),
        occupied((uint64_t(gx + 1) * (gy + 1) + 63) / 64),
        owner((n + 1) * (m + 1)), routed(owner.size(), false),
        port_priority(prioritize_ports), rules(config) {
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
    int phase = rules.phase;
    int x_phase = (phase >> 1) & 1, y_phase = phase & 1;
    int a = 2 * x - (N + 1), b = 2 * y - (M + 1);
    if (a && b)
      return (a > 0) + 2 * (b > 0);
    if (!a && b < 0)
      return (y + y_phase) % 2 ? 0 : 1;
    if (!a && b > 0)
      return (M - y + y_phase) % 2 ? 2 : 3;
    if (a < 0 && !b)
      return (x + x_phase) % 2 ? 2 : 0;
    if (a > 0 && !b)
      return (N - x + x_phase) % 2 ? 3 : 1;
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
  Path rule1(Point target, Point start, bool column) {
    if (rule_work >= replay_hard_limit)
      return {};
    Point p = start;
    Path c{p};
    int previous = -1;
    int side = column ? sign(target.x - start.x) : sign(target.y - start.y);
    if (blocked(p))
      return {};
    for (int steps = 0; steps < gx + gy + 2; ++steps) {
      ++rule_work;
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
          ++rule_work;
          ++rule_work;
          p.x += dx;
          p.y += dy;
        }
      }
      if (blocked_global(p))
        throw std::runtime_error("channel intersection at corner");
      set_global(p);
      ++rule_work;
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
      if (!rule2(true, (N + 1) / 2, std::min({2 * d - 1, lm, lm}), 0))
        return false;
    } else {
      if (!rule2(true, N / 2, std::min(d, lm), 0) ||
          !rule2(true, N / 2 + 1, lm, 1))
        return false;
    }
    if (M % 2) {
      if (!rule2(false, (M + 1) / 2, std::min({2 * d - 1, ln, ln}), 1))
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
    bool cached = rules.mode == 3 || rules.mode == 4;
    Point max = cached ? frontier : Point{(N + 1) / 2, (M + 1) / 2};
    while (max.x > 0 && !cols[region][max.x])
      --max.x;
    while (max.y > 0 && !rows[region][max.y])
      --max.y;
    if (cached)
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
  // Algorithm 4. Baseline alpha = 1.1; the optional candidate uses alpha = 1.
  // Weighted grid visits control effort, not a complete instruction count.
  // A separate fixed replay limit also bounds the number of reconstructions.
  long long rule_work = 0;
  int accepted_replays = 0;
  int replay_attempts = 0;
  struct Step {
    size_t size;
    int tx, ty;
    Point n;
    int action = 0;
    bool operator==(const Step &o) const {
      return size == o.size && tx == o.tx && ty == o.ty && n == o.n &&
             action == o.action;
    }
  };
  std::vector<Step> trace, replay_plan;
  std::vector<int> plan_epoch;
  int epoch = 1;
  void undo_to(size_t count) {
    while (paths.size() > count) {
      auto &c = paths.back();
      for (size_t i = 0; i < c.size(); ++i) {
        Point p = c[i];
        if (i) {
          auto a = c[i - 1];
          int dx = sign(p.x - a.x), dy = sign(p.y - a.y);
          p = {a.x + dx, a.y + dy};
          while (!(p == c[i])) {
            set_global(p, false);
            ++rule_work;
            p.x += dx;
            p.y += dy;
          }
        }
        set_global(p, false);
        ++rule_work;
      }
      int t = terminal_global(c.back()), k = owner[t];
      int x = c.back().x / d, y = c.back().y / d;
      ++cols[k][k & 1 ? N + 1 - x : x];
      ++rows[k][k & 2 ? M + 1 - y : y];
      if (rules.mode == 3 || rules.mode == 4) {
        frontier.x = std::max(frontier.x, k & 1 ? N + 1 - x : x);
        frontier.y = std::max(frontier.y, k & 2 ? M + 1 - y : y);
      }
      routed[t] = false;
      total -= length(c);
      paths.pop_back();
    }
  }
  // Actions 1/2 route one channel; 3/4 finish its column/row before resuming.
  bool step(int forced = 0) {
    if (forced >= 3) {
      auto original = remaining();
      while (true) {
        auto n = remaining();
        if ((forced == 3 ? n.x != original.x : n.y != original.y) || !n.x ||
            !n.y)
          return true;
        if (!step(forced - 2))
          return false;
      }
    }
    auto n = remaining();
    int tx = tx_current, ty = ty_current;
    if (tx <= 0 || ty <= 0)
      return false;
    int f = port_priority
                ? sign(tx - ty)
                : (100LL * tx > rules.alpha * 1LL * ty
                       ? 1
                       : (100LL * ty > rules.alpha * 1LL * tx ? -1 : 0));
    size_t before = paths.size();
    if (!forced && f != 1 && n.y * d <= ty) {
      if (!rule2(false, n.y, std::min(n.x, n.y), 0))
        return false;
    } else if (!forced && f != -1 && n.x * d <= tx) {
      if (!rule2(true, n.x, std::min(n.x, n.y), 0))
        return false;
    } else {
      auto cx = rule1({n.x * d, M * d}, {tx, 0}, true);
      auto cy = rule1({N * d, n.y * d}, {0, ty}, false);
      if (forced) {
        auto &c = forced == 1 ? cx : cy;
        if (c.empty())
          return false;
        commit(std::move(c));
      } else {
        if ((f != 1 && cy.empty()) || (f != -1 && cx.empty()))
          return false;
        if (f == 1 || (f == 0 && length(cx) <= length(cy))) {
          commit(cx);
          if (rules.mode == 5 && f == 0 && available(cy.back()) &&
              distance(cy.back(), {0, ty}) <= distance(cy.back(), {tx, 0}))
            commit(cy);
        } else {
          commit(cy);
          if (rules.mode == 5 && f == 0 && available(cx.back()) &&
              distance(cx.back(), {tx, 0}) <= distance(cx.back(), {0, ty}))
            commit(cx);
        }
      }
    }
    return paths.size() > before;
  }
  bool finish(int forced = 0) {
    while (true) {
      auto n = remaining();
      if (!n.x || !n.y)
        return true;
      // Retain successful later decisions when an earlier choice changes.
      // The same frontier and routed count are a heuristic match; all geometry
      // is reconstructed and the complete selected routing is verified.
      if (rules.mode >= 3 && !forced && plan_epoch[paths.size()] == epoch &&
          replay_plan[paths.size()].n == n)
        forced = replay_plan[paths.size()].action;
      trace.push_back({paths.size(), tx_current, ty_current, n, forced});
      if (!step(forced))
        return false;
      forced = 0;
    }
  }
  bool general(int k) {
    region = k;
    frontier = {(N + 1) / 2, (M + 1) / 2};
    tx_current = external(true);
    ty_current = external(false);
    add_masks();
    trace.clear();
    if (rules.mode >= 3) {
      replay_plan.resize(size_t(N) * M + 1);
      plan_epoch.assign(size_t(N) * M + 1, 0);
      epoch = 1;
    }
    if (!finish())
      return false;
    if (rules.mode == 5) {
      clear_masks();
      return true;
    }
    int replay_base = rules.mode == 0 ? 0 : replay_attempts;
    long long budget =
        (rules.mode == 0 ? 0 : rule_work) + (rules.mode == 0   ? 16
                                             : rules.mode == 1 ? 64
                                             : rules.mode <= 3 ? 256
                                                               : 1024) *
                                                1LL * (gx + 1) * (gy + 1);
    for (int pass = 0; pass < (rules.mode == 3   ? 2
                               : rules.mode >= 2 ? 8
                                                 : 3);
         ++pass) {
      auto pass_paths = paths;
      auto pass_trace = trace;
      bool changed = false;
      for (int i = int(trace.size()) - 1; i >= 0; --i) {
        if (rule_work >= budget ||
            replay_attempts - replay_base >= (rules.mode >= 3 ? 16384 : 4096))
          break;
        auto st = trace[i];
        if (std::max(st.n.x, st.n.y) >
            (rules.mode >= 3 ? 2 : 1) * (std::min(N, M) + 1) / 2)
          continue;
        for (int action = 1; action <= (rules.mode == 0 ? 2 : 4); ++action) {
          size_t end =
              (i + 1 < int(trace.size()) ? trace[i + 1].size : paths.size());
          Point start = global(paths[st.size].front());
          if (end == st.size + 1 && action == (start.y == 0 ? 1 : 2))
            continue;
          ++replay_attempts;
          if (rules.mode >= 3) {
            ++epoch;
            for (const auto &entry : trace)
              if (entry.action) {
                replay_plan[entry.size] = entry;
                plan_epoch[entry.size] = epoch;
              }
          }
          long long best = total;
          std::vector<Path> suffix(paths.begin() + st.size, paths.end());
          std::vector<Step> tail(trace.begin() + i, trace.end());
          undo_to(st.size);
          tx_current = st.tx;
          ty_current = st.ty;
          trace.resize(i);
          // Stop an unexpectedly expensive replay between channel searches.
          // One search or commit visits at most O(G) points. Restoration is
          // also O(G), so a last replay cannot escape the fixed grid budget.
          if (rules.mode == 3 || rules.mode == 4)
            replay_hard_limit = static_cast<long long>(std::min<__int128>(
                std::numeric_limits<long long>::max(),
                __int128(budget) + __int128(4096) * (gx + 1) * (gy + 1)));
          bool ok = finish(action);
          replay_hard_limit = std::numeric_limits<long long>::max();
          // Neutral moves can expose an improvement in the next pass.
          // Neither neutral nor descending replay ever increases the incumbent.
          if (ok && (total < best || (rules.mode >= 2 && total == best &&
                                      action == rules.tie))) {
            ++accepted_replays;
            changed = true;
          } else {
            undo_to(st.size);
            tx_current = st.tx;
            ty_current = st.ty;
            for (auto &c : suffix) {
              for (auto &p : c)
                p = global(p);
              commit(std::move(c));
            }
            trace.resize(i);
            trace.insert(trace.end(), tail.begin(), tail.end());
          }
        }
      }
      // An identical route and decision trace repeats deterministically.
      if (!changed || (paths == pass_paths && trace == pass_trace))
        break;
    }
    clear_masks();
    return true;
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
};

int main(int argc, char **argv) {
  try {
    if (argc < 4)
      throw std::invalid_argument(
          "usage: pure_replay N M d [paths.json] [--mode "
          "all|single|strip|neutral|guided|deep|baseline] [--phase 0..3] "
          "[--alpha 100..1000] [--tie 1|2]");
    int n = std::stoi(argv[1]), m = std::stoi(argv[2]), d = std::stoi(argv[3]);
    if (n < 1 || m < 1 || d < 1 ||
        (n + 1LL) * (m + 1LL) > std::numeric_limits<int>::max() ||
        (n + m + 2LL) * d + 2 > std::numeric_limits<int>::max())
      throw std::invalid_argument(
          "positive dimensions and int32 grid coordinates required");
    if (2LL * d >= std::min(n, m))
      throw std::invalid_argument("use pure_fan for 2*d >= min(N,M)");
    std::vector<int> modes{0, 1, 2}, phases{0, 1, 2, 3}, alphas{110, 120};
    int tie = 1;
    std::vector<int> candidates_to_run{0, 1, 2, 3};
    std::string output;
    for (int i = 4; i < argc; ++i) {
      std::string a = argv[i];
      if (a == "--mode" || a == "--phase" || a == "--alpha" || a == "--tie" ||
          a == "--candidate") {
        if (++i >= argc)
          throw std::invalid_argument("missing option value");
        std::string v = argv[i];
        if (a == "--mode") {
          if (v == "single")
            modes = {0};
          else if (v == "strip")
            modes = {1};
          else if (v == "neutral")
            modes = {2};
          else if (v == "guided")
            modes = {3};
          else if (v == "deep")
            modes = {4};
          else if (v == "baseline")
            modes = {5};
          else if (v != "all")
            throw std::invalid_argument("unknown replay mode");
        } else if (a == "--phase") {
          int p = std::stoi(v);
          if (p < 0 || p > 3)
            throw std::invalid_argument("phase must be 0..3");
          phases = {p};
        } else if (a == "--alpha") {
          int p = std::stoi(v);
          if (p < 100 || p > 1000)
            throw std::invalid_argument("alpha must be 100..1000");
          alphas = {p};
        } else if (a == "--candidate") {
          int c = std::stoi(v);
          if (c < 0 || c > 3)
            throw std::invalid_argument("candidate must be 0..3");
          candidates_to_run = {c};
        } else {
          tie = std::stoi(v);
          if (tie != 1 && tie != 2)
            throw std::invalid_argument("tie must be 1 or 2");
        }
      } else if (output.empty() && a.rfind("--", 0) != 0)
        output = a;
      else
        throw std::invalid_argument("unknown argument");
    }
    bool canonical_transposed = n < m;
    if (canonical_transposed)
      std::swap(n, m);
    auto started = std::chrono::steady_clock::now();
    std::vector<Path> best;
    long long best_length = std::numeric_limits<long long>::max(), work = 0,
              attempts = 0, accepted = 0;
    ReplayConfig selected{};
    bool selected_transposed = false, selected_priority = false;
    int candidates = 0;
    for (int mode : modes)
      for (int phase : phases)
        for (int alpha : alphas)
          for (int v : candidates_to_run) {
            bool transposed = v & 2, priority = v & 1;
            ReplayConfig config{phase, alpha, mode, tie};
            PureReplay r(transposed ? m : n, transposed ? n : m, d, priority,
                         config);
            ++candidates;
            try {
              if (r.run() && r.total < best_length) {
                if (transposed)
                  for (auto &path : r.paths)
                    for (auto &p : path)
                      std::swap(p.x, p.y);
                verify(n, m, d, r.paths, r.total);
                best = std::move(r.paths);
                best_length = r.total;
                selected = config;
                selected_transposed = transposed;
                selected_priority = priority;
              }
            } catch (const std::runtime_error &) { /* A failed constructive
                                                      candidate is discarded. */
            }
            work += r.rule_work;
            attempts += r.replay_attempts;
            accepted += r.accepted_replays;
          }
    if (best.empty())
      throw std::runtime_error("all constructive candidates failed");
    if (canonical_transposed) {
      std::swap(n, m);
      for (auto &path : best)
        for (auto &p : path)
          std::swap(p.x, p.y);
    }
    verify(n, m, d, best, best_length);
    if (!output.empty()) {
      std::ofstream out(output);
      out.exceptions(std::ios::badbit | std::ios::failbit);
      out << "{\"N\":" << n << ",\"M\":" << m << ",\"d\":" << d
          << ",\"total_length\":" << best_length << ",\"paths\":[";
      for (size_t i = 0; i < best.size(); ++i) {
        if (i)
          out << ',';
        out << '[';
        for (size_t j = 0; j < best[i].size(); ++j) {
          if (j)
            out << ',';
          out << '[' << best[i][j].x << ',' << best[i][j].y << ']';
        }
        out << ']';
      }
      out << "]}\n";
    }
    double seconds = std::chrono::duration<double>(
                         std::chrono::steady_clock::now() - started)
                         .count();
    std::cout << "{\"N\":" << n << ",\"M\":" << m << ",\"d\":" << d
              << ",\"verified\":true,\"total_length\":" << best_length
              << ",\"seconds\":" << seconds
              << ",\"method\":\"pure_geometric_replay\",\"optimality_"
                 "certified\":false,\"polished\":false,\"residual_work\":0"
              << ",\"candidates\":" << candidates
              << ",\"replay_attempts\":" << attempts
              << ",\"accepted_replays\":" << accepted
              << ",\"weighted_grid_visits\":" << work
              << ",\"selected_mode\":" << selected.mode
              << ",\"selected_phase\":" << selected.phase
              << ",\"selected_alpha\":" << selected.alpha
              << ",\"selected_transposed\":"
              << (selected_transposed ? "true" : "false")
              << ",\"selected_port_priority\":"
              << (selected_priority ? "true" : "false") << "}\n";
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
