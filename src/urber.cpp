#include "router.hpp"

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
