# noinspection PyArgumentList
def compute_robustness_score(args):
    import graph_tool.all as gt
    import numpy as np
    read_path, write_path_static_attack, write_path_adaptive_attack, write_path_random, seed, file_name, data_dir = \
    args[0], args[1][0], args[1][1], args[1][2], args[2], args[3], args[4]

    # The following gets a connected graph and its vertices in the reverse removal order as datasets,
    # and outputs the corresponding robustness scores when i% of the vertices are removed where i is ranging from 1 ... 100.
    def get_scores(graph, reverse_removal_order):
        n_ = len(reverse_removal_order)
        res = np.concatenate((gt.vertex_percolation(graph, reverse_removal_order)[0][::-1][1:], [0])) / n_
        endpoints = [int(np.ceil(alpha * n_)) for alpha in np.linspace(0.01, 1, 100)]
        return [np.mean(res[:end]) for end in endpoints]

    # The following efficiently computes the reverse removal order when vertices are removed based on adaptive targeted attacks.
    # In an adaptive targeted attack in each iteration the vertex with the highest current degree is being removed.
    def adaptive_targeted_attack(graph, random):
        num_vertices = graph.num_vertices()
        bins = []
        pos, deg = [0] * num_vertices, [0] * num_vertices
        for i in random.permutation(num_vertices):
            v = graph.vertex(i)
            k = v.out_degree()
            while k >= len(bins):
                bins.append([])
            bins[k].append(i)
            pos[i], deg[i] = len(bins[k]) - 1, k
        max_deg = len(bins) - 1
        removal_order = []
        for k in range(max_deg, -1, -1):
            while len(bins[k]) != 0:
                v = bins[k].pop()
                neighbors_v = graph.get_out_neighbors(v)
                random.shuffle(neighbors_v)
                for u in neighbors_v:
                    if deg[u] > 0:
                        bin_u, pos_u = deg[u], pos[u]
                        pos[bins[bin_u][-1]] = pos_u
                        bins[bin_u][pos_u], bins[bin_u][-1] = bins[bin_u][-1], bins[bin_u][pos_u]
                        bins[bin_u].pop()
                        bins[bin_u - 1].append(u)
                        pos[u] = len(bins[bin_u - 1]) - 1
                        deg[u] -= 1
                deg[v] = 0
                removal_order.append(v)
        return removal_order[::-1]

    try:
        # Load the graph, set n to be the number of its vertices, and fix rs to be the random state.
        g = gt.load_graph(read_path)
        n = g.num_vertices()
        rs = np.random.default_rng(seed)
        # Compute the revered vertex removal orders under static and adaptive targeted attacks as well as random failures.
        reverse_static_attack_order = np.argsort(g.get_out_degrees(np.arange(n)) + rs.random(n))
        reverse_adaptive_attack_order = adaptive_targeted_attack(g, rs)
        reverse_random_order = rs.permutation(n)
        # Write the computed robustness scores in the corresponding NumPy files.
        np.save(write_path_static_attack + str(file_name) + ".npy", get_scores(g, reverse_static_attack_order))
        np.save(write_path_adaptive_attack + str(file_name) + ".npy", get_scores(g, reverse_adaptive_attack_order))
        np.save(write_path_random + str(file_name) + ".npy", get_scores(g, reverse_random_order))
        return (0,) + tuple(
            write_path_static_attack[len(data_dir):][:-len('/Robustness-Score-Data/static-targeted-attack/')].split(
                "/")) + (
            seed, file_name,)

    except (Exception,):
        return (1,) + tuple(
            write_path_static_attack[len(data_dir):][:-len('/Robustness-Score-Data/static-targeted-attack/')].split(
                "/")) + (
            seed, file_name,)


# A vectorized implementation for efficient generation of large random graphs based on: https://doi.org/10.1103/PhysRevE.71.036113.
def fast_gnm(args):
    import graph_tool.all as gt
    import numpy as np
    from numba import guvectorize, int64
    # The following takes a vector of size m in which elements are chosen randomly without repetition in the range from 0 to 0.5*n*(n-1),
    # and transforms it to an edge list of a random network with n vertices and m edges. This is fast for larger networks given the vectorization by Numba.
    # This method of generating random networks is based on the equation on the bottom left of page 036113-3 in  https://doi.org/10.1103/PhysRevE.71.036113.
    @guvectorize([(int64[:], int64[:], int64[:, :])], '(n), (m) -> (n, m)')
    def transform(x, _, res):
        for i in range(x.shape[0]):
            res[i, 0] = int(1 + np.floor(-0.5 + np.sqrt(0.25 + (2 * x[i]))))
            res[i, 1] = int(x[i] - (res[i, 0] * (res[i, 0] - 1) / 2))

    # Get the dataset's directory, directory to write the random network, number of vertices (n), number of edges (m), and the random seed.
    data_dir, net_dir, n, m, seed = args[0], args[1], args[2], args[3], args[4]
    # Set the random number generator.
    rs = np.random.default_rng(seed)
    # We attempt at most 100 times to generate a random network with the desired properties.
    num_attempts = 0
    while num_attempts < 100:
        #  We generate a random network with n vertices and m edges, wherein the largest connected component contains at least 96% of the vertices.
        g = gt.Graph(directed=False)
        g.add_vertex(n)
        g.add_edge_list(transform(rs.choice(int((n * (n - 1)) / 2), size=m, replace=False) + 1, [0, 0]))
        g = gt.extract_largest_component(g, directed=False, prune=True)
        if g.num_vertices() / n >= 0.96:
            g.save(net_dir + str(seed) + ".gt", fmt="gt")
            return (0,) + tuple(args[1][len(data_dir):][:-len('/Graph-Data/random-nets/')].split("/")) + (
                args[2], args[3], args[4],)
        else:
            num_attempts += 1
    return (1,) + tuple(args[1][len(data_dir):][:-len('/Graph-Data/random-nets/')].split("/")) + (
        args[2], args[3], args[4],)
