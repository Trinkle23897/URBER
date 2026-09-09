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
	$(PYTHON) -m research.plot_paper
	$(PYTHON) -m research.plot_benchmark
	$(PYTHON) -m research.plot_full_sweep benchmarks/full400/results.jsonl.gz --output assets/optimality-full400.png
	$(PYTHON) -m research.plot_full_sweep benchmarks/full400/results.jsonl.gz --output assets/optimality-full400.svg
	$(PYTHON) -m research.plot_routes benchmarks/paper/routes/mcf-30x30-d9.json benchmarks/paper/routes/paper-30x30-d9.json benchmarks/paper/routes/geometric-30x30-d9.json --labels "Minimum-cost flow" "Paper method" "Geometric replay" --output assets/routing-square.png
	$(PYTHON) -m research.plot_routes benchmarks/paper/routes/mcf-72x13-d6.json benchmarks/paper/routes/paper-72x13-d6.json benchmarks/paper/routes/geometric-72x13-d6.json --labels "Minimum-cost flow" "Paper method" "Geometric replay" --output assets/routing-rectangle.png

clean:
	rm -rf build
