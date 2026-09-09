#include "../verify.hpp"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>

// No occupancy search: emit a closed-form, minimum-offset fan in a strip.
template <class Transform>
void fan(std::vector<Path> &paths, int count, int d, Transform transform) {
  for (int rank = 1; rank <= count; ++rank) {
    int a = rank / 2, s = rank % 2 ? -1 : 1;
    Path path{transform(0, s * a)};
    for (int j = 0; j < a; ++j) {
      int u = ((rank % 2 ? 2 : 1) + 2 * j) * d + a - j;
      path.push_back(transform(u, s * (a - j)));
      path.push_back(transform(u, s * (a - j - 1)));
    }
    path.push_back(transform(rank * d, 0));
    paths.push_back(std::move(path));
  }
}

long long formula(int n, int m, int d) {
  long long result = 0;
  int h = (m + 1) / 2;
  for (int x = 1; x <= n; ++x) {
    int c = std::min(x, n + 1 - x), t = std::min(c, h);
    int b = std::min(h, c - 1), a = std::min(m / 2, c - 1);
    result += 1LL * d * t * (m + 1 - t) + 1LL * b * b / 4 + 1LL * a * a / 4;
  }
  for (int y = 1; y <= m; ++y) {
    int k = std::min(y, m + 1 - y);
    result += 2 * (1LL * k * k / 4);
  }
  if (n == m && m % 2)
    result -= h / 2;
  return result;
}

int main(int argc, char **argv) {
  try {
    if (argc < 4 || argc > 5)
      throw std::invalid_argument("usage: pure_fan N M d [paths.json]");
    int original_n = std::stoi(argv[1]), original_m = std::stoi(argv[2]);
    int d = std::stoi(argv[3]);
    int n = std::max(original_n, original_m),
        m = std::min(original_n, original_m);
    if (m < 1 || d < (m + 1) / 2 ||
        1LL * n * m > std::numeric_limits<int>::max() ||
        (1LL * n + m + 2) * d + 2 > std::numeric_limits<int>::max())
      throw std::invalid_argument(
          "requires positive dimensions, d >= ceil(min(N,M)/2)");
    auto start = std::chrono::steady_clock::now();
    std::vector<Path> paths;
    paths.reserve(size_t(n) * m);
    int width = (n + 1) * d, height = (m + 1) * d;
    for (int y = 1; y <= m; ++y) {
      int k = std::min(y, m + 1 - y);
      fan(paths, k, d, [=](int u, int v) { return Point{u, y * d + v}; });
      int right_count = k - int(n == m && m % 2 && y == (m + 1) / 2);
      fan(paths, right_count, d,
          [=](int u, int v) { return Point{width - u, y * d + v}; });
    }
    for (int x = 1; x <= n; ++x) {
      int c = std::min(x, n + 1 - x);
      fan(paths, std::min((m + 1) / 2, c - 1), d,
          [=](int u, int v) { return Point{x * d + v, u}; });
      fan(paths, std::min(m / 2, c - 1), d,
          [=](int u, int v) { return Point{x * d + v, height - u}; });
    }
    if (original_n < original_m)
      for (auto &path : paths)
        for (auto &point : path)
          std::swap(point.x, point.y);
    long long total = 0;
    for (const auto &path : paths)
      total += length(path);
    if (total != formula(n, m, d))
      throw std::runtime_error("construction length disagrees with formula");
    double seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
            .count();
    verify(original_n, original_m, d, paths, total);
    if (argc == 5) {
      std::ofstream out(argv[4]);
      out.exceptions(std::ios::failbit | std::ios::badbit);
      out << "{\"N\":" << original_n << ",\"M\":" << original_m
          << ",\"d\":" << d << ",\"total_length\":" << total << ",\"paths\":[";
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
    }
    std::cout << "{\"N\":" << original_n << ",\"M\":" << original_m
              << ",\"d\":" << d
              << ",\"verified\":true,\"total_length\":" << total
              << ",\"formula\":" << formula(n, m, d)
              << ",\"seconds\":" << seconds << "}\n";
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
