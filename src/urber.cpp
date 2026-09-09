#include "router.hpp"
#include "verify.hpp"

// Degenerate one- and two-terminal-wide arrays use distinct nearest exits.
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

int main(int argc, char **argv) {
  try {
    if (argc < 4 || argc > 5 ||
        (argc == 5 && std::string(argv[4]).rfind("--", 0) == 0))
      throw std::invalid_argument("usage: urber N M d [paths.json]");
    int n = std::stoi(argv[1]), m = std::stoi(argv[2]), d = std::stoi(argv[3]);
    if (n < 1 || m < 1 || d < 1 ||
        (n + 1LL) * (m + 1LL) > std::numeric_limits<int>::max() ||
        (n + m + 2LL) * d + 2 > std::numeric_limits<int>::max())
      throw std::invalid_argument(
          "require N,M >= 1, d >= 1 and grid coordinates fitting int32");
    auto start = std::chrono::steady_clock::now();
    Router router(n, m, d);
    bool ok;
    if (std::min(n, m) <= 2) {
      router.paths = fan_routes(n, m, d);
      for (const auto &path : router.paths)
        router.total += length(path);
      ok = true;
    } else {
      ok = router.run();
    }
    double seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - start)
            .count();
    if (ok) {
      router.occupied.clear();
      router.occupied.shrink_to_fit();
      verify(n, m, d, router.paths, router.total);
      if (argc == 5)
        router.write(argv[4]);
    }
    std::cout << "{\"N\":" << n << ",\"M\":" << m << ",\"d\":" << d
              << ",\"success\":" << (ok ? "true" : "false")
              << ",\"verified\":" << (ok ? "true" : "false")
              << ",\"routed\":" << router.paths.size()
              << ",\"total_length\":" << router.total
              << ",\"seconds\":" << seconds << "}\n";
    return ok ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
