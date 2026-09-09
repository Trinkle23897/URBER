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
  damaged = valid;
  damaged[4] = {{0, 3}, {-1, 3}, {-1, 4}, {4, 4}};
  reject(damaged, 23);
  reject(valid, 22);
  std::cout << "Validator accepted valid routing and rejected 8 corruptions.\n";
}
