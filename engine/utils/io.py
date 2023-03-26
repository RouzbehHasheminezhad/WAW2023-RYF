import logging
from engine.config.config import *

# The following function lists the network categories given the dataset directory.
def get_categories(data_dir):
    base_path = data_dir
    result_list = []
    for category_name in os.listdir(base_path):
        if category_name == "__MACOSX" or category_name == "nets.pkl":
            continue
        result_list.append(category_name)
    return result_list


# The following function lists the subcategories corresponding to a given network category, given the dataset's directory and the network category.
def get_subcategories(data_dir, category):
    result_list = []
    base_path = data_dir + category
    for subcategory_name in os.listdir(base_path):
        if subcategory_name == ".DS_Store":
            continue
        result_list.append(subcategory_name)
    return result_list


# Given the dataset's directory as well as the network category and subcategory, the following list the corresponding networks.
def get_networks(data_dir, category, subcategory):
    result_list = []
    base_path = data_dir + category + "/" + subcategory
    for network_name in os.listdir(base_path):
        if network_name == ".DS_Store":
            continue
        result_list.append(network_name)
    return result_list


# For a given that dataset's directory and a network in a specific subcategory and category, the following lists the corresponding subcategories.
def get_subnetworks(data_dir, category, subcategory, network):
    result_list = []
    network_path = data_dir + category + "/" + subcategory + "/" + network
    for subnetwork_name in os.listdir(network_path):
        if subnetwork_name == ".DS_Store":
            continue
        result_list.append(subnetwork_name)
    return result_list


# The following function loads the preprocessed version of a graph, given an argument list containing the:
# dataset's directory, the network's: category, subcategory, network, and subnetwork.
def load_graph(args):
    import graph_tool.all as gt
    data_dir, category, subcategory, network, subnetwork = args[0], args[1], args[2], args[3], args[4]
    pre_processed_file = data_dir + category + "/" + subcategory + "/" + network + "/" + subnetwork + "/Graph-Data/preprocessed/" + subnetwork + ".gt"
    return gt.load_graph(pre_processed_file)


# The following function preprocess a given empirical network.
def pre_process(args):
    import graph_tool.all as gt
    import os
    try:
        # As arguments of the function the directory of the datasets, the network's: category, subcategory, network, subnetwork information are mentioned.
        data_dir, category, subcategory, network, subnetwork = args[0], args[1], args[2], args[3], args[4]
        base = data_dir + category + "/" + subcategory + "/" + network + "/" + subnetwork + "/"
        file = base + "Graph-Data/" + subnetwork + ".gt"
        pre_processed_base = base + "Graph-Data/preprocessed/"
        pre_processed_file = pre_processed_base + subnetwork + ".gt"

        os.mkdir(pre_processed_base)
        # The preprocessing removes self-loops and parallel edges, finally discarding anything not in the largest connected component.
        g = gt.load_graph(file)
        gt.remove_self_loops(g)
        gt.remove_parallel_edges(g)
        gt.extract_largest_component(g, prune=True).save(pre_processed_file, fmt="gt")
        return (0,) + args
    except Exception as e:
        raise e
#        return (1,) + args


# The following resets the logger currently at use, to be able to start a new logging procedure.
def reset_logger():
    import logging
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)


# The following function re-configures the logger, sets a new logging file, and fixes the formatting style.
def set_logger(file_name):
    import logging
    from engine.config.config import get_log_dir
    reset_logger()
    logging.basicConfig(filename=get_log_dir() + file_name,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        filemode="w",
                        level=logging.INFO)


# The following function creates a logging directory, and logs the initial parameter of the analysis there.
def log_initial_parameters():
    os.mkdir(get_log_dir())
    set_logger("initial_params.log")
    logging.info("num_engines: %s", get_num_engines())
    logging.info("data_dir: %s", get_data_dir())
    logging.info("log_dir: %s", get_log_dir())
    logging.info("num_sampled_random_graphs: %s", get_num_sampled_random_graphs())
    logging.info("vertex_cut_off (lower bound): %s", get_vertex_cut_off())
    logging.info("edge_cut_off (lower bound): %s", get_edge_cut_off())
    logging.info("seed: %s", get_seed())
    reset_logger()


# Given a single value "val" and a group of values given in a list "arr", we compute the z-score to compare the single value to the group of values.
def z_score(val, arr):
    import numpy as np
    return (np.sqrt(len(arr)) * (val - np.mean(arr))) / (np.sqrt(np.var(arr, ddof=0)))


# The following function takes the fraction of removed vertices, and returns a list of tuples.
# The first three elements of each tuple are z-scores comparing the robustness of an empirical network, identified uniquely by the last four elements of the tuple.
# Each of the three z-score values reflects how the robustness of an empirical network compares to size-matching random graphs under: static/adaptive targeted attack
def compute_z_score(beta):
    import pickle
    index = int(beta * 100) - 1
    points = []
    data_dir = get_data_dir()
    for category in get_categories(data_dir):
        for subcategory in get_subcategories(data_dir, category):
            for network in get_networks(data_dir, category, subcategory):
                for subnetwork in get_subnetworks(data_dir, category, subcategory, network):
                    file_dir = data_dir + category + "/" + subcategory + "/" + network + "/" + subnetwork + "/Robustness-Score-Data/scores.pkl"
                    point = ()
                    with open(file_dir, "rb") as f:
                        scores = pickle.load(f)
                        for removal_strategy in ["static-targeted-attack", "adaptive-targeted-attack",
                                                 "random-failure"]:
                            score_main = scores["main"][removal_strategy][index]
                            score_baseline = [scores["baseline"][removal_strategy][i][index] for i in
                                              range(len(scores["baseline"][removal_strategy]))]
                            point = point + (z_score(score_main, score_baseline),)
                    points.append(point + (category, subcategory, network, subnetwork))
    return points
