#
# This example defines a script that solves the Traveling
# Salesperson Problem using a naive branching and bounding
# strategy. It highlights how the optional notify_* Problem
# methods can be used to save the problem state for the best
# solution and broadcast it to all processes at the end of
# the solve.
#
# This example can be executed in serial as
#
# $ python tsp_naive.py
#
# or in parallel as
#
# $ mpiexec -n <n> python tsp_naive.py
#
import pybnb

def parse_dense_adjacency(filename):
    """Extracts a dense adjacency matrix from a file with
    the given name. Assumes columns are separated by
    whitespace and rows are separated by newlines. For
    consistency, entries that are zero or inf will be
    converted to `None`."""
    import math
    adj = []
    with open(filename) as f:
        line = f.readline().strip()
        while line:
            adj.append([float(x) for x in line.split()])
            line = f.readline().strip()
    N = len(adj)
    inf = float('inf')
    for row in adj:
        assert len(row) == N
        for i,c in enumerate(row):
            assert c != -inf
            assert not math.isnan(c)
            if (c == 0) or (c == inf):
                row[i] = None
    return adj

class TSP_Naive(pybnb.Problem):

    def __init__(self, adj):
        self._adj = adj
        self._N = len(adj)
        # state that changes during the solve
        self._path = [0]

    #
    # Implement Problem abstract methods
    #

    def sense(self):
        return pybnb.minimize

    def objective(self):
        cost = self.infeasible_objective()
        if len(self._path) == self._N:
            return_cost = self._adj[self._path[-1]][self._path[0]]
            if return_cost is not None:
                cost = 0.0
                for i in range(self._N-1):
                    assert self._path[i] != -1
                    assert self._path[i+1] != -1
                    cost += self._adj[self._path[i]][self._path[i+1]]
                cost += self._adj[self._path[-1]][self._path[0]]
        return cost

    def bound(self):
        if len(self._path) == self._N:
            return self.objective()

        visited = set(self._path)
        remaining = []
        for u in range(self._N):
            if u not in visited:
                remaining.append(u)
        assert len(remaining) > 0

        bound = 0
        # for the edges that are certain
        for i in range(len(self._path) - 1):
            bound += self._adj[self._path[i]][self._path[i+1]]
        # for the last item
        last = self._path[-1]
        tmp = [self._adj[last][v] for v in remaining
               if self._adj[last][v] is not None]
        if len(tmp) == 0:
            return self.infeasible_objective()
        bound += min(self._adj[last][v] for v in remaining
                     if self._adj[last][v] is not None)
        # for the undetermined nodes
        p = [self._path[0]] + remaining
        for r in remaining:
            tmp = [self._adj[r][v] for v in p
                   if self._adj[r][v] is not None]
            if len(tmp) == 0:
                return self.infeasible_objective()
            bound += min(tmp)
        return bound

    def save_state(self, node):
        node.state = self._path

    def load_state(self, node):
        self._path = node.state
        assert len(self._path) <= self._N

    def branch(self):
        # note that the branch method should never be called
        # with a path of length N as the objective and bound
        # converge exactly in that case.
        assert len(self._path) < self._N
        u = self._path[-1]
        visited = set(self._path)
        for v in range(self._N):
            # adj[u][v] == None means there is
            # either no edge or u == v
            if (self._adj[u][v] is not None) and \
               (v not in visited):
                child = pybnb.Node()
                child.state = self._path + [v]
                yield child

    def notify_solve_finished(self,
                              comm,
                              worker_comm,
                              results):
        tour = None
        if (results.best_node is not None) and \
           (results.best_node.state is not None):
            path = results.best_node.state
            tour_ = path + [path[0]]
            tour = {'cost': results.best_node.objective,
                    'tour': tour_}
        results.tour = tour

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description=("Run parallel branch and bound "
                     "to solve an instance of TSP."))
    parser.add_argument("--results-filename", type=str, default=None,
                        help=("When set, saves the solver results into a "
                              "YAML-formated file with the given name."))
    args = parser.parse_args()

    # data source: https://people.sc.fsu.edu/~jburkardt/datasets/tsp/tsp.html
    thisdir = os.path.dirname(os.path.abspath(__file__))
    adj = parse_dense_adjacency(os.path.join(thisdir, 'p01_d.txt'))
    problem = TSP_Naive(adj)
    solver = pybnb.Solver()

    # solve exactly (disable check for relative
    # gap and use absolute gap of zero)
    results = solver.solve(
        problem,
        absolute_gap=0,
        relative_gap=None,
        queue_strategy='depth',
        log_new_incumbent=False)

    stats = solver.collect_worker_statistics()
    if solver.is_dispatcher:
        pybnb.solver.summarize_worker_statistics(stats)
        # save results to a file
        # (mainly used for testing this example)
        if args.results_filename is not None:
            results.write(args.results_filename)
