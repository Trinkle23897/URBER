#include "residual_repair.hpp"
#include "verify.hpp"
#include <iostream>

int main() {
  // A hand-constructed 3x3 routing; the center escapes through the y=3
  // corridor.
  const std::vector<Path> valid = {{{2, 0}, {2, 2}},
                                   {{0, 4}, {2, 4}},
                                   {{2, 8}, {2, 6}},
                                   {{4, 0}, {4, 2}},
                                   {{0, 3}, {3, 3}, {3, 4}, {4, 4}},
                                   {{4, 8}, {4, 6}},
                                   {{6, 0}, {6, 2}},
                                   {{8, 4}, {6, 4}},
                                   {{6, 8}, {6, 6}}};
  verify(3, 3, 2, valid, 21);
  auto reject = [](const std::vector<Path> &paths, long long expected) {
    try {
      verify(3, 3, 2, paths, expected);
    } catch (const std::runtime_error &) {
      return;
    }
    throw std::runtime_error("validator accepted corrupted routing");
  };
  auto damaged = valid;
  damaged.pop_back();
  reject(damaged, 19);
  damaged = valid;
  damaged.back() = valid.front();
  reject(damaged, 21);
  damaged = valid;
  damaged[4] = {{0, 4}, {4, 4}};
  reject(damaged, 20);
  damaged = valid;
  damaged[4] = {{0, 1}, {3, 1}, {3, 4}, {4, 4}};
  reject(damaged, 23);
  damaged = valid;
  damaged[4] = {{0, 3}, {4, 4}};
  reject(damaged, 21);
  damaged = valid;
  damaged[4] = {{0, 3}, {3, 3}, {3, 5}, {4, 5}, {4, 4}};
  reject(damaged, 23);
  verify(3, 3, 2, damaged, 23, false);
  Residual limited(3, 3, 2, damaged);
  long long gain = 0;
  if (limited.improve(0, true, gain) || limited.exhausted)
    throw std::runtime_error(
        "zero search budget falsely improved or certified");
  verify(3, 3, 2, limited.paths(), 23, false);
  Residual repair(3, 3, 2, damaged);
  if (!repair.improve(1024, true, gain) || gain != 2)
    throw std::runtime_error("failed to remove a two-step detour");
  verify(3, 3, 2, repair.paths(), 21, false);
  // Warm labels need not be distances from the sink. Merely lowering the sink
  // label therefore does not establish an improving cycle.
  Residual warm(3, 3, 2, valid);
  warm.labels.assign(warm.sink + 1, 0);
  warm.labels[warm.sink] = 1000;
  if (warm.improve(1024, true, gain) || !warm.exhausted)
    throw std::runtime_error("warm labels changed an optimal routing");
  std::vector<long long> forged(warm.sink + 1, 0);
  if (warm.check_certificate(forged, std::numeric_limits<long long>::max() / 4))
    throw std::runtime_error("accepted a forged residual certificate");
  damaged = valid;
  damaged[4] = {{0, 3}, {-1, 3}, {-1, 4}, {4, 4}};
  reject(damaged, 23);
  reject(valid, 22);
  std::cout << "Validator accepted valid routing and rejected 8 corruptions.\n";
  std::cout << "Residual search respected zero budget and removed a detour.\n";
}
