CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra
PYTHON ?= python3

.PHONY: all pure-router test plot clean
all: pure-router build/urber
pure-router: build/pure_router build/pure_fan

build:
	mkdir -p $@

build/urber: src/urber.cpp src/routing_types.hpp src/verify.hpp src/residual_repair.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

build/pure_router: src/pure/pure_router.cpp src/routing_types.hpp src/verify.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

build/pure_fan: src/pure/pure_fan.cpp src/routing_types.hpp src/verify.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

build/test_verify: tests/test_verify.cpp src/routing_types.hpp src/verify.hpp src/residual_repair.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

test: all build/test_verify
	./build/test_verify
	$(PYTHON) -m unittest discover -s tests -v

plot:
	$(PYTHON) -m research.plot_benchmark

clean:
	rm -rf build
