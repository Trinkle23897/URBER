#pragma once

#include "routing_types.hpp"
#include <cstdint>
#include <stdexcept>

// Independent reconstruction: no access to the router's occupancy or
// assignments.
void verify(int n, int m, int d, const std::vector<Path> &paths,
            long long expected, bool require_monotone = true) {
  int width = (n + 1) * d, height = (m + 1) * d;
  if (paths.size() != size_t(n) * m)
    throw std::runtime_error("verification: missing channels");
  std::vector<uint64_t> seen((uint64_t(width + 1) * (height + 1) + 63) / 64);
  std::vector<bool> terminals(size_t(n) * m);
  long long total = 0;
  for (const auto &path : paths) {
    if (path.size() < 2)
      throw std::runtime_error("verification: empty channel");
    auto end = path.back();
    if (end.x <= 0 || end.x >= width || end.y <= 0 || end.y >= height ||
        end.x % d || end.y % d)
      throw std::runtime_error("verification: invalid internal endpoint");
    int t = (end.x / d - 1) * m + end.y / d - 1;
    if (terminals[t])
      throw std::runtime_error("verification: duplicate terminal");
    terminals[t] = true;
    long long steps = 0;
    for (size_t j = 0; j < path.size(); ++j) {
      Point p = path[j], last = path[j];
      int dx = 0, dy = 0;
      if (j) {
        p = path[j - 1];
        if ((p.x == last.x) == (p.y == last.y))
          throw std::runtime_error(
              "verification: non-axis-aligned or empty segment");
        dx = (last.x > p.x) - (last.x < p.x);
        dy = (last.y > p.y) - (last.y < p.y);
        p.x += dx;
        p.y += dy;
      }
      while (true) {
        if (p.x < 0 || p.x > width || p.y < 0 || p.y > height)
          throw std::runtime_error("verification: outside chip");
        bool boundary = p.x == 0 || p.x == width || p.y == 0 || p.y == height;
        if (boundary != (j == 0))
          throw std::runtime_error(
              "verification: boundary visit inside channel");
        bool internal = !boundary && p.x % d == 0 && p.y % d == 0;
        if (internal && !(j == path.size() - 1 && p == end))
          throw std::runtime_error("verification: passes another terminal");
        uint64_t id = uint64_t(p.y) * (width + 1) + p.x, bit = uint64_t(1)
                                                               << (id % 64);
        if (seen[id / 64] & bit)
          throw std::runtime_error("verification: overlap/crossing");
        seen[id / 64] |= bit;
        if (j)
          ++steps;
        if (p == last)
          break;
        p.x += dx;
        p.y += dy;
      }
    }
    long long manhattan =
        std::abs(path.front().x - end.x) + std::abs(path.front().y - end.y);
    if (require_monotone && steps != manhattan)
      throw std::runtime_error("verification: non-monotone path");
    total += steps;
  }
  if (total != expected)
    throw std::runtime_error("verification: total length mismatch");
}
