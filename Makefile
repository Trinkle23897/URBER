CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra
PYTHON ?= python3

.PHONY: all test plot clean
all: build/pure_fan build/urber build/construct

build:
	mkdir -p $@

build/construct: src/construct.cpp src/router.hpp src/routing_types.hpp src/verify.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

build/urber: src/urber.cpp src/router.hpp src/routing_types.hpp src/verify.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

build/pure_fan: src/pure/pure_fan.cpp src/routing_types.hpp src/verify.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

build/test_verify: tests/test_verify.cpp src/routing_types.hpp src/verify.hpp | build
	$(CXX) $(CXXFLAGS) -Isrc $< -o $@

test: all build/test_verify
	./build/test_verify
	$(PYTHON) -m unittest discover -s tests -v

plot:
	$(PYTHON) -m research.plot_paper --results benchmarks/paper/revised_ii.jsonl
	$(PYTHON) -m research.plot_full_sweep benchmarks/rules100/results.jsonl.gz --max-n 100 --output assets/optimality-rules100.png
	$(PYTHON) -m research.plot_full_sweep benchmarks/rules100/results.jsonl.gz --max-n 100 --output assets/optimality-rules100.svg
	$(PYTHON) -m research.plot_full_sweep benchmarks/rules400/results.jsonl.gz --max-n 400 --output assets/optimality-rules400.png
	$(PYTHON) -m research.plot_full_sweep benchmarks/rules400/results.jsonl.gz --max-n 400 --output assets/optimality-rules400.svg
	$(PYTHON) -m research.plot_routes benchmarks/paper/routes/mcf-30x30-d9.json benchmarks/paper/routes/paper-30x30-d9.json benchmarks/paper/routes/single_pass-30x30-d9.json --labels "Minimum-cost flow" "Paper method" "Revised deterministic rules" --output assets/routing-square.png
	$(PYTHON) -m research.plot_routes benchmarks/paper/routes/mcf-72x13-d6.json benchmarks/paper/routes/paper-72x13-d6.json benchmarks/paper/routes/single_pass-72x13-d6.json --labels "Minimum-cost flow" "Paper method" "Revised deterministic rules" --output assets/routing-rectangle.png
	$(PYTHON) -m research.plot_routes benchmarks/paper/routes/mcf-24x13-d6.json benchmarks/paper/routes/paper-24x13-d6.json benchmarks/paper/routes/single_pass-24x13-d6.json --labels "Minimum-cost flow" "Paper method" "Revised deterministic rules" --output assets/routing-improvement.png

clean:
	rm -rf build
