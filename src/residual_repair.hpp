#pragma once

#include "routing_types.hpp"
#include <algorithm>
#include <cstdint>
#include <deque>
#include <limits>
#include <stdexcept>

struct Residual {
  int width, height, cells, sink;
  std::vector<int8_t> next, prev;
  std::vector<uint8_t> used;
  std::vector<int> terminals;
  int moves[5];
  std::vector<long long> labels;
  long long work = 0;
  bool exhausted = false;
  Residual(int n, int m, int d, const std::vector<Path> &paths)
      : width((n + 1) * d + 1), height((m + 1) * d + 1), cells(width * height),
        sink(2 * cells), next(cells), prev(cells), used(cells) {
    moves[1] = 1;
    moves[2] = -1;
    moves[3] = width;
    moves[4] = -width;
    for (const auto &p : paths) {
      int last = p.back().y * width + p.back().x;
      terminals.push_back(last);
      used[last] = 1;
      prev[last] = 5;
      for (int j = int(p.size()) - 2; j >= 0; --j) {
        int target = p[j].y * width + p[j].x;
        int dir = p[j].x != last % width ? (target > last ? 1 : 2)
                                         : (target > last ? 3 : 4);
        while (last != target) {
          int v = last + moves[dir];
          next[last] = dir;
          prev[v] = opposite(dir);
          used[v] = 1;
          last = v;
        }
      }
      next[last] = 5;
    }
  }
  int opposite(int dir) const { return ((dir - 1) ^ 1) + 1; }
  bool boundary(int v) const {
    return v < width || v >= cells - width || v % width == 0 ||
           v % width == width - 1;
  }
  int direction(int from, int to) const {
    for (int d = 1; d <= 4; ++d)
      if (from + moves[d] == to)
        return d;
    throw std::runtime_error("nonadjacent residual edge");
  }
  bool check_certificate(const std::vector<long long> &potential,
                         long long inf) const {
    long long ceiling = 0;
    for (auto p : potential)
      if (p != inf)
        ceiling = std::max(ceiling, p);
    auto price = [&](int v) {
      return potential[v] == inf ? ceiling : potential[v];
    };
    auto feasible = [&](int u, int v, int cost) {
      return cost + price(u) - price(v) >= 0;
    };
    for (int v = 0; v < cells; ++v) {
      if (used[v] && (potential[2 * v] == inf || potential[2 * v + 1] == inf))
        return false;
      if (!used[v] && !feasible(2 * v, 2 * v + 1, 0))
        return false;
      if (prev[v] > 0 && prev[v] < 5 &&
          !feasible(2 * v, 2 * (v + moves[prev[v]]) + 1, -1))
        return false;
      if (used[v] && !feasible(2 * v + 1, 2 * v, 0))
        return false;
      if (boundary(v)) {
        if (next[v] == 5) {
          if (!feasible(sink, 2 * v + 1, 0))
            return false;
        } else if (!feasible(2 * v + 1, sink, 0))
          return false;
      } else {
        for (int dir = 1; dir <= 4; ++dir)
          if (next[v] != dir && !feasible(2 * v + 1, 2 * (v + moves[dir]), 1))
            return false;
      }
    }
    return true;
  }
  // Any negative predecessor cycle is an exact improving residual cycle.
  int negative_cycle(const std::vector<int> &parent) const {
    std::vector<uint8_t> color(sink + 1);
    for (int root = 0; root <= sink; ++root) {
      if (color[root])
        continue;
      int v = root;
      while (v >= 0 && !color[v]) {
        color[v] = 1;
        v = parent[v];
      }
      if (v >= 0 && color[v] == 1) {
        int p = v;
        long long cost = 0;
        do {
          int u = parent[p];
          if (u != sink && p != sink && u / 2 != p / 2)
            cost += (u & 1) ? 1 : -1;
          p = u;
        } while (p != v);
        if (cost < 0)
          return v;
      }
      v = root;
      while (v >= 0 && color[v] == 1) {
        color[v] = 2;
        v = parent[v];
      }
    }
    return -1;
  }
  bool improve(int multiplier, bool slf, long long &gain) {
    const long long inf = std::numeric_limits<long long>::max() / 4;
    // Start with minus Manhattan distance to an unused boundary port.
    // These are tentative labels, not an optimality certificate.
    if (labels.empty()) {
      labels.resize(sink + 1);
      auto boundary_distance = [&](int start, int stride, int size) {
        std::vector<int> result(size, width + height);
        for (int i = 1; i < size - 1; ++i)
          if (next[start + i * stride] != 5)
            result[i] = 0;
        for (int i = 1; i < size; ++i)
          result[i] = std::min(result[i], result[i - 1] + 1);
        for (int i = size - 2; i >= 0; --i)
          result[i] = std::min(result[i], result[i + 1] + 1);
        return result;
      };
      auto bottom = boundary_distance(0, 1, width);
      auto top = boundary_distance(cells - width, 1, width);
      auto left = boundary_distance(0, width, height);
      auto right = boundary_distance(width - 1, width, height);
      for (int v = 0; v < cells; ++v) {
        int x = v % width, y = v / width;
        labels[2 * v] = labels[2 * v + 1] =
            -std::min({y + bottom[x], height - 1 - y + top[x], x + left[y],
                       width - 1 - x + right[y]});
      }
      labels[sink] = 0;
    }
    auto &distance = labels;
    std::vector<int> parent(sink + 1, -1);
    std::vector<uint8_t> queued(sink + 1);
    std::deque<int> queue;
    // Queue every initially violated edge tail. Decreasing a label later
    // requeues its outgoing edges; other constraints remain satisfied.
    auto seed = [&](int u, int v, int cost) {
      if (distance[u] + cost >= distance[v] || queued[u])
        return;
      queued[u] = 1;
      if (slf && !queue.empty() && distance[u] < distance[queue.front()])
        queue.push_front(u);
      else
        queue.push_back(u);
    };
    for (int v = 0; v < cells; ++v) {
      if (!used[v])
        seed(2 * v, 2 * v + 1, 0);
      if (prev[v] > 0 && prev[v] < 5)
        seed(2 * v, 2 * (v + moves[prev[v]]) + 1, -1);
      if (used[v])
        seed(2 * v + 1, 2 * v, 0);
      if (boundary(v)) {
        if (next[v] == 5)
          seed(sink, 2 * v + 1, 0);
        else
          seed(2 * v + 1, sink, 0);
      } else {
        for (int dir = 1; dir <= 4; ++dir)
          if (next[v] != dir)
            seed(2 * v + 1, 2 * (v + moves[dir]), 1);
      }
    }
    long long budget = 1LL * multiplier * cells;
    bool found = false;
    int cycle_start = sink;
    long long scan_interval = cells, next_scan = cells;
    auto relax = [&](int u, int v, int cost) {
      ++work;
      if (distance[v] <= distance[u] + cost)
        return;
      distance[v] = distance[u] + cost;
      parent[v] = u;
      if (!queued[v]) {
        queued[v] = 1;
        if (slf && !queue.empty() && distance[v] < distance[queue.front()])
          queue.push_front(v);
        else
          queue.push_back(v);
      }
    };
    while (!queue.empty() && work < budget && !found) {
      if (work >= next_scan && work + cells < budget) {
        cycle_start = negative_cycle(parent);
        // Charge periodic O(G) predecessor scans to the same shared budget.
        work += cells;
        scan_interval = std::min(16LL * cells, 2 * scan_interval);
        next_scan = work + scan_interval;
        if (cycle_start >= 0) {
          found = true;
          break;
        }
        cycle_start = sink;
      }
      int u = queue.front();
      queue.pop_front();
      queued[u] = 0;
      if (u == sink) {
        for (int x = 0; x < width; ++x) {
          for (int v : {x, cells - width + x})
            if (next[v] == 5)
              relax(u, 2 * v + 1, 0);
        }
        for (int y = 1; y < height - 1; ++y) {
          for (int v : {y * width, y * width + width - 1})
            if (next[v] == 5)
              relax(u, 2 * v + 1, 0);
        }
      } else {
        int v = u / 2;
        if (!(u & 1)) {
          if (!used[v])
            relax(u, u + 1, 0);
          if (prev[v] > 0 && prev[v] < 5)
            relax(u, 2 * (v + moves[prev[v]]) + 1, -1);
        } else {
          if (used[v])
            relax(u, u - 1, 0);
          if (boundary(v)) {
            if (next[v] != 5)
              relax(u, sink, 0);
          } else {
            for (int dir = 1; dir <= 4; ++dir)
              if (next[v] != dir)
                relax(u, 2 * (v + moves[dir]), 1);
          }
        }
      }
    }
    exhausted = queue.empty() && !found && check_certificate(distance, inf);
    if (exhausted)
      return false;
    if (!found) {
      // A negative cycle can trap label correction before its gain reaches the
      // sink. Inspect the entire predecessor forest once, in linear time.
      cycle_start = negative_cycle(parent);
      found = cycle_start >= 0;
    }
    if (!found)
      return false;
    std::vector<int> cycle;
    std::vector<uint8_t> seen(sink + 1);
    int p = cycle_start;
    while (!seen[p]) {
      seen[p] = 1;
      cycle.push_back(p);
      p = parent[p];
      if (p < 0)
        throw std::runtime_error("broken residual predecessor");
    }
    // The predecessor chain may itself enter a negative cycle before the sink.
    cycle.erase(cycle.begin(), std::find(cycle.begin(), cycle.end(), p));
    long long cost = 0;
    for (int v : cycle) {
      int u = parent[v];
      if (u != sink && v != sink && u / 2 != v / 2)
        cost += (u & 1) ? 1 : -1;
    }
    if (cost >= 0)
      return false;
    // Clear reverse arcs first; then install forwards, preserving replacements.
    for (int v : cycle) {
      int u = parent[v];
      if (u == sink)
        next[v / 2] = 0;
      else if (v == sink) {
      } else if (u / 2 == v / 2) {
        if (u & 1)
          used[u / 2] = 0;
      } else if (!(u & 1)) {
        next[v / 2] = 0;
        prev[u / 2] = 0;
      }
    }
    for (int v : cycle) {
      int u = parent[v];
      if (u == sink) {
      } else if (v == sink)
        next[u / 2] = 5;
      else if (u / 2 == v / 2) {
        if (!(u & 1))
          used[u / 2] = 1;
      } else if (u & 1) {
        int d = direction(u / 2, v / 2);
        next[u / 2] = d;
        prev[v / 2] = opposite(d);
      }
    }
    gain = -cost;
    return true;
  }
  std::vector<Path> paths() const {
    std::vector<Path> result;
    for (int t : terminals) {
      Path p{{t % width, t / width}};
      int v = t, lastdir = 0, steps = 0;
      while (next[v] != 5) {
        if (next[v] < 1 || next[v] > 4 || ++steps > cells)
          throw std::runtime_error("broken repaired path");
        int d = next[v];
        if (lastdir && d != lastdir)
          p.push_back({v % width, v / width});
        lastdir = d;
        v += moves[d];
      }
      p.push_back({v % width, v / width});
      std::reverse(p.begin(), p.end());
      result.push_back(std::move(p));
    }
    return result;
  }
};
