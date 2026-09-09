#pragma once

#include <cstdlib>
#include <vector>

struct Point {
  int x, y;
  bool operator==(const Point &p) const { return x == p.x && y == p.y; }
};
using Path = std::vector<Point>;
inline long long distance(Point a, Point b) {
  return std::abs(a.x - b.x) + std::abs(a.y - b.y);
}
inline long long length(const Path &p) {
  long long n = 0;
  for (size_t i = 1; i < p.size(); ++i)
    n += distance(p[i - 1], p[i]);
  return n;
}
inline int sign(int x) { return (x > 0) - (x < 0); }
