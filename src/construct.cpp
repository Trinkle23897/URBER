#include "router.hpp"
#include "verify.hpp"

int main(int argc, char **argv) {
  try {
    if (argc < 4 || argc > 5)
      throw std::invalid_argument("usage: construct N M d [paths.json]");
    int n = std::stoi(argv[1]), m = std::stoi(argv[2]), d = std::stoi(argv[3]);
    if (n < 1 || m < 1 || d < 1 ||
        (n + 1LL) * (m + 1LL) > std::numeric_limits<int>::max() ||
        (n + m + 2LL) * d + 2 > std::numeric_limits<int>::max())
      throw std::invalid_argument(
          "require positive dimensions and int32 coordinates");
    if (2LL * d >= std::min(n, m))
      throw std::invalid_argument(
          "use pure_fan for the high-pitch construction");
    if (1LL * n * m > 2LL * (n + m + 2LL) * d - 4)
      throw std::invalid_argument(
          "not enough distinct boundary exits at this pitch");
    bool transpose = n < m;
    if (transpose)
      std::swap(n, m);
    auto started = std::chrono::steady_clock::now();
    // Preserve the balanced dense-grid construction. The revised central and
    // port-demand rules apply to the lower-density branch.
    bool revised_rules = 3LL * d >= m;
    Router router(n, m, d, false, revised_rules);
    bool ok = router.run();
    if (transpose) {
      for (auto &path : router.paths)
        for (auto &point : path)
          std::swap(point.x, point.y);
      std::swap(n, m);
      std::swap(router.N, router.M);
      std::swap(router.gx, router.gy);
    }
    if (ok) {
      router.occupied.clear();
      router.occupied.shrink_to_fit();
      verify(n, m, d, router.paths, router.total);
      if (argc == 5)
        router.write(argv[4]);
    }
    double seconds = std::chrono::duration<double>(
                         std::chrono::steady_clock::now() - started)
                         .count();
    std::cout << "{\"N\":" << n << ",\"M\":" << m << ",\"d\":" << d
              << ",\"verified\":" << (ok ? "true" : "false")
              << ",\"revised_rules\":" << (revised_rules ? "true" : "false")
              << ",\"total_length\":" << router.total
              << ",\"decision_work\":" << router.decision_work
              << ",\"seconds\":" << seconds << "}\n";
    return ok ? 0 : 1;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
